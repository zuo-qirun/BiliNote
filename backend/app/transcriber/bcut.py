import json
import os
import time
from typing import List

import requests

from app.decorators.timeit import timeit
from app.models.transcriber_model import TranscriptSegment, TranscriptResult
from app.transcriber.base import Transcriber
from app.utils.logger import get_logger
from events import transcription_finished

__version__ = "0.0.3"

API_BASE_URL = "https://member.bilibili.com/x/bcut/rubick-interface"

# 申请上传
API_REQ_UPLOAD = API_BASE_URL + "/resource/create"

# 提交上传
API_COMMIT_UPLOAD = API_BASE_URL + "/resource/create/complete"

# 创建任务
API_CREATE_TASK = API_BASE_URL + "/task"

# 查询结果
API_QUERY_RESULT = API_BASE_URL + "/task/result"

logger = get_logger(__name__)


class BcutTranscriber(Transcriber):
    """必剪 语音识别接口"""
    headers = {
        'User-Agent': 'Bilibili/1.0.0 (https://www.bilibili.com)',
        'Content-Type': 'application/json'
    }

    def __init__(self):
        self.commit_max_attempts = max(
            1,
            int(os.getenv("BCUT_COMMIT_MAX_ATTEMPTS", "3")),
        )
        self.commit_retry_base_seconds = max(
            0.0,
            float(os.getenv("BCUT_COMMIT_RETRY_BASE_SECONDS", "1")),
        )
        
    def _load_file(self, file_path: str) -> bytes:
        """读取文件内容"""
        with open(file_path, 'rb') as f:
            return f.read()

    def _upload(self, file_path: str, session: requests.Session) -> str:
        """申请上传"""
        file_binary = self._load_file(file_path)
        if not file_binary:
            raise ValueError("无法读取文件数据")
            
        payload = json.dumps({
            "type": 2,
            "name": "audio.mp3",
            "size": len(file_binary),
            "ResourceFileType": "mp3",
            "model_id": "8",
        })

        resp = session.post(
            API_REQ_UPLOAD,
            data=payload,
            headers=self.headers,
            timeout=30,
        )
        resp.raise_for_status()
        resp = resp.json()
        resp_data = resp["data"]

        in_boss_key = resp_data["in_boss_key"]
        resource_id = resp_data["resource_id"]
        upload_id = resp_data["upload_id"]
        upload_urls = resp_data["upload_urls"]
        per_size = resp_data["per_size"]

        logger.info(
            f"申请上传成功, 总计大小{resp_data['size'] // 1024}KB, {len(upload_urls)}分片, 分片大小{per_size // 1024}KB: {in_boss_key}"
        )
        etags = self.__upload_part(
            session=session,
            file_binary=file_binary,
            upload_urls=upload_urls,
            per_size=per_size,
        )
        return self.__commit_upload(
            session=session,
            in_boss_key=in_boss_key,
            resource_id=resource_id,
            upload_id=upload_id,
            etags=etags,
        )

    def __upload_part(
        self,
        session: requests.Session,
        file_binary: bytes,
        upload_urls: List[str],
        per_size: int,
    ) -> List[str]:
        """上传音频数据"""
        etags: List[str] = []
        for clip, upload_url in enumerate(upload_urls):
            start_range = clip * per_size
            end_range = min((clip + 1) * per_size, len(file_binary))
            logger.info(f"开始上传分片{clip}: {start_range}-{end_range}")
            resp = session.put(
                upload_url,
                data=file_binary[start_range:end_range],
                headers={'Content-Type': 'application/octet-stream'},
                timeout=120,
            )
            resp.raise_for_status()
            etag = resp.headers.get("Etag", "").strip('"')
            if not etag:
                raise RuntimeError(f"分片{clip}上传成功但未返回 ETag")
            etags.append(etag)
            logger.info(f"分片{clip}上传成功: {etag}")
        return etags

    def __commit_upload(
        self,
        session: requests.Session,
        in_boss_key: str,
        resource_id: str,
        upload_id: str,
        etags: List[str],
    ) -> str:
        """提交上传数据"""
        data = json.dumps({
            "InBossKey": in_boss_key,
            "ResourceId": resource_id,
            "Etags": ",".join(etags),
            "UploadId": upload_id,
            "model_id": "8",
        })

        for attempt in range(1, self.commit_max_attempts + 1):
            try:
                response = session.post(
                    API_COMMIT_UPLOAD,
                    data=data,
                    headers=self.headers,
                    timeout=30,
                )
                response.raise_for_status()
                response_data = response.json()
                code = response_data.get("code")
                if code == 0:
                    download_url = response_data["data"]["download_url"]
                    logger.info("上传提交成功")
                    return download_url

                error_msg = response_data.get("message", "未知错误")
                if code != 139201:
                    raise RuntimeError(f"上传提交失败: {error_msg} (code={code})")
                failure = RuntimeError(
                    f"上传提交失败: {error_msg} (code={code})"
                )
            except (requests.RequestException, ValueError, KeyError) as exc:
                failure = exc

            if attempt >= self.commit_max_attempts:
                logger.error(
                    "上传提交在 %s 次尝试后仍失败: %s",
                    attempt,
                    failure,
                )
                raise RuntimeError(
                    f"上传提交失败，已重试 {attempt} 次: {failure}"
                ) from failure

            delay = self.commit_retry_base_seconds * (2 ** (attempt - 1))
            logger.warning(
                "上传提交第 %s/%s 次失败: %s；%.1f 秒后重试",
                attempt,
                self.commit_max_attempts,
                failure,
                delay,
            )
            time.sleep(delay)

        raise RuntimeError("上传提交失败")

    def _create_task(
        self,
        session: requests.Session,
        download_url: str,
    ) -> str:
        """开始创建转换任务"""
        resp = session.post(
            API_CREATE_TASK,
            json={"resource": download_url, "model_id": "8"},
            headers=self.headers,
            timeout=30,
        )
        resp.raise_for_status()
        resp = resp.json()
        if resp.get("code") != 0:
            error_msg = f"创建任务失败: {resp.get('message', '未知错误')}"
            logger.error(error_msg)
            raise Exception(error_msg)
            
        task_id = resp["data"]["task_id"]
        logger.info(f"任务已创建: {task_id}")
        return task_id

    def _query_result(
        self,
        session: requests.Session,
        task_id: str,
    ) -> dict:
        """查询转换结果"""
        resp = session.get(
            API_QUERY_RESULT, 
            params={"model_id": 7, "task_id": task_id},
            headers=self.headers,
            timeout=30,
        )
        resp.raise_for_status()
        resp = resp.json()
        if resp.get("code") != 0:
            error_msg = f"查询结果失败: {resp.get('message', '未知错误')}"
            logger.error(error_msg)
            raise Exception(error_msg)
            
        return resp["data"]

    @timeit
    def transcript(self, file_path: str) -> TranscriptResult:
        """执行识别过程，符合 Transcriber 接口"""
        try:
            logger.info(f"开始处理文件: {file_path}")
            session = requests.Session()
            
            # 上传文件
            logger.info("正在上传文件...")
            download_url = self._upload(file_path, session)
            
            # 创建任务
            logger.info("提交转录任务...")
            task_id = self._create_task(session, download_url)
            
            # 轮询检查任务状态
            logger.info("等待转录结果...")
            task_resp = None
            max_retries = 500
            for i in range(max_retries):
                task_resp = self._query_result(session, task_id)
                
                if task_resp["state"] == 4:  # 完成状态
                    break
                elif task_resp["state"] == 3:  # 失败状态
                    error_msg = f"B站ASR任务失败，状态码: {task_resp['state']}"
                    logger.error(error_msg)
                    raise Exception(error_msg)
                    
                # 每隔一段时间打印进度
                if i % 10 == 0:
                    logger.info(f"转录进行中... {i}/{max_retries}")
                    
                time.sleep(1)
                
            if not task_resp or task_resp["state"] != 4:
                error_msg = f"B站ASR任务未能完成，状态: {task_resp.get('state') if task_resp else 'Unknown'}"
                logger.error(error_msg)
                raise Exception(error_msg)
                
            # 解析结果
            logger.info("转录成功，处理结果...")
            result_json = json.loads(task_resp["result"])
            
            # 提取分段数据
            segments = []
            full_text = ""
            
            for u in result_json.get("utterances", []):
                text = u.get("transcript", "").strip()
                # B站ASR返回的时间戳是毫秒，需要转换为秒
                start_time = float(u.get("start_time", 0)) / 1000.0
                end_time = float(u.get("end_time", 0)) / 1000.0
                
                full_text += text + " "
                segments.append(TranscriptSegment(
                    start=start_time,
                    end=end_time,
                    text=text
                ))

            if not full_text.strip():
                raise RuntimeError(
                    "B站ASR任务已完成，但未返回可用文字；"
                    "这通常是源音频无语音、静音或上游识别结果为空"
                )
            
            # 创建结果对象
            result = TranscriptResult(
                language=result_json.get("language", "zh"),
                full_text=full_text.strip(),
                segments=segments,
                raw=result_json
            )
            
            # 触发完成事件
            # self.on_finish(file_path, result)
            
            return result
            
        except Exception as e:
            logger.error(f"B站ASR处理失败: {str(e)}")
            raise

    def on_finish(self, video_path: str, result: TranscriptResult) -> None:
        """转录完成的回调"""
        logger.info(f"B站ASR转写完成: {video_path}")
        transcription_finished.send({
            "file_path": video_path,
        })
