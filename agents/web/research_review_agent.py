"""检查子Agent：仅按标题和摘要筛选候选，不宣称已核对正文。"""

import json
import logging
import asyncio

from langchain_core.exceptions import OutputParserException
from langchain_core.language_models import BaseChatModel
from langchain_openai.chat_models.base import OpenAIConnectionError

from diagnostics.operation_logging import log_operation
from models.web.research_contract import SearchReview
from models.web.search_web_contract import WebSearchItem


logger = logging.getLogger(__name__)


class ResearchReviewAgent:
    """独立检查标题和摘要；输出候选编号及搜索建议，不读取网页正文。

    本类使用LangChain模型结构化输出，但不是create_agent工具循环。
    判断结果只是初筛；图负责忽略虚构编号、合并重复URL和决定是否继续。
    """

    def __init__(self, *, model: BaseChatModel, prompt: str) -> None:
        """注入JSON模式模型和外层读取的提示词；构造时不发起模型请求。

        model由调用方创建和管理；prompt描述筛选标准，修改文件后需重新读取
        并创建实例。模型输出将按SearchReview校验，不保证判断一定正确。
        """
        self._reviewer = model.with_structured_output(SearchReview, method="json_mode")
        self._prompt = prompt

    @log_operation("agent.research_review")
    async def review(self, *, question: str, candidates: list[WebSearchItem]) -> SearchReview:
        """筛选本轮候选并返回SearchReview。

        question是用户要求；candidates是search_web返回的本轮网页条目，
        其中编号用于关联结果。空列表直接返回空编号和反馈，不调用模型。
        SearchReview.relevant_ids仅为模型选择；外层还必须核对编号确实存在。
        模型输出格式解析失败时纠正重试一次；再次失败或其他异常向上传递。
        """
        if not candidates:
            return SearchReview(relevant_ids=[], alternatives=[], unmet_requirements=[], feedback="本轮没有候选，请尝试其他搜索引擎或调整搜索词。")
        # ensure_ascii=False让中文保持可读；候选是待分析数据，不是指令。
        prompt = self._prompt + "\n用户要求：" + question + "\n候选数据：" + json.dumps(candidates, ensure_ascii=False)
        try:
            result = await self._invoke_with_connection_retry(prompt)
        except OutputParserException:
            # 只重试输出格式，不记录模型原文；两次失败仍抛错，不能伪装为零结果。
            logger.warning("event=research_review_format_retry")
            result = await self._invoke_with_connection_retry(
                prompt + '\n上次格式不正确。必须输出JSON对象：relevant_ids数组、alternatives对象数组（每项含candidate_id和unmet_requirement）、unmet_requirements数组和feedback字符串。'
            )
        if not isinstance(result, SearchReview):
            raise ValueError("检查模型未返回有效的筛选结果。")
        # 模型可能编造或重复编号；只保留本轮真实编号，重叠时优先保留正式候选。
        valid_ids = {item["candidate_id"] for item in candidates}
        relevant_ids = list(dict.fromkeys(item for item in result.relevant_ids if item in valid_ids))
        seen = set(relevant_ids)
        alternatives = []
        for item in result.alternatives:
            if item.candidate_id in valid_ids and item.candidate_id not in seen:
                alternatives.append(item)
                seen.add(item.candidate_id)
        return SearchReview(relevant_ids=relevant_ids, alternatives=alternatives,
                            unmet_requirements=result.unmet_requirements, feedback=result.feedback)

    async def _invoke_with_connection_retry(self, prompt: str) -> SearchReview:
        """调用检查模型；连接中断时最多重试两次，最终失败保留原异常。

        只处理LangChain包装的OpenAIConnectionError；超时、认证失败、输出长度
        和解析错误由各自现有流程处理。重试仅重新请求本批检查，不重跑搜索或
        已完成批次。asyncio.sleep可被取消，日志不记录提示词和异常原文。
        """
        for retry in range(3):
            try:
                result = await self._reviewer.ainvoke(prompt)
                if not isinstance(result, SearchReview):
                    raise ValueError("检查模型未返回有效的筛选结果。")
                return result
            except OpenAIConnectionError:
                if retry == 2:
                    logger.warning("event=research_review_connection_retries_exhausted retry_count=%d", retry)
                    raise
                logger.warning("event=research_review_connection_retry retry=%d max_retries=2", retry + 1)
                await asyncio.sleep(retry + 1)
        raise RuntimeError("模型重试流程异常结束。")
