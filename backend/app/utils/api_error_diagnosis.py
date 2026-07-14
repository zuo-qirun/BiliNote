"""Consistent, safe diagnostics for every API error response."""

from __future__ import annotations

import re
from typing import Any


def _clean(value: Any) -> str:
    text = str(value or "操作失败").strip()
    text = re.sub(
        r"(?i)(api[-_ ]?key|authorization|token|secret|password)(\s*[:=]\s*)([^\s,;]+)",
        r"\1\2[已隐藏]",
        text,
    )
    text = re.sub(r"(?i)bearer\s+[a-z0-9._~+\-/]+=*", "Bearer [已隐藏]", text)
    return text[:2000]


def diagnose_api_error(message: Any, code: Any = 500) -> dict[str, Any]:
    technical = _clean(message)
    raw = technical.lower()
    try:
        status = int(code)
    except (TypeError, ValueError):
        status = 500

    result: dict[str, Any] = {
        "code": "API-SYS-500",
        "title": "服务处理失败",
        "summary": technical if technical != "操作失败" else "服务器未能完成本次操作。",
        "possible_causes": ["服务内部出现未预期异常", "依赖的数据库或上游服务暂时不可用"],
        "suggestions": ["稍后重试一次", "若持续出现，请复制错误代码和技术信息交给管理员"],
        "retryable": True,
        "technical_message": technical,
    }

    if "验证码" in technical:
        result.update(code="API-AUTH-CAPTCHA", title="验证码校验失败", summary=technical,
            possible_causes=["验证码输入错误", "验证码已过期或已被使用"],
            suggestions=["刷新验证码后重新输入", "确认字母与数字没有混淆"], retryable=False)
    elif any(token in technical for token in ("账号或密码", "登录状态", "请先登录", "登录已过期")) or status == 401:
        result.update(code="API-AUTH-401", title="身份验证失败", summary=technical,
            possible_causes=["账号或密码不正确", "登录凭证已过期或在其他设备被注销"],
            suggestions=["重新登录后再试", "若忘记凭据，请联系管理员处理"], retryable=False)
    elif "管理员" in technical or status == 403:
        result.update(code="API-AUTH-403", title="当前账号没有操作权限", summary=technical,
            possible_causes=["当前账号角色权限不足", "该功能仅允许管理员修改"],
            suggestions=["切换到具备权限的账号", "联系管理员完成此操作"], retryable=False)
    elif "配额" in technical or "额度" in technical or "quota" in raw or status == 429:
        result.update(code="API-LIMIT-429", title="生成额度或请求频率已受限", summary=technical,
            possible_causes=["今日生成次数已用完", "短时间请求过多触发限流", "上游模型账户余额不足"],
            suggestions=["等待额度刷新后重试", "特权用户或管理员可检查账户与供应商额度"])
    elif "上传" in technical or "文件格式" in technical or status == 413:
        result.update(code="API-UPLOAD-413" if status == 413 else "API-UPLOAD-400", title="文件上传失败", summary=technical,
            possible_causes=["文件格式或大小不符合要求", "上传期间网络中断", "服务器磁盘空间不足"],
            suggestions=["确认文件为常见视频格式", "保持页面打开并重新上传", "大文件可检查网络稳定性"])
    elif "分享" in technical:
        result.update(code="API-SHARE-404" if status == 404 else "API-SHARE-500", title="分享笔记不可用", summary=technical,
            possible_causes=["分享链接不完整或已失效", "分享文件已被移除", "服务器读取分享内容失败"],
            suggestions=["检查分享链接是否完整", "让分享者重新生成链接"], retryable=status >= 500)
    elif any(token in technical for token in ("模型", "供应商", "API Key", "Base URL", "连接失败")):
        result.update(code="API-MODEL-CONFIG", title="模型供应商配置不可用", summary=technical,
            possible_causes=["API Key、Base URL 或模型名称填写错误", "供应商接口不可达或账户没有模型权限"],
            suggestions=["在模型设置中执行连接测试", "核对 API 地址、Key 和模型名称"])
    elif "转写" in technical or "whisper" in raw or "字幕" in technical:
        result.update(code="API-TRANSCRIBE-FAILED", title="音频转写服务不可用", summary=technical,
            possible_causes=["转写器配置错误或服务暂时不可达", "本地模型尚未下载完成"],
            suggestions=["检查转写设置与模型下载状态", "切换备用转写器后重试"])
    elif status in {400, 422} or "无效" in technical or "请填写" in technical:
        result.update(code="API-VALID-422" if status == 422 else "API-VALID-400", title="提交的数据不符合要求", summary=technical,
            possible_causes=["必填字段缺失", "链接、参数或数据格式不正确"],
            suggestions=["根据页面提示检查输入内容", "修正后重新提交"], retryable=False)
    elif status == 404 or "不存在" in technical or "未找到" in technical:
        result.update(code="API-NOT-404", title="请求的内容不存在", summary=technical,
            possible_causes=["内容已被删除", "链接或任务 ID 不完整"],
            suggestions=["刷新页面后重试", "返回上一页重新选择内容"], retryable=False)
    elif status == 409 or "已存在" in technical:
        result.update(code="API-CONFLICT-409", title="数据发生冲突", summary=technical,
            possible_causes=["名称或记录已经存在", "数据已被其他设备修改"],
            suggestions=["刷新数据后重试", "使用其他名称或保留较新的版本"], retryable=False)
    elif status in {502, 503, 504} or any(token in raw for token in ("timeout", "timed out", "connection error")):
        upstream_status = status if status in {502, 503, 504} else 504
        result.update(code=f"API-UPSTREAM-{upstream_status}", title="上游服务暂时不可用", summary=technical,
            possible_causes=["模型、转写或视频平台响应超时", "服务器到上游服务的网络波动"],
            suggestions=["稍后重试", "持续失败时切换供应商或转写器"])

    return result

