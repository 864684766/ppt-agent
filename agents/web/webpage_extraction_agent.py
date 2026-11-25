"""逐页提炼网页正文及可跟进链接。"""

import json
import logging

from langchain_core.language_models import BaseChatModel
from openai import LengthFinishReasonError

from diagnostics.operation_logging import log_operation
from models.web.web_research_summary import WebPageExtraction

logger = logging.getLogger(__name__)


class WebpageExtractionAgent:
    """网页正文只传给单页提炼；跨页面汇总由独立Agent负责。"""

    def __init__(self, *, model: BaseChatModel, prompt: str, retry_prompt: str) -> None:
        """接收单页提炼和超限重试提示词；资源由调用方负责。"""
        self._page_model = model.with_structured_output(WebPageExtraction, method="json_mode")
        self._prompt = prompt
        self._retry_prompt = retry_prompt

    @log_operation("agent.web_research_extract_page")
    async def extract_page(self, *, question: str, page: dict) -> WebPageExtraction:
        """提炼一篇网页；校验来源和后续链接确实来自本页。"""
        # 动态数据单独追加，不参与提示词模板替换。
        prompt = self._prompt + "\n用户要求：" + question + "\n网页数据：" + json.dumps(page, ensure_ascii=False)
        try:
            result = await self._page_model.ainvoke(prompt)
        except LengthFinishReasonError:
            # 限制为一次重试；不把输出超限误记为网页没有相关内容。
            logger.warning("event=research_page_extraction_length_retry")
            result = await self._page_model.ainvoke(prompt + "\n" + self._retry_prompt)
        if not isinstance(result, WebPageExtraction):
            raise ValueError("模型未返回有效的单页提炼结果。")
        page_id = page["candidate_id"]
        if any(set(point.candidate_ids) != {page_id} for point in result.points):
            raise ValueError("单页要点引用了其他网页编号。")
        links = {link["url"] for link in page["links"]}
        result.follow_links = [item for item in result.follow_links
                               if item.candidate_id == page_id and item.url in links][:3]
        return result

