# middlewares/exception_handler.py

from fastapi import Request, HTTPException
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError

from app.enmus.exception import NoteErrorEnum
from app.exceptions.biz_exception import BizException
from app.exceptions.note import NoteError
from app.exceptions.provider import ProviderError
from app.utils.logger import get_logger
from app.utils.response import ResponseWrapper as R
import traceback

logger = get_logger(__name__)

def register_exception_handlers(app: FastAPI):
    @app.exception_handler(BizException)
    async def biz_exception_handler(request: Request, exc: BizException):
        logger.error(f"BizException: {exc.code} - {exc.message}")
        return R.error(code=exc.code, msg=str(exc.message))
    @app.exception_handler(NoteError)
    async def note_exception_handler(request: Request, exc: NoteError):
        logger.error(f"NoteError: {exc.code} - {exc.message}")
        return R.error(code=exc.code, msg=str(exc.message))
    @app.exception_handler(ProviderError)
    async def provider_exception_handler(request: Request, exc: ProviderError):
        logger.error(f"供应商模块错误: {exc.code} - {exc.message}")
        return R.error(code=exc.code, msg=str(exc.message))

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        return R.error(code=exc.status_code, msg=str(exc.detail))

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        first = exc.errors()[0] if exc.errors() else {}
        location = ".".join(str(item) for item in first.get("loc", []) if item != "body")
        reason = first.get("msg", "输入格式不正确")
        message = f"参数 {location}：{reason}" if location else reason
        return R.error(code=422, msg=message)

    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        logger.error(f"系统异常: {str(exc)}\n{traceback.format_exc()}")
        return R.error(code=500000, msg="系统内部异常，请稍后重试")
