"""chat中的OSS模板处理：组装下载能力，再复用已有PPTX文字读取。"""

import asyncio
from pydantic import ValidationError
from fastapi import HTTPException

from api.chat_attachment_processing import read_chat_attachment
from api.template_resource_dependencies import open_template_storage_client
from config.settings import Settings
from diagnostics.operation_logging import log_operation
from domain.templates.template_file_reader_contract import TemplateFileReader
from domain.templates.template_resource_catalog_contract import TemplateResourceError
from integrations.storage.s3_template_file_reader import S3TemplateFileReader
from models.chat.chat_request import ChatAttachmentInput
from models.chat.chat_response import ChatTemplateResponse


@log_operation("chat.read_template")
async def read_chat_template(template_key: str) -> ChatTemplateResponse:
    """下载模板并提取实际幻灯片文字，不调用AI/视觉/渲染，也不修改文件。

    SDK连接和下载流在线程中关闭。取消等待不保证立即终止下载线程，其连接/读取
    超时及文件大小上限仍生效；解析阶段也由独立读取模块在线程中处理。
    """
    try:
        settings = Settings()
    except ValidationError:
        raise HTTPException(503, detail={"code": "storage_configuration_invalid", "message": "OSS模板配置无效，请检查环境变量。"}) from None

    def download() -> bytes:
        with open_template_storage_client(settings) as client:
            reader: TemplateFileReader = S3TemplateFileReader(
                client=client, bucket=settings.s3_template_bucket,
            )
            return reader.read_file(object_key=template_key, max_bytes=settings.s3_template_max_file_bytes)

    try:
        content = await asyncio.to_thread(download)
    except TemplateResourceError as error:
        status = {
            "template_not_found": 404, "template_too_large": 413,
            "template_format_invalid": 422, "template_empty": 400,
            "storage_configuration_invalid": 503,
        }.get(error.code, 502)
        raise HTTPException(status, detail={"code": error.code, "message": str(error)}) from None
    # OSS Key不是本地路径，只取最后一段作展示。真实下载仍使用完整template_key。
    parsed = await read_chat_attachment(
        ChatAttachmentInput(file_name=template_key.rsplit("/", 1)[-1], format="pptx", content=content),
        max_file_bytes=settings.s3_template_max_file_bytes,
    )
    return ChatTemplateResponse(object_key=template_key, **parsed.model_dump())
