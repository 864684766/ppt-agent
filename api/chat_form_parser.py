"""限制multipart读取规模，并负责已解析上传资源的生命周期。"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from anyio import CancelScope
from starlette.datastructures import FormData
from starlette.formparsers import MultiPartException, MultiPartParser
from starlette.requests import Request

from domain.uploads.file_upload_errors import FileUploadError


# multipart包含边界和字段头，不能直接把整个请求的上限等同于文件大小。
_MULTIPART_OVERHEAD_BYTES = 64 * 1024


@asynccontextmanager
async def open_chat_form(request: Request, *, max_file_bytes: int) -> AsyncIterator[FormData]:
    """接收最多一个附件、message/template_key两个普通字段；退出时释放上传资源。

    使用当前锁定Starlette的公开MultiPartParser接口，其parse会在BaseException
    （包含断连和取消）时关闭解析中创建的临时文件；成功后由本上下文关闭FormData。
    框架可能把大文件缓冲到系统临时目录，因此不承诺整个请求零落盘。
    """
    media_type = request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
    if media_type != "multipart/form-data":
        raise FileUploadError("unsupported_media_type", "附件请求请使用multipart/form-data，提供message、可选file和可选template_key。")
    request_limit = max_file_bytes + _MULTIPART_OVERHEAD_BYTES
    declared_length = request.headers.get("content-length")
    if declared_length is not None:
        try:
            size = int(declared_length)
        except ValueError:
            raise FileUploadError("invalid_multipart", "Content-Length格式无效。") from None
        if size < 0:
            raise FileUploadError("invalid_multipart", "Content-Length不能为负数。")
        if size > request_limit:
            raise FileUploadError("file_too_large", "上传请求超过文件大小加64 KiB表单开销的上限。")

    async def bounded_stream() -> AsyncIterator[bytes]:
        # 即使没有或伪造Content-Length，也按实际收到的字节累计检查。
        received = 0
        async for chunk in request.stream():
            received += len(chunk)
            if received > request_limit:
                raise FileUploadError("file_too_large", "上传请求实际字节数超过允许上限。")
            yield chunk

    parser = MultiPartParser(
        headers=request.headers, stream=bounded_stream(),
        max_files=1, max_fields=2, max_part_size=40000,
    )
    try:
        form = await parser.parse()
    except MultiPartException:
        raise FileUploadError("invalid_multipart", "表单不可读取或超出字段/文件限制；仅接受message、单个file和template_key。") from None
    try:
        yield form
    finally:
        # 即使外层请求已取消，也尽量完成临时文件关闭；这不是吞掉业务取消信号。
        with CancelScope(shield=True):
            await form.close()
