"""分析用户需求并提出资料处理计划；不执行搜索、读取或询问。"""

import json
import logging
from langchain_core.language_models import BaseChatModel
from langchain_core.exceptions import OutputParserException
from langchain_openai.chat_models.base import OpenAIConnectionError, OpenAITimeoutError
from pydantic import ValidationError
from diagnostics.operation_logging import log_operation, safe_error_location
from models.materials.request_analysis import RequestAnalysis, RequestAnalysisResult

logger = logging.getLogger(__name__)


class RequestAnalysisAgent:
    """借用调用方的模型和提示词，输出经过结构校验的计划建议。"""

    def __init__(self, *, model: BaseChatModel, prompt: str) -> None:
        self._model = model.with_structured_output(RequestAnalysis, method="json_mode")
        self._prompt = prompt

    @log_operation("agent.request_analysis")
    async def analyze(self, *, message: str, has_file: bool, allow_web: bool | None = None) -> RequestAnalysisResult:
        """分析用户消息和附件事实；allow_web=False是调用方明确禁止联网的约束。

        失败返回安全分类且plan为None；取消仍向上传递。模型理解用户意图仍需评估。
        """
        if not isinstance(message, str) or not message.strip() or type(has_file) is not bool or (allow_web is not None and type(allow_web) is not bool):
            return RequestAnalysisResult(status="failed", plan=None, error_code="invalid_input", message="需求分析输入无效，请检查消息和资料选项。")
        payload = {"message": message, "has_file": has_file, "allow_web": allow_web}
        try:
            result = await self._model.ainvoke(self._prompt + "\n输入：" + json.dumps(payload, ensure_ascii=False))
            if not isinstance(result, RequestAnalysis):
                raise ValueError("模型未返回有效需求分析计划。")
            if not has_file and result.source_mode in {"file", "both"} and not result.needs_clarification:
                raise ValueError("计划需要未提供的文件。")
            if allow_web is False and result.source_mode in {"web", "both"}:
                raise ValueError("计划违反联网限制。")
        except Exception as error:
            # 安全日志只包含类型和位置；不输出消息、提示词或模型原文。
            logger.error("event=request_analysis_failed error_location=%s", safe_error_location(error))
            if isinstance(error, OpenAITimeoutError):
                code, message = "model_timeout", "需求分析超时，请稍后重试。"
            elif isinstance(error, OpenAIConnectionError):
                code, message = "model_connection", "需求分析连接失败，请检查服务后重试。"
            elif isinstance(error, (OutputParserException, ValidationError, ValueError)):
                code, message = "invalid_plan", "需求分析结果无效，请重试。"
            else:
                code, message = "analysis_failed", "需求分析失败，请检查服务日志。"
            return RequestAnalysisResult(status="failed", plan=None, error_code=code, message=message)
        return RequestAnalysisResult(status="completed", plan=result, error_code=None, message="需求分析完成。")
