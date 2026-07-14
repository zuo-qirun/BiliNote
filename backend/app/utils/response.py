from fastapi.responses import JSONResponse
from app.utils.api_error_diagnosis import diagnose_api_error


class ResponseWrapper:
    @staticmethod
    def success(data=None, msg="success", code=0):
        return JSONResponse(content={
            "code": code,
            "msg": msg,
            "data": data
        })

    @staticmethod
    def error(msg="error", code=500, data=None):
        payload = dict(data) if isinstance(data, dict) else {}
        if "error_detail" not in payload:
            payload["error_detail"] = diagnose_api_error(msg, code)
        return JSONResponse(content={
            "code": code,
            "msg": str(msg),
            "data": payload
        })
