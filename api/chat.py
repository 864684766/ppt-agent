"""普通模型对话调试接口；尚不是带项目状态的大纲对话接口。"""

import json
from collections.abc import AsyncGenerator
from contextlib import aclosing
from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field

from api.dependencies import get_chat_client
from integrations.llm import ChatClient, ModelCallError


class ChatRequest(BaseModel):
    """只接受一条非空消息；限制长度以避免调试时误传大段文件。"""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    message: str = Field(min_length=1, max_length=10000, description="用户消息，最多 10000 字符")


router = APIRouter(prefix="/ppt-agent/v1", tags=["模型调试"])


def encode_event(event: str, data: dict[str, str]) -> str:
    """构造一个 SSE 事件；空行标志事件结束，JSON 转义正文中的换行。

    ensure_ascii=False 让中文直接以 UTF-8 传输。客户端必须按 SSE 事件解析，
    不能假设一个网络数据包就是一个事件或一个 token。
    """
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


async def stream_events(client: ChatClient, message: str) -> AsyncGenerator[str, None]:
    """把模型增量转换为 delta / done / error 事件。

    响应开始后无法将 HTTP 200 改成 502/504，因此调用错误写入 error 事件。
    error 和 done 都是结束标志，失败后不会再发 done，已输出文本可保留供查看。
    不捕获异步取消异常；StreamingResponse 取消消费时通过 finally 关闭上游流。
    """
    try:
        async with aclosing(client.stream_reply(message)) as chunks:
            async for text in chunks:
                yield encode_event("delta", {"text": text})
    except ModelCallError as error:
        yield encode_event("error", {
            "code": "model_timeout" if error.timed_out else "model_error",
            "message": str(error),
        })
        return
    yield encode_event("done", {"finish_reason": "completed"})


@router.post("/chat", response_class=StreamingResponse,
             responses={200: {"content": {"text/event-stream": {"schema": {"type": "string"}}}}},
             summary="调用默认模型进行单轮流式对话")
async def chat(
    request: ChatRequest,
    client: Annotated[ChatClient, Depends(get_chat_client)],
) -> StreamingResponse:
    """将校验后的消息交给模型适配器，以 SSE 格式逐段返回正文。

    Depends 告诉 FastAPI：client 由 get_chat_client 提供，不从 JSON 读取。
    接口负责 HTTP 协议转换，具体如何调用模型由 integrations/llm.py 负责。
    """
    # 返回生成器而不是完整回答；Starlette 在响应期间持续迭代并发送内容。
    # 默认 request 作用域的 yield 依赖会在流发送完后才释放 HTTP 客户端。
    return StreamingResponse(
        stream_events(client, request.message),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
