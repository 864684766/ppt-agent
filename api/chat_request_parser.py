"""把JSON消息或multipart问题附件解析成统一内部输入；在这里关闭上传句柄。"""

import json
import logging

from fastapi import Request
from pydantic import ValidationError
from starlette.datastructures import UploadFile

from api.chat_error_mapping import chat_http_error
from api.chat_form_parser import open_chat_form
from config.settings import Settings
from diagnostics.operation_logging import log_operation
from domain.uploads.file_upload_errors import FileUploadError
from domain.uploads.file_upload_validation import validate_upload_metadata
from models.chat.chat_request import ChatAttachmentInput, ChatRequest, ChatSubmission


logger = logging.getLogger(__name__)


@log_operation("chat.parse_request")
async def get_chat_submission(request: Request) -> ChatSubmission:
    """将两种HTTP请求转换成内部输入，上传句柄在退出表单时关闭。

    JSON接受message和可选template_key；multipart再允许可选file。文件字节
    拷贝到本请求后关闭表单句柄，不在API层缓存供以后查询。
    """
    try:
        media_type = request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
        if media_type == "application/json":
            body = bytearray()
            async for chunk in request.stream():
                body.extend(chunk)
                if len(body) > 64 * 1024:
                    raise FileUploadError("file_too_large", "JSON消息请求超过64 KiB，请勿把文件正文或base64塞入消息。")
            try:
                parameters = ChatRequest.model_validate(json.loads(body))
            except (ValueError, UnicodeError, ValidationError):
                raise FileUploadError("invalid_message", "JSON需要1–10000字符的非空message，可选template_key（最多1024字符）。") from None
            return ChatSubmission(**parameters.model_dump())
        if media_type != "multipart/form-data":
            raise FileUploadError("unsupported_media_type", "请发送application/json消息，或multipart/form-data问题与附件。")
        try:
            settings = Settings()
        except ValidationError:
            raise FileUploadError("configuration_invalid", "附件配置无效，请检查环境变量。") from None
        async with open_chat_form(request, max_file_bytes=settings.upload_max_file_bytes) as form:
            items = form.multi_items()
            names = [name for name, _ in items]
            if len(names) != len(set(names)) or "message" not in names or not set(names) <= {"message", "file", "template_key"}:
                raise FileUploadError("invalid_fields", "仅接受message、可选file和可选template_key，不能有重复或其他字段。")
            try:
                parameters = ChatRequest.model_validate({
                    "message": form["message"], "template_key": form.get("template_key"),
                })
            except ValidationError:
                raise FileUploadError("invalid_message", "message必须为1–10000字符的非空文本；template_key须为最多1024字符的文本。") from None
            if "file" not in form:
                return ChatSubmission(**parameters.model_dump())
            upload = form["file"]
            if not isinstance(upload, UploadFile):
                raise FileUploadError("invalid_fields", "file必须为文件类型，不能是文本路径。")
            name, file_format = validate_upload_metadata(file_name=upload.filename, content_type=upload.content_type)
            content = await _read_attachment_bytes(upload, max_file_bytes=settings.upload_max_file_bytes)
            # 退出open_chat_form前已把字节读到本请求的内存对象，
            # 后续解析不再依赖已关闭的UploadFile临时句柄。
            return ChatSubmission(
                **parameters.model_dump(),
                attachment=ChatAttachmentInput(
                    file_name=name,
                    format=file_format, content=content,
                ),
            )
    except FileUploadError as error:
        logger.warning("event=chat_request_rejected code=%s", error.code)
        raise chat_http_error(error.code, str(error)) from None


async def _read_attachment_bytes(upload: UploadFile, *, max_file_bytes: int) -> bytes:
    """累计检查实际文件字节，不相信单个声明；关闭责任归open_chat_form。"""
    if upload.size is not None and upload.size > max_file_bytes:
        raise FileUploadError("file_too_large", "附件超过UPLOAD_MAX_FILE_BYTES限制。")
    chunks = []
    total = 0
    while chunk := await upload.read(64 * 1024):
        total += len(chunk)
        if total > max_file_bytes:
            raise FileUploadError("file_too_large", "附件实际字节数超过配置上限。")
        chunks.append(chunk)
    return b"".join(chunks)
