"""选择网页研究结果的HTTP公开字段，不执行路由或模型调用。"""
import logging

from models.chat.chat_request import ChatSubmission
from models.chat.chat_response import ChatAttachmentResponse, ChatReadResponse, ChatResearchResult, ChatResearchSource, ChatTemplateResponse
from models.web.research_contract import ResearchState

logger = logging.getLogger(__name__)


def build_chat_response(*, submission: ChatSubmission, task_id: str, result: ResearchState,
                        attachment: ChatAttachmentResponse | None, template: ChatTemplateResponse | None) -> ChatReadResponse:
    """构造SSE result事件的数据；只公开来源、报告及用户可见字段。"""
    sources = [ChatResearchSource(candidate_id=page["candidate_id"], title=page["title"],
                                  url=page["final_url"], truncated=page["truncated"]) for page in result["pages"]]
    research = ChatResearchResult(summary=result["summary"], sources=sources,
                                  page_extractions=result["page_extractions"], report=result["report"],
                                  waiting_question=result["waiting_question"])
    logger.info("event=chat_research_result status=%s source_count=%d", result["status"], len(sources))
    return ChatReadResponse(task_id=task_id, message=submission.message, template_key=submission.template_key,
                            status=result["status"], notice=result["message"], attachment=attachment,
                            template=template, research=research)
