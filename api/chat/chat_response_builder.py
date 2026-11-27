"""从资料图状态选择SSE公开字段；不返回内部状态、附件字节或网页正文。"""

from models.chat.chat_request import ChatSubmission
from models.chat.chat_response import ChatReadResponse, ChatResearchSource, ChatTemplateResponse
from models.materials.material_collection_state import MaterialCollectionState


def build_chat_response(*, submission: ChatSubmission, task_id: str, result: MaterialCollectionState,
                        template: ChatTemplateResponse | None) -> ChatReadResponse:
    """保留汇总要点与来源映射；尚未产生的阶段以空值表示。"""
    web = result.get("web") or {}
    pages = {page["candidate_id"]: page for page in result.get("prior_pages", [])}
    pages.update({page["candidate_id"]: page for page in web.get("pages", [])})
    sources = [ChatResearchSource(candidate_id=page["candidate_id"], title=page["title"],
                                 url=page["final_url"], truncated=page["truncated"])
               for page in pages.values()]
    file = result.get("file") or {}
    # 图状态使用可序列化字典；在HTTP边界统一校验嵌套对象、状态及枚举。
    return ChatReadResponse.model_validate({
        "task_id": task_id, "previous_task_id": submission.previous_task_id,
        "message": submission.message, "template_key": submission.template_key,
        "status": result["status"], "notice": result["message"], "analysis": result.get("analysis"),
        "summary": result.get("summary"), "outline": result.get("outline"), "outline_error": result.get("outline_error"),
        "summary_inputs": result.get("summary_inputs") or result.get("prior_inputs", []), "sources": sources,
        "file_sources": result.get("file_sources", {}),
        "report": result.get("report"), "waiting_question": result.get("waiting_question"),
        "attachment_analyzed": file.get("status") == "completed",
        "attachment_file_name": submission.attachment.file_name if submission.attachment else None, "template": template,
    })
