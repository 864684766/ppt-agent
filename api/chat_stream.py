"""将网页研究的实际阶段和最终结果通过SSE发送给客户端。"""

import asyncio
import logging
from collections.abc import AsyncIterator
from uuid import uuid4

from fastapi import HTTPException, Request

from api.chat_template_processing import read_chat_template
from api.chat_response_builder import build_chat_response
from api.sse_encoder import encode_event
from diagnostics.operation_logging import operation_scope, safe_error_location
from models.chat.chat_request import ChatSubmission
from integrations.llm.reasoning_stream_handler import ReasoningStreamHandler
from workflows.web.research_progress import research_progress

logger = logging.getLogger(__name__)
_MESSAGES = {
    "analyze": "正在分析需求。", "file": "正在读取并提炼文件。", "template": "正在读取所选模板。",
    "search": "正在分析问题并搜索网页。", "review": "正在检查搜索候选。",
    "read_webpage": "正在读取网页。", "extract": "正在提炼网页要点。",
    "summarize": "正在汇总并检查资料。",
}


async def stream_chat(request: Request, submission: ChatSubmission) -> AsyncIterator[str]:
    """消费一次研究任务并输出完整SSE帧；断连时取消任务并等待资源退出。"""
    task_id = uuid4().hex
    queue: asyncio.Queue[tuple[str, dict]] = asyncio.Queue()

    def progress(stage: str) -> None:
        # 仅由业务选择固定阶段，不向客户端泄露模型正文或内部反馈。
        queue.put_nowait(("progress", {"task_id": task_id, "stage": stage, "message": _MESSAGES[stage]}))

    async def execute() -> None:
        token = research_progress.set(progress)
        try:
            if submission.template_key:
                progress("template")
            template = await read_chat_template(submission.template_key) if submission.template_key else None
            workflow = await request.app.state.web_research_runtime.get_material_workflow()
            # 只为当前SSE请求注册回调；不影响并发请求，也不记录推理正文。
            callbacks = None
            if request.app.state.web_research_runtime.show_thinking:
                callbacks = [ReasoningStreamHandler(lambda text: queue.put_nowait(
                    ("thinking", {"task_id": task_id, "text": text})))]
            attachment = submission.attachment
            result = await workflow.run(thread_id=task_id, question=submission.message,
                file_name=attachment.file_name if attachment else None,
                file_content=attachment.content if attachment else None, callbacks=callbacks)
            response = build_chat_response(submission=submission, task_id=task_id, result=result,
                                           template=template)
            await queue.put(("result", response.model_dump(mode="json")))
        except HTTPException as error:
            await queue.put(("error", {"task_id": task_id, "code": error.detail.get("code", "request_failed"),
                                      "message": error.detail.get("message", "请求处理失败。")}))
        except Exception as error:
            logger.error("event=chat_stream_failed error_location=%s", safe_error_location(error))
            await queue.put(("error", {"task_id": task_id, "code": "research_failed", "message": "资料研究执行失败，请检查服务日志。"}))
        finally:
            research_progress.reset(token)

    with operation_scope(logger, "chat.stream"):
        task = asyncio.create_task(execute())
        try:
            yield encode_event("start", {"task_id": task_id})
            while True:
                try:
                    event, data = await asyncio.wait_for(queue.get(), timeout=15)
                except TimeoutError:
                    # SSE注释是心跳，不会被客户端当作业务事件。
                    yield ": heartbeat\n\n"
                    continue
                yield encode_event(event, data)
                if event in {"result", "error"}:
                    break
        finally:
            if not task.done():
                task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                logger.info("event=chat_stream_cancelled")
