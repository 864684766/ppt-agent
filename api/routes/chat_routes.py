"""接收消息及可选文件，启动一次网页资料研究。"""

import logging
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request

from api.chat_attachment_processing import read_chat_attachment
from api.chat_template_processing import read_chat_template
from api.chat_request_parser import get_chat_submission
from api.chat_openapi import CHAT_REQUEST_BODY, CHAT_RESPONSES
from diagnostics.operation_logging import log_operation, safe_error_location
from models.chat.chat_request import ChatSubmission
from models.chat.chat_response import ChatReadResponse, ChatResearchResult, ChatResearchSource

router = APIRouter(tags=["对话"])
logger = logging.getLogger(__name__)


@router.post(
    "/chat", response_model=ChatReadResponse,
    responses=CHAT_RESPONSES, openapi_extra=CHAT_REQUEST_BODY,
    summary="接收问题与可选文件，启动网页资料研究",
)
@log_operation("chat.web_research")
async def chat(
    request: Request,
    submission: Annotated[ChatSubmission, Depends(get_chat_submission)],
) -> ChatReadResponse:
    """解析附件与OSS模板，随后以问题启动网页研究；附件尚未参与模型分析。"""
    attachment = await read_chat_attachment(submission.attachment) if submission.attachment else None
    template = await read_chat_template(submission.template_key) if submission.template_key else None
    try:
        workflow = await request.app.state.web_research_runtime.get_workflow()
    except (ValueError, OSError) as error:
        logger.error("event=chat_research_configuration_failed error_location=%s", safe_error_location(error))
        raise HTTPException(503, detail={"code": "configuration_invalid", "message": "网页研究配置无效，请检查模型、搜索服务及提示词配置。"}) from None
    task_id = uuid4().hex
    try:
        result = await workflow.run(thread_id=task_id, question=submission.message)
    except Exception as error:
        # 不向客户端或日志暴露模型异常原文、网页内容或密钥。
        logger.error("event=chat_research_failed error_location=%s", safe_error_location(error))
        raise HTTPException(502, detail={"code": "research_failed", "message": "网页资料研究执行失败，请检查模型与搜索服务日志后重试。"}) from None
    sources = [ChatResearchSource(candidate_id=page["candidate_id"], title=page["title"],
                                  url=page["final_url"], truncated=page["truncated"]) for page in result["pages"]]
    research = ChatResearchResult(summary=result["summary"], sources=sources,
                                  page_extractions=result["page_extractions"], report=result["report"],
                                  waiting_question=result["waiting_question"])
    logger.info("event=chat_research_result status=%s source_count=%d", result["status"], len(sources))
    return ChatReadResponse(task_id=task_id, message=submission.message, template_key=submission.template_key,
                            status=result["status"], notice=result["message"], attachment=attachment,
                            template=template, research=research)
