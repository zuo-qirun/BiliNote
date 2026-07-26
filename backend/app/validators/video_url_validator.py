from pydantic import AnyUrl, validator, BaseModel, field_validator
import re
from urllib.parse import urlparse

SUPPORTED_PLATFORMS = {
    "youtube": r"(https?://)?(www\.)?(youtube\.com/(watch\?v=|shorts/)|youtu\.be/)[\w\-]+",
    "douyin": "douyin",
    "kuaishou": "kuaishou"
}


def is_supported_video_url(url: str) -> bool:
    parsed = urlparse(url)
    hostname = (parsed.hostname or "").lower()

    # 检查是否为Bilibili的短链接
    if hostname in {"b23.tv", "www.b23.tv"}:
        return True

    # 兼容 www、m 等 B 站子域，且与浏览器扩展的识别规则保持一致。
    if (
        (hostname == "bilibili.com" or hostname.endswith(".bilibili.com"))
        and re.match(r"^/video/(?:BV[0-9A-Za-z]+|av\d+)", parsed.path, re.IGNORECASE)
    ):
        return True

    for name, pattern in SUPPORTED_PLATFORMS.items():
        if pattern in ["douyin", "kuaishou"]:
            if pattern in url:
                return True
        else:
            if re.match(pattern, url):
                return True
    return False


class VideoRequest(BaseModel):
    url: AnyUrl
    platform: str

    @field_validator("url")
    def validate_video_url(cls, v):
        if not is_supported_video_url(str(v)):
            raise ValueError("暂不支持该视频平台或链接格式无效")
        return v
