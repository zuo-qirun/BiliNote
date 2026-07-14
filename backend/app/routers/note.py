# app/routers/note.py
import json
import hashlib
import hmac
import os
import re
import secrets
import sqlite3
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

from fastapi import APIRouter, HTTPException, BackgroundTasks, UploadFile, File, Header
from pydantic import BaseModel, Field, validator, field_validator
from dataclasses import asdict

from app.db.video_task_dao import get_task_by_video
from app.enmus.exception import NoteErrorEnum
from app.enmus.note_enums import DownloadQuality
from app.exceptions.note import NoteError
from app.services.note import NoteGenerator, logger
from app.services.task_serial_executor import task_serial_executor
from app.utils.response import ResponseWrapper as R
from app.utils.error_diagnosis import diagnose_task_error
from app.utils.url_parser import extract_video_id
from app.validators.video_url_validator import is_supported_video_url
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
import httpx
from app.enmus.task_status_enums import TaskStatus
from app.utils.video_helper import generate_screenshot
from app.services.account_access import (
    ROLE_LABELS,
    account_db,
    account_quota,
    consume_generation_quota,
    create_captcha,
    login_user,
    public_user,
    register_user,
    require_account,
    require_admin,
)

# from app.services.downloader import download_raw_audio
# from app.services.whisperer import transcribe_audio

router = APIRouter()


class RecordRequest(BaseModel):
    video_id: str
    platform: str


class ShareNoteRequest(BaseModel):
    markdown: str = Field(min_length=1, max_length=2_000_000)
    title: str = Field(default="BiliNote 分享笔记", max_length=500)
    task_id: Optional[str] = Field(default=None, max_length=100)
    video_url: Optional[str] = Field(default=None, max_length=2000)
    platform: Optional[str] = Field(default=None, max_length=100)
    author: Optional[str] = Field(default=None, max_length=300)


class AuthCredentials(BaseModel):
    username: str = Field(min_length=3, max_length=32)
    password: str = Field(min_length=8, max_length=128)


class RegisterRequest(AuthCredentials):
    email: str = Field(min_length=5, max_length=254)
    phone: Optional[str] = Field(default=None, max_length=30)
    captcha_id: str = Field(min_length=10, max_length=100)
    captcha_code: str = Field(min_length=4, max_length=10)


class RoleUpdateRequest(BaseModel):
    role: str = Field(pattern=r"^(free|privileged|admin)$")


class SyncTasksRequest(BaseModel):
    tasks: list[dict] = Field(default_factory=list, max_length=200)


class VideoRequest(BaseModel):
    video_url: str
    platform: str
    quality: DownloadQuality
    screenshot: Optional[bool] = False
    link: Optional[bool] = False
    model_name: str
    provider_id: str
    task_id: Optional[str] = None
    format: Optional[list] = []
    style: str = None
    extras: Optional[str]=None
    video_understanding: Optional[bool] = False
    video_interval: Optional[int] = 0
    grid_size: Optional[list] = []
    # 客户端（如浏览器插件）已经在用户浏览器里抓到字幕，直接传给后端复用，
    # 跳过 download_subtitles 和音频转写。形如：
    #   {"language": "zh", "full_text": "...", "segments": [{"start","end","text"}, ...]}
    prefetched_transcript: Optional[dict] = None

    @field_validator("video_url")
    def validate_supported_url(cls, v):
        url = str(v)
        parsed = urlparse(url)
        if parsed.scheme in ("http", "https"):
            # 是网络链接，继续用原有平台校验
            if not is_supported_video_url(url):
                raise NoteError(code=NoteErrorEnum.PLATFORM_NOT_SUPPORTED.code,
                                message=NoteErrorEnum.PLATFORM_NOT_SUPPORTED.message)

        return v


NOTE_OUTPUT_DIR = os.getenv("NOTE_OUTPUT_DIR", "note_results")
SHARE_OUTPUT_DIR = Path(NOTE_OUTPUT_DIR) / "shares"
ACCOUNT_DB_PATH = Path(NOTE_OUTPUT_DIR) / "accounts.sqlite3"
UPLOAD_DIR = Path("uploads")
UPLOAD_CHUNK_SIZE = 1024 * 1024
UPLOAD_MAX_BYTES = int(os.getenv("UPLOAD_MAX_BYTES", str(10 * 1024 * 1024 * 1024)))
ALLOWED_VIDEO_SUFFIXES = {
    ".mp4", ".mkv", ".mov", ".avi", ".webm", ".flv", ".m4v", ".mpeg", ".mpg", ".ts",
}


def _account_db():
    ACCOUNT_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(ACCOUNT_DB_PATH, timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("PRAGMA foreign_keys=ON")
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            username_key TEXT NOT NULL UNIQUE,
            password_salt TEXT NOT NULL,
            password_hash TEXT NOT NULL,
            created_at INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS account_sessions (
            token_hash TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            expires_at INTEGER NOT NULL,
            created_at INTEGER NOT NULL,
            FOREIGN KEY(user_id) REFERENCES accounts(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS synced_tasks (
            user_id INTEGER NOT NULL,
            task_id TEXT NOT NULL,
            snapshot_json TEXT NOT NULL,
            updated_at INTEGER NOT NULL,
            created_at INTEGER NOT NULL,
            PRIMARY KEY(user_id, task_id),
            FOREIGN KEY(user_id) REFERENCES accounts(id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_synced_tasks_user_updated
            ON synced_tasks(user_id, updated_at DESC);
        """
    )
    return connection


def _username_key(username: str) -> tuple[str, str]:
    cleaned = username.strip()
    if not re.fullmatch(r"[A-Za-z0-9_.-]{3,32}", cleaned):
        raise HTTPException(
            status_code=400,
            detail="账号仅支持 3-32 位字母、数字、点、下划线或短横线",
        )
    return cleaned, cleaned.casefold()


def _password_hash(password: str, salt: bytes) -> str:
    return hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        310_000,
    ).hex()


def _issue_session(connection: sqlite3.Connection, user_id: int) -> str:
    now = int(time.time())
    token = secrets.token_urlsafe(32)
    connection.execute(
        """
        INSERT INTO account_sessions(token_hash, user_id, expires_at, created_at)
        VALUES (?, ?, ?, ?)
        """,
        (hashlib.sha256(token.encode()).hexdigest(), user_id, now + 180 * 86400, now),
    )
    connection.execute("DELETE FROM account_sessions WHERE expires_at < ?", (now,))
    connection.commit()
    return token


def _require_account(authorization: Optional[str] = Header(default=None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="请先登录")
    token = authorization[7:].strip()
    if not token:
        raise HTTPException(status_code=401, detail="登录状态无效")

    now = int(time.time())
    with _account_db() as connection:
        row = connection.execute(
            """
            SELECT accounts.id, accounts.username
            FROM account_sessions
            JOIN accounts ON accounts.id = account_sessions.user_id
            WHERE account_sessions.token_hash = ? AND account_sessions.expires_at > ?
            """,
            (hashlib.sha256(token.encode()).hexdigest(), now),
        ).fetchone()
    if not row:
        raise HTTPException(status_code=401, detail="登录已过期，请重新登录")
    return {"id": row["id"], "username": row["username"]}


def _task_timestamp(task: dict, key: str, fallback: int) -> int:
    value = task.get(key)
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, str) and value:
        try:
            return int(datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp() * 1000)
        except ValueError:
            pass
    return fallback


def save_note_to_file(task_id: str, note):
    os.makedirs(NOTE_OUTPUT_DIR, exist_ok=True)
    with open(os.path.join(NOTE_OUTPUT_DIR, f"{task_id}.json"), "w", encoding="utf-8") as f:
        json.dump(asdict(note), f, ensure_ascii=False, indent=2)


def _persist_prefetched_transcript(task_id: str, transcript: dict) -> None:
    """把客户端预取的字幕写到 NoteGenerator 期望的转写缓存文件里。

    NoteGenerator.generate 会优先读 <task_id>_transcript.json，命中即跳过 download_subtitles
    与音频转写流程。要求字段：language(可空)/full_text/segments[{start,end,text}]
    """
    segments = transcript.get("segments") or []
    cleaned_segments = []
    for s in segments:
        text = (s.get("text") or "").strip()
        if not text:
            continue
        cleaned_segments.append({
            "start": float(s.get("start", 0)),
            "end": float(s.get("end", 0)),
            "text": text,
        })
    if not cleaned_segments:
        raise ValueError("prefetched_transcript 没有可用的 segments")

    full_text = transcript.get("full_text") or " ".join(s["text"] for s in cleaned_segments)
    payload = {
        "language": transcript.get("language") or "zh",
        "full_text": full_text,
        "segments": cleaned_segments,
    }

    os.makedirs(NOTE_OUTPUT_DIR, exist_ok=True)
    target = os.path.join(NOTE_OUTPUT_DIR, f"{task_id}_transcript.json")
    with open(target, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    logger.info(f"已写入客户端预取字幕缓存: {target} ({len(cleaned_segments)} 段)")


def run_note_task(task_id: str, video_url: str, platform: str, quality: DownloadQuality,
                  link: bool = False, screenshot: bool = False, model_name: str = None, provider_id: str = None,
                  _format: list = None, style: str = None, extras: str = None, video_understanding: bool = False,
                  video_interval=0, grid_size=[]
                  ):

    if not model_name or not provider_id:
        raise HTTPException(status_code=400, detail="请选择模型和提供者")

    def _execute_note_task():
        return NoteGenerator().generate(
            video_url=video_url,
            platform=platform,
            quality=quality,
            task_id=task_id,
            model_name=model_name,
            provider_id=provider_id,
            link=link,
            _format=_format,
            style=style,
            extras=extras,
            screenshot=screenshot,
            video_understanding=video_understanding,
            video_interval=video_interval,
            grid_size=grid_size,
        )

    logger.info(f"任务进入执行队列 (task_id={task_id})")
    note = task_serial_executor.run(_execute_note_task)
    logger.info(f"Note generated: {task_id}")
    if not note or not note.markdown:
        logger.warning(f"任务 {task_id} 执行失败，跳过保存")
        return
    save_note_to_file(task_id, note)

    # 自动建立向量索引（用于 AI 问答），失败不影响笔记生成
    try:
        from app.services.vector_store import VectorStoreManager
        VectorStoreManager().index_task(task_id)
    except Exception as e:
        logger.warning(f"向量索引失败（不影响笔记）: {e}")


@router.post('/delete_task')
def delete_task(data: RecordRequest):
    try:
        # TODO: 待持久化完成
        # NoteGenerator().delete_note(video_id=data.video_id, platform=data.platform)
        return R.success(msg='删除成功')
    except Exception as e:
        return R.error(msg=e)


@router.post("/upload")
async def upload(file: UploadFile = File(...)):
    original_name = Path(file.filename or "video").name
    suffix = Path(original_name).suffix.lower()
    if suffix not in ALLOWED_VIDEO_SUFFIXES:
        await file.close()
        return R.error(
            msg="不支持该文件格式，请上传 MP4、MKV、MOV、AVI、WebM 等常见视频文件",
            code=400,
            data={"reason": "unsupported_video_format"},
        )

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    safe_stem = re.sub(r"[^\w.-]+", "_", Path(original_name).stem, flags=re.UNICODE).strip("._")[:80]
    safe_stem = safe_stem or "video"
    stored_name = f"{safe_stem}-{uuid.uuid4().hex[:12]}{suffix}"
    file_location = UPLOAD_DIR / stored_name
    uploaded_bytes = 0

    try:
        with file_location.open("xb") as destination:
            while chunk := await file.read(UPLOAD_CHUNK_SIZE):
                uploaded_bytes += len(chunk)
                if uploaded_bytes > UPLOAD_MAX_BYTES:
                    raise ValueError("upload_too_large")
                destination.write(chunk)
    except ValueError as exc:
        file_location.unlink(missing_ok=True)
        if str(exc) == "upload_too_large":
            return R.error(
                msg=f"文件超过服务器允许的最大大小（{UPLOAD_MAX_BYTES // 1024 // 1024} MB）",
                code=413,
                data={"reason": "upload_too_large", "max_bytes": UPLOAD_MAX_BYTES},
            )
        raise
    except Exception as exc:
        file_location.unlink(missing_ok=True)
        logger.error("保存上传视频失败: %s", exc, exc_info=True)
        return R.error(
            msg="服务器保存视频失败，请检查磁盘空间后重试",
            code=500,
            data={"reason": "upload_save_failed"},
        )
    finally:
        await file.close()

    return R.success({
        "url": f"/uploads/{stored_name}",
        "filename": stored_name,
        "original_filename": original_name,
        "size": uploaded_bytes,
    })


@router.post("/generate_note")
def generate_note(
    data: VideoRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    authorization: Optional[str] = Header(default=None),
):
    try:
        # 就绪门禁：本地转写引擎（fast-whisper / mlx-whisper）必须等模型下载完才能跑视频，
        # 否则任务会卡在首次下载（慢 / OOM / 截断），用户只看到一个静默失败的任务。
        # 客户端已抓好字幕（prefetched_transcript）则不需要转写，跳过检查。
        if not data.prefetched_transcript:
            from app.services.transcriber_config_manager import TranscriberConfigManager
            readiness = TranscriberConfigManager().is_model_ready()
            if not readiness["ready"]:
                logger.warning(f"拒绝 generate_note：{readiness['reason']}")
                return R.error(
                    msg=readiness["reason"],
                    code=300102,
                    data={
                        "reason": "transcriber_model_not_ready",
                        "transcriber_type": readiness["transcriber_type"],
                        "model_size": readiness["model_size"],
                        "downloading": readiness["downloading"],
                    },
                )

        quota = consume_generation_quota(request, authorization)
        video_id = extract_video_id(data.video_url, data.platform)
        # if not video_id:
        #     raise HTTPException(status_code=400, detail="无法提取视频 ID")
        # existing = get_task_by_video(video_id, data.platform)
        # if existing:
        #     return R.error(
        #         msg='笔记已生成，请勿重复发起',
        #
        #     )
        if data.task_id:
            # 如果传了task_id，说明是重试！
            task_id = data.task_id
            logger.info(f"重试模式，复用已有 task_id={task_id}")
        else:
            # 正常新建任务
            task_id = str(uuid.uuid4())

        # 统一先写入 PENDING，表示已进入队列等待串行执行
        NoteGenerator()._update_status(task_id, TaskStatus.PENDING)

        # 客户端已经抓好字幕的话，写到转写缓存文件，NoteGenerator 的 cache-hit 逻辑会直接用上
        if data.prefetched_transcript:
            try:
                _persist_prefetched_transcript(task_id, data.prefetched_transcript)
            except Exception as e:
                logger.warning(f"写入预取字幕失败 (task_id={task_id}): {e}")

        background_tasks.add_task(run_note_task, task_id, data.video_url, data.platform, data.quality, data.link,
                                  data.screenshot, data.model_name, data.provider_id, data.format, data.style,
                                  data.extras, data.video_understanding, data.video_interval, data.grid_size)
        return R.success({"task_id": task_id, "quota": quota})
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/task_status/{task_id}")
def get_task_status(task_id: str):
    status_path = os.path.join(NOTE_OUTPUT_DIR, f"{task_id}.status.json")
    result_path = os.path.join(NOTE_OUTPUT_DIR, f"{task_id}.json")
    partial_result = NoteGenerator.get_partial_result(task_id)

    # 优先读状态文件
    if os.path.exists(status_path):
        with open(status_path, "r", encoding="utf-8") as f:
            status_content = json.load(f)

        status = status_content.get("status")
        message = status_content.get("message", "")

        if status == TaskStatus.SUCCESS.value:
            # 成功状态的话，继续读取最终笔记内容
            if os.path.exists(result_path):
                with open(result_path, "r", encoding="utf-8") as rf:
                    result_content = json.load(rf)
                return R.success({
                    "status": status,
                    "result": result_content,
                    "partial_result": partial_result,
                    "message": message,
                    "task_id": task_id
                })
            else:
                # 理论上不会出现，保险处理
                return R.success({
                    "status": TaskStatus.PENDING.value,
                    "message": "任务完成，但结果文件未找到",
                    "partial_result": partial_result,
                    "task_id": task_id
                })

        if status == TaskStatus.FAILED.value:
            if partial_result and partial_result.get("transcript"):
                failed_stage = "summarizing"
            elif partial_result and partial_result.get("audio_meta"):
                failed_stage = "transcribing"
            else:
                failed_stage = "unknown"
            error_detail = diagnose_task_error(message, stage=failed_stage)
            return R.error(
                message or "任务失败",
                code=500,
                data={
                    "status": status,
                    "message": message,
                    "error_detail": error_detail,
                    "partial_result": partial_result,
                    "task_id": task_id,
                },
            )

        # 处理中状态
        return R.success({
            "status": status,
            "message": message,
            "partial_result": partial_result,
            "task_id": task_id
        })

    # 没有状态文件，但有结果
    if os.path.exists(result_path):
        with open(result_path, "r", encoding="utf-8") as f:
            result_content = json.load(f)
        return R.success({
            "status": TaskStatus.SUCCESS.value,
            "result": result_content,
            "partial_result": partial_result,
            "task_id": task_id
        })

    # 什么都没有，默认PENDING
    return R.success({
        "status": TaskStatus.PENDING.value,
        "message": "任务排队中",
        "partial_result": partial_result,
        "task_id": task_id
    })


@router.get("/auth/captcha")
def auth_captcha():
    return R.success(create_captcha())


@router.post("/auth/register")
def register_account(data: RegisterRequest):
    return R.success(
        register_user(
            username=data.username,
            password=data.password,
            email=data.email,
            phone=data.phone,
            captcha_id=data.captcha_id,
            captcha_code=data.captcha_code,
        )
    )


@router.post("/auth/login")
def login_account(data: AuthCredentials):
    return R.success(login_user(data.username, data.password))


@router.get("/auth/me")
def current_account(authorization: Optional[str] = Header(default=None)):
    account = require_account(authorization)
    with account_db() as connection:
        row = connection.execute(
            "SELECT * FROM accounts WHERE id = ?",
            (account["id"],),
        ).fetchone()
        return R.success(public_user(connection, row))


@router.get("/auth/quota")
def current_quota(authorization: Optional[str] = Header(default=None)):
    return R.success(account_quota(require_account(authorization)))


@router.post("/auth/logout")
def logout_account(authorization: Optional[str] = Header(default=None)):
    if authorization and authorization.startswith("Bearer "):
        token_hash = hashlib.sha256(authorization[7:].strip().encode()).hexdigest()
        with _account_db() as connection:
            connection.execute(
                "DELETE FROM account_sessions WHERE token_hash = ?",
                (token_hash,),
            )
    return R.success()


@router.get("/admin/users")
def list_accounts(authorization: Optional[str] = Header(default=None)):
    require_admin(authorization)
    with account_db() as connection:
        rows = connection.execute(
            """
            SELECT id, username, email, phone, role, created_at
            FROM accounts ORDER BY created_at DESC
            LIMIT 1000
            """
        ).fetchall()
        users = []
        for row in rows:
            payload = dict(row)
            payload["role_label"] = ROLE_LABELS.get(row["role"], ROLE_LABELS["free"])
            payload["quota"] = account_quota(payload)
            users.append(payload)
    return R.success({"users": users})


@router.patch("/admin/users/{user_id}/role")
def update_account_role(
    user_id: int,
    data: RoleUpdateRequest,
    authorization: Optional[str] = Header(default=None),
):
    admin = require_admin(authorization)
    if admin["id"] == user_id and data.role != "admin":
        raise HTTPException(status_code=400, detail="不能取消自己的管理员权限")
    with account_db() as connection:
        cursor = connection.execute(
            "UPDATE accounts SET role = ? WHERE id = ?",
            (data.role, user_id),
        )
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="用户不存在")
        row = connection.execute(
            "SELECT * FROM accounts WHERE id = ?",
            (user_id,),
        ).fetchone()
        return R.success(public_user(connection, row))


@router.get("/sync/tasks")
def get_synced_tasks(authorization: Optional[str] = Header(default=None)):
    account = require_account(authorization)
    with _account_db() as connection:
        rows = connection.execute(
            """
            SELECT snapshot_json FROM synced_tasks
            WHERE user_id = ?
            ORDER BY updated_at DESC
            LIMIT 500
            """,
            (account["id"],),
        ).fetchall()

    tasks = []
    for row in rows:
        try:
            tasks.append(json.loads(row["snapshot_json"]))
        except json.JSONDecodeError:
            continue
    return R.success({"tasks": tasks})


@router.post("/sync/tasks")
def put_synced_tasks(
    data: SyncTasksRequest,
    authorization: Optional[str] = Header(default=None),
):
    account = require_account(authorization)
    now_ms = int(time.time() * 1000)
    synced = 0

    with _account_db() as connection:
        for item in data.tasks:
            task_id = str(item.get("task_id") or "")
            if not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", task_id):
                continue

            snapshot = dict(item)
            snapshot["task_id"] = task_id
            updated_at = _task_timestamp(snapshot, "updated_at", now_ms)
            created_at = _task_timestamp(snapshot, "created_at", updated_at)
            snapshot["updated_at"] = updated_at
            snapshot["created_at"] = created_at
            serialized = json.dumps(snapshot, ensure_ascii=False, separators=(",", ":"))
            if len(serialized.encode("utf-8")) > 3_000_000:
                continue

            connection.execute(
                """
                INSERT INTO synced_tasks(user_id, task_id, snapshot_json, updated_at, created_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(user_id, task_id) DO UPDATE SET
                    snapshot_json = excluded.snapshot_json,
                    updated_at = excluded.updated_at
                WHERE excluded.updated_at >= synced_tasks.updated_at
                """,
                (account["id"], task_id, serialized, updated_at, created_at),
            )
            synced += 1

        connection.execute(
            """
            DELETE FROM synced_tasks
            WHERE user_id = ? AND task_id NOT IN (
                SELECT task_id FROM synced_tasks
                WHERE user_id = ?
                ORDER BY updated_at DESC
                LIMIT 500
            )
            """,
            (account["id"], account["id"]),
        )

    return R.success({"synced": synced})


@router.delete("/sync/tasks/{task_id}")
def delete_synced_task(
    task_id: str,
    authorization: Optional[str] = Header(default=None),
):
    account = require_account(authorization)
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", task_id):
        raise HTTPException(status_code=400, detail="无效的任务 ID")
    with _account_db() as connection:
        connection.execute(
            "DELETE FROM synced_tasks WHERE user_id = ? AND task_id = ?",
            (account["id"], task_id),
        )
    return R.success()


@router.post("/share_note")
def share_note(data: ShareNoteRequest):
    SHARE_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    for _ in range(5):
        share_id = secrets.token_urlsafe(9)
        share_path = SHARE_OUTPUT_DIR / f"{share_id}.json"
        if not share_path.exists():
            break
    else:
        raise HTTPException(status_code=500, detail="无法创建分享链接")

    payload = {
        "share_id": share_id,
        "markdown": data.markdown,
        "title": data.title,
        "task_id": data.task_id,
        "video_url": data.video_url,
        "platform": data.platform,
        "author": data.author,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    temporary_path = share_path.with_suffix(".tmp")
    temporary_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    os.replace(temporary_path, share_path)

    return R.success({
        "share_id": share_id,
        "path": f"/share/{share_id}",
    })


@router.get("/shared_note/{share_id}")
def shared_note(share_id: str):
    if not re.fullmatch(r"[A-Za-z0-9_-]{8,32}", share_id):
        raise HTTPException(status_code=400, detail="无效的分享 ID")

    share_path = SHARE_OUTPUT_DIR / f"{share_id}.json"
    if not share_path.is_file():
        raise HTTPException(status_code=404, detail="分享笔记不存在")

    try:
        return R.success(json.loads(share_path.read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError):
        raise HTTPException(status_code=500, detail="分享笔记读取失败")


@router.get("/screenshot_frame")
def screenshot_frame(video_id: str, timestamp: int):
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", video_id):
        raise HTTPException(status_code=400, detail="无效的视频 ID")
    if timestamp < 0 or timestamp > 86400:
        raise HTTPException(status_code=400, detail="无效的截图时间")

    data_dir = Path(NOTE_OUTPUT_DIR).parent / "data"
    video_path = data_dir / f"{video_id}.mp4"
    if not video_path.is_file():
        raise HTTPException(status_code=404, detail="未找到本地视频文件")

    output_dir = Path(
        os.getenv("OUT_DIR", "/app/backend/static/screenshots")
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"frame_{video_id}_{timestamp:05}.jpg"

    if not output_path.is_file() or output_path.stat().st_size == 0:
        generated = Path(
            generate_screenshot(
                str(video_path),
                str(output_dir),
                timestamp,
                timestamp,
            )
        )
        if not generated.is_file() or generated.stat().st_size == 0:
            raise HTTPException(status_code=500, detail="截图生成失败")
        os.replace(generated, output_path)

    return FileResponse(
        output_path,
        media_type="image/jpeg",
        headers={"Cache-Control": "public, max-age=31536000, immutable"},
    )


@router.get("/image_proxy")
async def image_proxy(request: Request, url: str):
    headers = {
        "Referer": "https://www.bilibili.com/",
        "User-Agent": request.headers.get("User-Agent", ""),
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, headers=headers)

            if resp.status_code != 200:
                raise HTTPException(status_code=resp.status_code, detail="图片获取失败")

            content_type = resp.headers.get("Content-Type", "image/jpeg")
            return StreamingResponse(
                resp.aiter_bytes(),
                media_type=content_type,
                headers={
                    "Cache-Control": "public, max-age=86400",  #  缓存一天
                    "Content-Type": content_type,
                }
            )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
