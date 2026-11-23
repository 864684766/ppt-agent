"""逐页提炼网页，再根据累计要点合并和检查资料。"""

import json
import logging

from langchain_core.language_models import BaseChatModel
from openai import LengthFinishReasonError

from diagnostics.operation_logging import log_operation
from models.web.web_research_summary import WebPageExtraction, WebResearchSummary

logger = logging.getLogger(__name__)


class WebResearchSummaryAgent:
    """封装两种模型调用；网页正文只传给单页提炼，汇总只接收提炼结果。"""

    def __init__(self, *, model: BaseChatModel, prompt: str, page_prompt: str,
                 summary_prompt: str, retry_prompt: str) -> None:
        """接收模型、共同规则和各阶段提示词；读取文件和资源管理由调用方负责。"""
        self._page_model = model.with_structured_output(WebPageExtraction, method="json_mode")
        self._summary_model = model.with_structured_output(WebResearchSummary, method="json_mode")
        self._prompt = prompt
        self._page_prompt = page_prompt
        self._summary_prompt = summary_prompt
        self._retry_prompt = retry_prompt

    @log_operation("agent.web_research_extract_page")
    async def extract_page(self, *, question: str, page: dict) -> WebPageExtraction:
        """提炼一篇网页；校验来源和后续链接确实来自本页。"""
        # 共同规则和单页规则均由外层加载，动态数据单独追加，不参与模板替换。
        prompt = self._prompt + "\n" + self._page_prompt + "\n用户要求：" + question + "\n网页数据：" + json.dumps(page, ensure_ascii=False)
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

    @log_operation("agent.web_research_summary")
    async def summarize(self, *, question: str, extractions: list[dict]) -> WebResearchSummary:
        """合并单页要点并检查缺口；只接受本次实际提炼过的来源编号。"""
        if not extractions:
            raise ValueError("没有可整理的网页提炼结果。")
        result = await self._summary_model.ainvoke(self._prompt + "\n" + self._summary_prompt + "\n用户要求：" + question
                                                     + "\n单页提炼：" + json.dumps(extractions, ensure_ascii=False))
        if not isinstance(result, WebResearchSummary):
            raise ValueError("模型未返回有效的网页整理结果。")
        valid_ids = {item["candidate_id"] for item in extractions}
        point_ids = {item["candidate_id"] for item in extractions if item["points"]}
        if any(not set(point.candidate_ids).issubset(point_ids) for point in result.points):
            raise ValueError("模型要点引用了未提炼的网页编号。")
        if any(not set(issue.candidate_ids).issubset(valid_ids) for issue in result.issues):
            raise ValueError("模型问题引用了未提炼的网页编号。")
        # 跟进链接由单页提炼阶段核对；汇总模型不能再生成新链接。
        result.follow_links = []
        return result
