"""Turn low-level task failures into safe, actionable diagnostics for the UI."""

from __future__ import annotations

import re
from typing import Any


def _clean_message(message: Any) -> str:
    raw = str(message or "").strip() or "任务执行失败，后端未返回具体错误。"
    # Avoid accidentally returning credentials embedded in an upstream exception.
    raw = re.sub(
        r"(?i)(api[-_ ]?key|authorization|token|secret)(\s*[:=]\s*)([^\s,;]+)",
        r"\1\2[已隐藏]",
        raw,
    )
    raw = re.sub(r"(?i)bearer\s+[a-z0-9._~+\-/]+=*", "Bearer [已隐藏]", raw)
    return raw[:2000]


def diagnose_task_error(message: Any, *, stage: str = "unknown") -> dict[str, Any]:
    """Return a stable error payload that the web and extension clients can render."""
    technical_message = _clean_message(message)
    normalized = technical_message.lower()

    diagnosis: dict[str, Any] = {
        "code": "TASK_EXECUTION_FAILED",
        "title": "任务执行失败",
        "summary": "任务在处理过程中遇到异常，暂时无法完成笔记生成。",
        "stage": stage,
        "retryable": True,
        "possible_causes": [
            "上游服务临时异常或网络连接中断",
            "当前模型、转写器或视频源返回了非预期结果",
        ],
        "suggestions": [
            "稍后重试当前任务",
            "若持续失败，请复制技术信息并交给管理员排查",
        ],
        "technical_message": technical_message,
    }

    if "your request was blocked" in normalized or (
        "403" in normalized and any(token in normalized for token in ("blocked", "forbidden", "permission"))
    ):
        diagnosis.update(
            code="AI_PROVIDER_BLOCKED",
            title="AI 服务拒绝了请求",
            summary="视频解析和转写可能已经完成，但 AI 模型供应商返回了 403 拒绝访问。",
            stage="summarizing",
            retryable=False,
            possible_causes=[
                "API Key 已失效、被冻结，或没有所选模型的调用权限",
                "第三方代理限制了服务器 IP、地区、账户或请求来源",
                "代理服务的风控、防火墙或内容策略拦截了请求",
                "供应商账户余额、套餐或并发权限异常",
            ],
            suggestions=[
                "在模型设置中测试当前供应商连接",
                "检查 API Key、账户状态和所选模型权限",
                "更换可用的 API 地址、Key 或模型供应商后重试",
                "如果使用第三方代理，请联系代理服务商查询 403 拦截记录",
            ],
        )
    elif any(token in normalized for token in ("401", "invalid api key", "incorrect api key", "authentication")):
        diagnosis.update(
            code="AI_AUTHENTICATION_FAILED",
            title="AI 服务身份验证失败",
            summary="当前 API Key 无效或未被供应商接受。",
            stage="summarizing",
            retryable=False,
            possible_causes=["API Key 填写错误、过期或已被撤销", "API 地址与 API Key 不属于同一供应商"],
            suggestions=["重新填写并测试 API Key", "核对供应商 API 地址后再重试"],
        )
    elif any(token in normalized for token in ("429", "rate limit", "insufficient quota", "insufficient_user_quota", "额度")):
        diagnosis.update(
            code="AI_QUOTA_OR_RATE_LIMIT",
            title="AI 服务额度或频率受限",
            summary="供应商暂时拒绝继续处理请求，通常与余额、额度或请求频率有关。",
            stage="summarizing",
            possible_causes=["API 账户余额或调用额度不足", "短时间请求过多，触发并发或频率限制"],
            suggestions=["检查供应商余额和用量", "等待几分钟后重试，或切换其他模型供应商"],
        )
    elif any(token in normalized for token in ("context length", "maximum context", "request too large", "payload too large", "413")):
        diagnosis.update(
            code="AI_INPUT_TOO_LARGE",
            title="输入内容超过模型限制",
            summary="转写文本或多模态图片过多，超过了当前模型或代理允许的请求大小。",
            stage="summarizing",
            possible_causes=["视频较长，转写文本超过上下文窗口", "开启多模态后图片数量或请求体积过大"],
            suggestions=["关闭多模态理解后重试", "改用上下文更大的模型，或缩短视频范围"],
        )
    elif any(token in normalized for token in ("content filter", "content policy", "safety", "moderation")):
        diagnosis.update(
            code="AI_CONTENT_FILTERED",
            title="内容被供应商安全策略拦截",
            summary="AI 供应商判定部分输入不符合其内容政策。",
            stage="summarizing",
            retryable=False,
            possible_causes=["视频转写或画面触发了模型安全过滤", "第三方代理使用了额外的内容审核规则"],
            suggestions=["关闭多模态理解后重试", "更换符合该内容场景的模型供应商"],
        )
    elif any(token in normalized for token in ("model_not_found", "model not found", "does not exist", "unknown model")):
        diagnosis.update(
            code="AI_MODEL_UNAVAILABLE",
            title="所选 AI 模型不可用",
            summary="供应商找不到所选模型，或当前账户没有访问权限。",
            stage="summarizing",
            retryable=False,
            possible_causes=["模型名称填写错误或已下线", "当前 API Key 没有该模型权限"],
            suggestions=["刷新模型列表并选择可用模型", "在模型设置中测试供应商连接"],
        )
    elif any(token in normalized for token in ("timeout", "timed out", "504", "524", "connection error")):
        diagnosis.update(
            code="UPSTREAM_TIMEOUT",
            title="上游服务响应超时",
            summary="下载、转写或 AI 服务未能在规定时间内响应。",
            possible_causes=["上游服务繁忙或网络波动", "视频较长，处理耗时超过代理限制"],
            suggestions=["稍后重试，系统会复用已保存的阶段缓存", "持续出现时切换其他转写器或模型供应商"],
        )
    elif any(token in normalized for token in ("download", "下载", "unsupported url", "video unavailable")):
        diagnosis.update(
            code="VIDEO_DOWNLOAD_FAILED",
            title="视频或音频下载失败",
            summary="系统无法从视频平台取得生成笔记所需的媒体内容。",
            stage="downloading",
            possible_causes=["视频已删除、设为私密或存在地区限制", "平台登录状态过期或触发访问风控"],
            suggestions=["确认视频可在浏览器中正常播放", "更新平台 Cookie，或稍后重试"],
        )
    elif any(token in normalized for token in ("transcrib", "转写", "subtitle", "字幕")):
        diagnosis.update(
            code="TRANSCRIPTION_FAILED",
            title="音频转写失败",
            summary="媒体已取得，但转写服务未能生成有效文本。",
            stage="transcribing",
            possible_causes=["主转写器暂时不可用", "音频格式、时长或语言不受当前转写器支持"],
            suggestions=["重试以启用备用转写器", "在设置中切换转写器后再次生成"],
        )

    return diagnosis

