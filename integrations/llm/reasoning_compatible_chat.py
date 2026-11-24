"""兼容OpenAI格式代理提供的流式reasoning_content扩展字段。"""

from typing import Any

from langchain_core.outputs import ChatGenerationChunk
from langchain_openai import ChatOpenAI


class ReasoningCompatibleChatOpenAI(ChatOpenAI):
    """保留代理的推理片段，让LangChain转换为标准reasoning内容块。

    ChatOpenAI当前版本会丢弃非OpenAI字段。这里仅处理存在的字符串字段，
    不修改普通回答或工具调用；依赖当前锁定版本的内部转换钩子，升级时需验证。
    """

    def _convert_chunk_to_generation_chunk(
        self, chunk: dict, default_chunk_class: type, base_generation_info: dict | None,
    ) -> ChatGenerationChunk | None:
        result = super()._convert_chunk_to_generation_chunk(chunk, default_chunk_class, base_generation_info)
        choices: Any = chunk.get("choices") or chunk.get("chunk", {}).get("choices", [])
        if result is not None and choices:
            delta = choices[0].get("delta") or {}
            reasoning = delta.get("reasoning_content")
            if isinstance(reasoning, str) and reasoning:
                # LangChain的content_blocks会将additional_kwargs中的该字段标准化。
                result.message.additional_kwargs["reasoning_content"] = reasoning
                # OpenAI专用转换器会忽略该扩展字段；使用LangChain通用转换器读取。
                result.message.response_metadata.pop("model_provider", None)
        return result
