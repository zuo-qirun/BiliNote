import base64
import hashlib
import hmac
import io
import os
import re
import secrets
import sqlite3
import time
from datetime import datetime
from pathlib import Path
from typing import Optional
from zoneinfo import ZoneInfo

from fastapi import Header, HTTPException, Request
from PIL import Image, ImageDraw, ImageFont


ROLE_LIMITS = {
    "free": 5,
    "privileged": 50,
    "admin": None,
}
ROLE_LABELS = {
    "free": "免费用户",
    "privileged": "特权用户",
    "admin": "管理员",
}
ACCOUNT_DB_PATH = Path(os.getenv("NOTE_OUTPUT_DIR", "note_results")) / "accounts.sqlite3"
_CAPTCHA_ALPHABET = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"


def account_db() -> sqlite3.Connection:
    ACCOUNT_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(ACCOUNT_DB_PATH, timeout=15)
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
            email TEXT,
            email_key TEXT,
            phone TEXT,
            role TEXT NOT NULL DEFAULT 'free',
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
        CREATE TABLE IF NOT EXISTS auth_captchas (
            captcha_id TEXT PRIMARY KEY,
            answer_hash TEXT NOT NULL,
            expires_at INTEGER NOT NULL,
            attempts INTEGER NOT NULL DEFAULT 0,
            created_at INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS generation_usage (
            subject_type TEXT NOT NULL,
            subject_key TEXT NOT NULL,
            period_key TEXT NOT NULL,
            count INTEGER NOT NULL DEFAULT 0,
            updated_at INTEGER NOT NULL,
            PRIMARY KEY(subject_type, subject_key, period_key)
        );
        CREATE INDEX IF NOT EXISTS idx_synced_tasks_user_updated
            ON synced_tasks(user_id, updated_at DESC);
        """
    )

    columns = {row["name"] for row in connection.execute("PRAGMA table_info(accounts)")}
    migrations = {
        "email": "ALTER TABLE accounts ADD COLUMN email TEXT",
        "email_key": "ALTER TABLE accounts ADD COLUMN email_key TEXT",
        "phone": "ALTER TABLE accounts ADD COLUMN phone TEXT",
        "role": "ALTER TABLE accounts ADD COLUMN role TEXT NOT NULL DEFAULT 'free'",
    }
    for column, statement in migrations.items():
        if column not in columns:
            connection.execute(statement)
    connection.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_accounts_email_key "
        "ON accounts(email_key) WHERE email_key IS NOT NULL"
    )
    connection.commit()
    return connection


def normalize_username(username: str) -> tuple[str, str]:
    cleaned = username.strip()
    if not re.fullmatch(r"[A-Za-z0-9_.-]{3,32}", cleaned):
        raise HTTPException(
            status_code=400,
            detail="账号仅支持 3-32 位字母、数字、点、下划线或短横线",
        )
    return cleaned, cleaned.casefold()


def normalize_email(email: str) -> tuple[str, str]:
    cleaned = email.strip()
    if len(cleaned) > 254 or not re.fullmatch(
        r"[^@\s]+@[^@\s]+\.[^@\s]+",
        cleaned,
    ):
        raise HTTPException(status_code=400, detail="邮箱格式不正确")
    return cleaned, cleaned.casefold()


def normalize_phone(phone: Optional[str]) -> Optional[str]:
    if not phone or not phone.strip():
        return None
    cleaned = re.sub(r"[\s()-]", "", phone.strip())
    if not re.fullmatch(r"\+?[0-9]{6,20}", cleaned):
        raise HTTPException(status_code=400, detail="手机号格式不正确")
    return cleaned


def password_hash(password: str, salt: bytes) -> str:
    return hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        310_000,
    ).hex()


def issue_session(connection: sqlite3.Connection, user_id: int) -> str:
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


def _quota_payload(connection: sqlite3.Connection, account: sqlite3.Row | dict) -> dict:
    role = account["role"] if account["role"] in ROLE_LIMITS else "free"
    limit = ROLE_LIMITS[role]
    period_key = datetime.now(ZoneInfo("Asia/Shanghai")).strftime("%Y-%m-%d")
    used = connection.execute(
        """
        SELECT count FROM generation_usage
        WHERE subject_type = 'account' AND subject_key = ? AND period_key = ?
        """,
        (str(account["id"]), period_key),
    ).fetchone()
    used_count = int(used["count"]) if used else 0
    return {
        "role": role,
        "role_label": ROLE_LABELS[role],
        "limit": limit,
        "used": used_count,
        "remaining": None if limit is None else max(limit - used_count, 0),
        "period": "day",
        "period_key": period_key,
    }


def public_user(connection: sqlite3.Connection, account: sqlite3.Row | dict) -> dict:
    return {
        "username": account["username"],
        "email": account["email"],
        "phone": account["phone"],
        "role": account["role"],
        "role_label": ROLE_LABELS.get(account["role"], ROLE_LABELS["free"]),
        "quota": _quota_payload(connection, account),
    }


def optional_account(authorization: Optional[str]) -> Optional[dict]:
    if not authorization or not authorization.startswith("Bearer "):
        return None
    token = authorization[7:].strip()
    if not token:
        return None
    now = int(time.time())
    with account_db() as connection:
        row = connection.execute(
            """
            SELECT accounts.id, accounts.username, accounts.email, accounts.phone, accounts.role
            FROM account_sessions
            JOIN accounts ON accounts.id = account_sessions.user_id
            WHERE account_sessions.token_hash = ? AND account_sessions.expires_at > ?
            """,
            (hashlib.sha256(token.encode()).hexdigest(), now),
        ).fetchone()
    return dict(row) if row else None


def require_account(authorization: Optional[str] = Header(default=None)) -> dict:
    account = optional_account(authorization)
    if not account:
        raise HTTPException(status_code=401, detail="请先登录")
    return account


def require_admin(authorization: Optional[str] = Header(default=None)) -> dict:
    account = require_account(authorization)
    if account["role"] != "admin":
        raise HTTPException(status_code=403, detail="仅管理员可以修改全局配置")
    return account


def create_captcha() -> dict:
    answer = "".join(secrets.choice(_CAPTCHA_ALPHABET) for _ in range(5))
    captcha_id = secrets.token_urlsafe(18)
    now = int(time.time())
    answer_hash = hashlib.sha256(f"{captcha_id}:{answer}".encode()).hexdigest()

    image = Image.new("RGB", (170, 54), "#f5f3ef")
    draw = ImageDraw.Draw(image)
    for _ in range(7):
        draw.line(
            (
                secrets.randbelow(170),
                secrets.randbelow(54),
                secrets.randbelow(170),
                secrets.randbelow(54),
            ),
            fill=(160 + secrets.randbelow(60), 150 + secrets.randbelow(70), 150 + secrets.randbelow(70)),
            width=1,
        )
    for _ in range(90):
        x, y = secrets.randbelow(170), secrets.randbelow(54)
        draw.point((x, y), fill=(110 + secrets.randbelow(120),) * 3)

    font_path = Path(__file__).resolve().parents[2] / "fonts" / "arial.ttf"
    try:
        font = ImageFont.truetype(str(font_path), 30)
    except OSError:
        font = ImageFont.load_default()
    for index, char in enumerate(answer):
        x = 17 + index * 29 + secrets.randbelow(5)
        y = 8 + secrets.randbelow(8)
        draw.text(
            (x, y),
            char,
            font=font,
            fill=(25 + secrets.randbelow(60), 25 + secrets.randbelow(60), 25 + secrets.randbelow(60)),
        )

    buffer = io.BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    with account_db() as connection:
        connection.execute(
            """
            INSERT INTO auth_captchas(captcha_id, answer_hash, expires_at, attempts, created_at)
            VALUES (?, ?, ?, 0, ?)
            """,
            (captcha_id, answer_hash, now + 300, now),
        )
        connection.execute("DELETE FROM auth_captchas WHERE expires_at < ?", (now,))

    return {
        "captcha_id": captcha_id,
        "image": "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode(),
        "expires_in": 300,
    }


def verify_captcha(captcha_id: str, captcha_code: str) -> None:
    now = int(time.time())
    with account_db() as connection:
        row = connection.execute(
            """
            SELECT answer_hash, expires_at, attempts
            FROM auth_captchas WHERE captcha_id = ?
            """,
            (captcha_id,),
        ).fetchone()
        if not row or row["expires_at"] < now or row["attempts"] >= 5:
            connection.execute("DELETE FROM auth_captchas WHERE captcha_id = ?", (captcha_id,))
            raise HTTPException(status_code=400, detail="验证码已失效，请刷新")

        actual = hashlib.sha256(
            f"{captcha_id}:{captcha_code.strip().upper()}".encode()
        ).hexdigest()
        connection.execute(
            "UPDATE auth_captchas SET attempts = attempts + 1 WHERE captcha_id = ?",
            (captcha_id,),
        )
        if not hmac.compare_digest(actual, row["answer_hash"]):
            raise HTTPException(status_code=400, detail="图形验证码错误")
        connection.execute("DELETE FROM auth_captchas WHERE captcha_id = ?", (captcha_id,))


def register_user(
    username: str,
    password: str,
    email: str,
    phone: Optional[str],
    captcha_id: str,
    captcha_code: str,
) -> dict:
    verify_captcha(captcha_id, captcha_code)
    username, username_key = normalize_username(username)
    email, email_key = normalize_email(email)
    phone = normalize_phone(phone)
    salt = secrets.token_bytes(16)
    now = int(time.time())
    try:
        with account_db() as connection:
            cursor = connection.execute(
                """
                INSERT INTO accounts(
                    username, username_key, password_salt, password_hash,
                    email, email_key, phone, role, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 'free', ?)
                """,
                (
                    username,
                    username_key,
                    salt.hex(),
                    password_hash(password, salt),
                    email,
                    email_key,
                    phone,
                    now,
                ),
            )
            token = issue_session(connection, cursor.lastrowid)
            account = connection.execute(
                "SELECT * FROM accounts WHERE id = ?",
                (cursor.lastrowid,),
            ).fetchone()
            return {"token": token, "user": public_user(connection, account)}
    except sqlite3.IntegrityError as error:
        message = "邮箱已被注册" if "email" in str(error).lower() else "该账号已存在"
        raise HTTPException(status_code=409, detail=message)


def login_user(username: str, password: str) -> dict:
    _, username_key = normalize_username(username)
    with account_db() as connection:
        row = connection.execute(
            "SELECT * FROM accounts WHERE username_key = ?",
            (username_key,),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=401, detail="账号或密码错误")
        actual = password_hash(password, bytes.fromhex(row["password_salt"]))
        if not hmac.compare_digest(actual, row["password_hash"]):
            raise HTTPException(status_code=401, detail="账号或密码错误")
        token = issue_session(connection, row["id"])
        return {"token": token, "user": public_user(connection, row)}


def account_quota(account: dict) -> dict:
    with account_db() as connection:
        return _quota_payload(connection, account)


def consume_generation_quota(
    request: Request,
    authorization: Optional[str],
) -> dict:
    account = optional_account(authorization)
    now = int(time.time())
    with account_db() as connection:
        if account:
            role = account["role"] if account["role"] in ROLE_LIMITS else "free"
            limit = ROLE_LIMITS[role]
            period_key = datetime.now(ZoneInfo("Asia/Shanghai")).strftime("%Y-%m-%d")
            subject_type = "account"
            subject_key = str(account["id"])
        else:
            role = "guest"
            limit = 5
            period_key = "lifetime"
            forwarded = (
                request.headers.get("cf-connecting-ip")
                or (request.client.host if request.client else "unknown")
            )
            subject_type = "guest"
            subject_key = hashlib.sha256(forwarded.encode()).hexdigest()

        connection.execute("BEGIN IMMEDIATE")
        row = connection.execute(
            """
            SELECT count FROM generation_usage
            WHERE subject_type = ? AND subject_key = ? AND period_key = ?
            """,
            (subject_type, subject_key, period_key),
        ).fetchone()
        used = int(row["count"]) if row else 0
        if limit is not None and used >= limit:
            if role == "guest":
                detail = "未登录用户最多可生成 5 篇笔记，请注册或登录后继续"
            else:
                detail = f"{ROLE_LABELS[role]}今日生成额度已用完（{limit} 篇）"
            raise HTTPException(
                status_code=429,
                detail=detail,
                headers={"Retry-After": "86400" if period_key != "lifetime" else "0"},
            )
        connection.execute(
            """
            INSERT INTO generation_usage(subject_type, subject_key, period_key, count, updated_at)
            VALUES (?, ?, ?, 1, ?)
            ON CONFLICT(subject_type, subject_key, period_key)
            DO UPDATE SET count = generation_usage.count + 1, updated_at = excluded.updated_at
            """,
            (subject_type, subject_key, period_key, now),
        )
        used += 1
        return {
            "role": role,
            "role_label": ROLE_LABELS.get(role, "未登录用户"),
            "limit": limit,
            "used": used,
            "remaining": None if limit is None else max(limit - used, 0),
            "period": "lifetime" if role == "guest" else "day",
            "period_key": period_key,
        }
