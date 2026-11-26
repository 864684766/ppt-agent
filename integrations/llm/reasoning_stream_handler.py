"""从LangChain标准模型流提取推理块；不读取供应商私有字段。"""
from collections.abc import Callable
from typing import Any
from uuid import UUID

from langchain_core.callbacks import AsyncCallbackHandler
from langchain_core.outputs import ChatGenerationChunk, GenerationChunk


class ReasoningStreamHandler(AsyncCallbackHandler):
    """把标准reasoning文本片段交给调用方，不记录正文或修改模型返回。"""

    def __init__(self, emit: Callable[[str], None]) -> None:
        self._emit = emit

    async def on_llm_new_token(self, token: str | list[str | dict[str, Any]], *,
                               chunk: GenerationChunk | ChatGenerationChunk | None = None,
                               run_id: UUID, parent_run_id: UUID | None = None,
                               tags: list[str] | None = None, **kwargs: Any) -> None:
        """只接收LangChain标准推理块；普通回答和工具调用不进入thinking事件。"""
        if not isinstance(chunk, ChatGenerationChunk):
            return
        for block in chunk.message.content_blocks:
            if block.get("type") == "reasoning":
                text = block.get("reasoning")
                if isinstance(text, str) and text:
                    self._emit(text)
