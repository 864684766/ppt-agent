"""根据已经读取的网页正文，让模型整理可追溯的资料要点。"""

import json

from langchain_core.language_models import BaseChatModel

from diagnostics.operation_logging import log_operation
from models.web.web_research_summary import WebResearchPage, WebResearchSummary


class WebResearchSummaryAgent:
    """模型只整理调用方交给它的正文；不自行访问网络或保证事实正确。"""

    def __init__(self, *, model: BaseChatModel, prompt: str) -> None:
        """注入共用模型工厂创建的模型和提示词；不会立即请求模型。"""
        self._model = model.with_structured_output(WebResearchSummary, method="json_mode")
        self._prompt = prompt

    @log_operation("agent.web_research_summary")
    async def summarize(self, *, question: str, pages: list[WebResearchPage]) -> WebResearchSummary:
        """整理非空网页列表；模型编号不属于输入时抛错，不能伪造来源。"""
        if not pages:
            raise ValueError("没有可整理的网页正文。")
        result = await self._model.ainvoke(
            self._prompt + "\n用户要求：" + question + "\n网页数据：" + json.dumps(pages, ensure_ascii=False)
        )
        if not isinstance(result, WebResearchSummary):
            raise ValueError("模型未返回有效的网页整理结果。")
        valid_ids = {page["candidate_id"] for page in pages}
        if any(not set(point.candidate_ids).issubset(valid_ids) for point in result.points):
            raise ValueError("模型引用了未提供正文的候选编号。")
        return result
