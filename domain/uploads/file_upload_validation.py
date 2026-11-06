"""检查文件名、声明类型和实际文件特征，不保存文件或调用模型。"""

from domain.uploads.file_upload_errors import FileUploadError
from domain.uploads.office_package_validation import validate_office_package
from domain.documents.text_decoding import decode_document_text


# 格式列表与MIME策略集中维护；新增格式需要先落实对应校验/读取能力。
_SUPPORTED_FORMATS = {"txt", "md", "pdf", "docx", "xlsx", "pptx"}
_FORMAT_MIME_TYPES = {
    "txt": {"text/plain"},
    "md": {"text/markdown", "text/plain", "text/x-markdown"},
    "pdf": {"application/pdf"},
    "docx": {"application/vnd.openxmlformats-officedocument.wordprocessingml.document", "application/zip", "application/x-zip-compressed"},
    "xlsx": {"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "application/zip", "application/x-zip-compressed"},
    "pptx": {"application/vnd.openxmlformats-officedocument.presentationml.presentation", "application/zip", "application/x-zip-compressed"},
}


def validate_upload_metadata(
    *, file_name: str | None, content_type: str | None,
) -> tuple[str, str]:
    """返回纯文件名和格式；不可信的文件名只作显示，不转换为服务器路径。

    客户端可能提交C:\\fakepath\\模板.pptx，先去掉路径。拒绝控制字符、Windows
    保留名/字符和异常长名称。MIME只作辅助；缺失或octet-stream允许继续内容检查。
    """
    if not file_name or len(file_name) > 1024 or any(ord(char) < 32 or ord(char) == 127 for char in file_name):
        raise FileUploadError("invalid_file_name", "请提供有效文件名，不能包含控制字符。")
    name = file_name.replace("\\", "/").rsplit("/", 1)[-1]
    reserved = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}
    if (
        not name or len(name) > 255 or name.endswith((" ", "."))
        or any(char in '<>:"|?*' for char in name)
        or name.split(".", 1)[0].upper() in reserved
    ):
        raise FileUploadError("invalid_file_name", "文件名为空、过长或包含不支持的名称/字符。")
    extension = name.rsplit(".", 1)[-1].lower() if "." in name else ""
    if extension not in _SUPPORTED_FORMATS:
        raise FileUploadError("unsupported_format", "附件仅接受TXT、MD、PDF、DOCX、XLSX、PPTX。")
    media_type = (content_type or "").split(";", 1)[0].strip().lower()
    if media_type not in {"", "application/octet-stream", *_FORMAT_MIME_TYPES[extension]}:
        raise FileUploadError("content_type_mismatch", "声明的Content-Type与文件扩展名不匹配，请检查上传类型。")
    return name, extension


def validate_uploaded_content(
    *, content: bytes, file_format: str, max_file_bytes: int, max_uncompressed_bytes: int,
) -> None:
    """检查实际字节；失败抛FileUploadError，不等于已成功提取正文或模型分析。

    此函数不读取磁盘、不操作网络，也不把文件放进全局内存。Office包检查可能耗时，
    HTTP调用方在线程中执行，避免阻塞事件循环。
    """
    if not content:
        raise FileUploadError("empty_file", "文件为空，请选择有内容的文件。")
    if len(content) > max_file_bytes:
        raise FileUploadError("file_too_large", "文件超过UPLOAD_MAX_FILE_BYTES配置的字节上限。")
    if file_format in {"txt", "md"}:
        _validate_text(content)
    elif file_format == "pdf":
        # 只做基础PDF头尾特征检查。能否解密、读取页面及提取文字由后续PDF解析器确认。
        if not content.startswith(b"%PDF-") or b"%%EOF" not in content[-1024:]:
            raise FileUploadError("invalid_file", "文件不具备完整的PDF头尾特征，可能格式不符或已损坏。")
    elif file_format in {"pptx", "docx", "xlsx"}:
        validate_office_package(content=content, file_format=file_format, max_uncompressed_bytes=max_uncompressed_bytes)
    else:
        raise FileUploadError("unsupported_format", "当前不支持此文件格式。")


def _validate_text(content: bytes) -> None:
    """接受UTF-8及带BOM的UTF-16文本；不把任意二进制按宽松编码猜成正文。"""
    try:
        decode_document_text(content)
    except UnicodeError:
        raise FileUploadError("invalid_file", "文本编码不可读取，请另存为UTF-8或带BOM的UTF-16。") from None
    except ValueError:
        raise FileUploadError("invalid_file", "文本为空白或包含二进制控制字符，请确认实际文件内容。") from None
