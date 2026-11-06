"""附件处理组装边界：内容校验、读取器选择及响应构造，不负责HTTP收流。"""

import asyncio
import logging

from pydantic import ValidationError

from api.chat_error_mapping import chat_http_error
from config.settings import PROJECT_ROOT, Settings
from diagnostics.operation_logging import log_operation
from domain.documents.document_reader_contract import DocumentReadError
from domain.uploads.file_upload_errors import FileUploadError
from domain.uploads.file_upload_validation import validate_uploaded_content
from integrations.documents.document_reader_registry import create_document_readers
from integrations.ocr.rapidocr_text_recognizer import RapidOcrTextRecognizer
from integrations.templates.pdfium_page_renderer import PdfiumPageRenderer
from models.chat.chat_request import ChatAttachmentInput
from models.chat.chat_response import ChatAttachmentResponse
from models.documents.document_content import DocumentContent, DocumentReadLimits


logger = logging.getLogger(__name__)


@log_operation("chat.read_attachment")
async def read_chat_attachment(attachment: ChatAttachmentInput, *, max_file_bytes: int | None = None) -> ChatAttachmentResponse:
    """不读取用户问题、不调用大语言模型；PDF无文字页可使用本地OCR。读取结果未来由外层交给内容智能体。

    max_file_bytes由OSS模板宿主传入其专用上限；未提供时用普通上传上限。
    两种来源复用校验/读取器，不把OSS大文件上限强加给普通上传。
    配置与具体解析库只在此处组装。取消线程等待不会立即中止底层解析，规模
    上限仍生效，各读取器在线程结束时关闭自己创建的资源。
    """
    try:
        settings = Settings()
    except ValidationError:
        raise chat_http_error("configuration_invalid", "附件读取配置无效，请检查环境变量。") from None
    # API是组装层：把环境配置转换成普通数据，读取器不需要知道.env在哪里。
    limits = DocumentReadLimits(
        max_characters=settings.document_max_characters,
        max_blocks=settings.document_max_blocks,
        max_cells=settings.document_max_cells,
    )
    # 注册表按已校验的格式选择实现，而不是让模型猜该使用哪个解析库。
    # 只有PDF注入OCR；构造器不加载权重，有文字的PDF不会初始化OCR模型。
    # 每次请求独立持有识别器，内部各页复用引擎；暂不建立全局模型缓存。
    readers = create_document_readers(
        recognizer=RapidOcrTextRecognizer(model_directory=PROJECT_ROOT / "ocr-models"),
        renderer=PdfiumPageRenderer(),
    ) if attachment.format == "pdf" else create_document_readers()
    reader = readers[attachment.format]

    def validate_and_read() -> DocumentContent:
        # 确定性文件检查先于读取；模型不会参与判断ZIP结构或打开文件句柄。
        validate_uploaded_content(
            content=attachment.content,
            file_format=attachment.format,
            max_file_bytes=max_file_bytes if max_file_bytes is not None else settings.upload_max_file_bytes,
            max_uncompressed_bytes=settings.upload_max_uncompressed_bytes,
        )
        return reader.read(content=attachment.content, limits=limits)

    try:
        result = await asyncio.to_thread(validate_and_read)
    except (FileUploadError, DocumentReadError) as error:
        logger.warning("event=attachment_rejected code=%s format=%s", error.code, attachment.format)
        raise chat_http_error(error.code, str(error)) from None
    logger.info(
        "event=attachment_read format=%s size_bytes=%s blocks=%s pages=%s warnings=%s",
        attachment.format, len(attachment.content), len(result.blocks),
        result.page_count, len(result.warnings),
    )
    return ChatAttachmentResponse(
        file_name=attachment.file_name,
        format=attachment.format,
        size_bytes=len(attachment.content),
        content=result,
    )
