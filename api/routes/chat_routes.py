"""当前对话只用于接收消息和解析文件，统一返回JSON，不接入AI。"""

from typing import Annotated
from fastapi import APIRouter, Depends

from api.chat_attachment_processing import read_chat_attachment
from api.chat_template_processing import read_chat_template
from api.chat_request_parser import get_chat_submission
from api.chat_openapi import CHAT_REQUEST_BODY, CHAT_RESPONSES
from diagnostics.operation_logging import log_operation
from models.chat.chat_request import ChatSubmission
from models.chat.chat_response import ChatReadResponse

router = APIRouter(tags=["对话"])


@router.post(
    "/chat", response_model=ChatReadResponse,
    responses=CHAT_RESPONSES, openapi_extra=CHAT_REQUEST_BODY,
    summary="接收消息与可选附件，只返回文件解析结果，不调用AI",
)
@log_operation("chat.receive_and_read")
async def chat(
    submission: Annotated[ChatSubmission, Depends(get_chat_submission)],
) -> ChatReadResponse:
    """分别读取上传参考附件和选中的OSS模板；两者可同时提供。

    template_key必须是列表中的object_key，不是URL。指定后实际下载并解析PPTX，
    未指定则不连接OSS。任一文件读取失败明确报错，不伪造部分成功。
    """
    result = None
    template = None
    if submission.attachment is not None:
        result = await read_chat_attachment(submission.attachment)
    if submission.template_key is not None:
        template = await read_chat_template(submission.template_key)
    if result is not None and template is not None:
        status = "files_read"
    elif template is not None:
        status = "template_read"
    elif result is not None:
        status = "attachment_read"
    else:
        status = "message_received"
    return ChatReadResponse(
        message=submission.message,
        template_key=submission.template_key,
        status=status,
        attachment=result,
        template=template,
    )
