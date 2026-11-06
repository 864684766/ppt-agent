"""将请求/文件/读取失败映射到HTTP；领域异常不包含HTTP状态码。"""

from fastapi import HTTPException


def chat_http_error(code: str, message: str) -> HTTPException:
    """只使用已选择的安全字段，禁止把解析器异常或原始输入直接交给此方法。"""
    status = 400
    if code in {"file_too_large", "archive_limit_exceeded", "document_limit_exceeded"}:
        status = 413
    elif code in {"unsupported_media_type", "unsupported_format", "content_type_mismatch"}:
        status = 415
    elif code in {"invalid_fields", "invalid_message"}:
        status = 422
    elif code == "configuration_invalid":
        status = 503
    return HTTPException(status, detail={"code": code, "message": message})
