"""SSE对话入口，与普通JSON接口共用请求格式。"""
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse

from api.chat_openapi import CHAT_REQUEST_BODY, CHAT_RESPONSES
from api.chat_request_parser import get_chat_submission
from api.chat_stream import stream_chat
from models.chat.chat_request import ChatSubmission

router = APIRouter(tags=["对话"])


@router.post("/chat/stream", response_class=StreamingResponse,
             responses={200: {"description": "SSE事件流：start、progress、result或error。",
                              "content": {"text/event-stream": {"schema": {"type": "string"}}}}, **CHAT_RESPONSES},
             openapi_extra=CHAT_REQUEST_BODY,
             summary="流式返回资料收集进度与最终JSON")
async def chat_stream(request: Request, submission: Annotated[ChatSubmission, Depends(get_chat_submission)]) -> StreamingResponse:
    """请求校验在开始发送前完成；发送后错误通过SSE error事件报告。"""
    return StreamingResponse(stream_chat(request, submission), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
