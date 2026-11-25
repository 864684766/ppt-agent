"""提炼文件：通过注入的文件读取器解析，再逐段调用模型。"""

import asyncio
import json
import logging
from collections import deque
from uuid import uuid4

from langchain_core.language_models import BaseChatModel
from langchain_core.exceptions import OutputParserException
from langchain_openai.chat_models.base import OpenAIConnectionError, OpenAITimeoutError
from openai import LengthFinishReasonError

from diagnostics.operation_logging import log_operation, safe_error_location
from domain.documents.document_file_reader import DocumentFileReader
from domain.documents.document_reader_contract import DocumentReadError
from domain.uploads.file_upload_errors import FileUploadError
from models.documents.document_content import DocumentContent
from models.materials.file_extraction import FileExtraction, FileExtractionBatch, FileProcessingReport

logger = logging.getLogger(__name__)


def _document_batches(content: DocumentContent, max_chars: int = 4000) -> list[list[dict[str, str]]]:
    """按字符数拆分正文；超长块分段但保留原block_id，不静默丢弃正文。"""
    batches: list[list[dict[str, str]]] = []
    batch: list[dict[str, str]] = []
    size = 0
    for block in content.blocks:
        for start in range(0, len(block.text), max_chars):
            text = block.text[start:start + max_chars]
            if batch and size + len(text) > max_chars:
                batches.append(batch)
                batch, size = [], 0
            batch.append({"block_id": block.block_id, "location": block.location, "text": text})
            size += len(text)
    if batch:
        batches.append(batch)
    return batches


def _split_batch(batch: list[dict[str, str]]) -> tuple[list[dict[str, str]], list[dict[str, str]]] | None:
    """优先按正文块拆分；只剩一个块时拆正文，保留块编号。"""
    if len(batch) > 1:
        middle = len(batch) // 2
        return batch[:middle], batch[middle:]
    text = batch[0]["text"]
    if len(text) < 2:
        return None
    middle = len(text) // 2
    return ([{**batch[0], "text": text[:middle]}], [{**batch[0], "text": text[middle:]}])


def _invalid_result_kind(result: object, batch: list[dict[str, str]]) -> str | None:
    """区分结构不合规和来源编号不属于当前批次；不暴露正文或模型输出。"""
    if not isinstance(result, FileExtractionBatch):
        return "type"
    valid_ids = {block["block_id"] for block in batch}
    if any(not set(point.block_ids).issubset(valid_ids) for point in result.points):
        return "unknown_block"
    return None


class FileExtractionAgent:
    """针对用户问题提炼已解析文件；模型、提示词由调用方创建和管理。"""

    def __init__(self, *, model: BaseChatModel, prompt: str, file_reader: DocumentFileReader) -> None:
        """注入聊天模型、提示词和文件读取器；调用方管理模型资源。"""
        self._model = model.with_structured_output(FileExtractionBatch, method="json_mode")
        self._prompt = prompt
        self._file_reader = file_reader
        # 恢复数据仅保存在当前实例中；不能跨实例或进程恢复。
        self._checkpoints: dict[str, tuple] = {}

    @log_operation("agent.file_extraction_file")
    async def extract_file(self, *, question: str, file_name: str, content: bytes) -> FileExtraction:
        """读取并提炼文件字节；解析在线程中运行，失败不会调用模型。"""
        if not question.strip():
            raise ValueError("用户问题不能为空。")
        try:
            name, document = await asyncio.to_thread(self._file_reader.read, file_name=file_name, content=content)
        except (FileUploadError, DocumentReadError) as error:
            # 只捕获约定内的安全异常；文件未解析，不能当成空正文或模型判断无关。
            stage = "validation" if isinstance(error, FileUploadError) else "reading"
            logger.warning("event=file_extraction_read_failed stage=%s code=%s", stage, error.code)
            return FileExtraction(file_name=file_name or "未命名文件", points=[], warnings=[], pages_without_text=[],
                status="failed", processed_characters=0, total_characters=0,
                failure_reason="file_validation" if stage == "validation" else "file_read",
                report=FileProcessingReport(stage=stage, code=error.code, message=str(error), has_usable_content=False))
        except Exception as error:
            # 未知读取故障只返回固定提示，原始异常位置写入安全日志；取消不被拦截。
            logger.error("event=file_extraction_read_failed error_location=%s", safe_error_location(error))
            return FileExtraction(file_name=file_name or "未命名文件", points=[], warnings=[], pages_without_text=[],
                status="failed", processed_characters=0, total_characters=0, failure_reason="processing_failed",
                report=FileProcessingReport(stage="reading", code="processing_failed", message="文件读取发生错误，请检查服务日志。", has_usable_content=False))
        return await self.extract(question=question, file_name=name, content=document)

    @log_operation("agent.file_extraction")
    async def extract(self, *, question: str, file_name: str, content: DocumentContent) -> FileExtraction:
        """逐批提炼并验证块编号；已识别的模型故障返回中断和已处理结果。"""
        if not question.strip() or not file_name.strip():
            raise ValueError("用户问题和文件名不能为空。")
        batches = _document_batches(content)
        # 元组记录正文批次、拆分深度及格式重试次数；重试只针对当前批次。
        pending = deque((batch, 0, 0) for batch in batches)
        return await self._process(question=question, file_name=file_name, content=content, pending=pending,
                                   points=[], processed_chars=0)

    @log_operation("agent.file_extraction_resume")
    async def resume(self, *, resume_id: str) -> FileExtraction:
        """从本实例保留的失败批次继续；编号一次性消费，重启后不可用。"""
        checkpoint = self._checkpoints.pop(resume_id, None)
        if checkpoint is None:
            raise ValueError("恢复编号无效、已使用或进程已重启。")
        question, file_name, content, pending, points, processed_chars = checkpoint
        # 在副本上恢复；异常或取消时原状态仍可重试，不丢失正在处理的批次。
        saved_checkpoint = (question, file_name, content, deque(pending), list(points), processed_chars)
        try:
            return await self._process(question=question, file_name=file_name, content=content, pending=pending,
                                       points=points, processed_chars=processed_chars)
        except BaseException:
            # 取消或未分类异常时恢复旧快照，避免编号被消费后无法再次尝试。
            self._checkpoints[resume_id] = saved_checkpoint
            raise

    async def _invoke_batch(self, instruction: str):
        """仅对超时和连接失败重试当前请求两次；其他异常交给外层分类。"""
        for attempt in range(3):
            try:
                return await self._model.ainvoke(instruction)
            except (OpenAITimeoutError, OpenAIConnectionError):
                if attempt == 2:
                    raise
                logger.warning("event=file_extraction_request_retry attempt=%d", attempt + 1)
                await asyncio.sleep(attempt + 1)

    async def _process(self, *, question: str, file_name: str, content: DocumentContent,
                       pending: deque, points: list, processed_chars: int) -> FileExtraction:
        """从待处理队列依次处理；中断时保存当前批次及其余队列。"""
        total_chars = sum(len(block.text) for block in content.blocks)
        failure_reason = None
        while pending:
            batch, depth, invalid_retries = pending.popleft()
            # 文件正文是外部数据；不执行其中的命令。
            instruction = self._prompt + "\n用户问题：" + question + "\n文件内容：" + json.dumps(batch, ensure_ascii=False)
            try:
                result = await self._invoke_batch(instruction)
            except LengthFinishReasonError:
                parts = _split_batch(batch) if depth < 6 else None
                if parts is None:
                    failure_reason = "output_limit"
                    pending.appendleft((batch, depth, invalid_retries))
                    break
                # 左半先处理；最多拆分六层，避免预算过小时无限调用模型。
                pending.appendleft((parts[1], depth + 1, 0))
                pending.appendleft((parts[0], depth + 1, 0))
                logger.warning("event=file_extraction_split depth=%d", depth + 1)
                continue
            except OpenAITimeoutError:
                failure_reason = "model_timeout"
                pending.appendleft((batch, depth, invalid_retries))
                break
            except OpenAIConnectionError:
                failure_reason = "model_connection"
                pending.appendleft((batch, depth, invalid_retries))
                break
            except OutputParserException:
                result = None
                invalid_kind = "schema"
            except Exception as error:
                logger.error("event=file_extraction_processing_failed error_location=%s", safe_error_location(error))
                failure_reason = "processing_failed"
                pending.appendleft((batch, depth, invalid_retries))
                break
            else:
                invalid_kind = _invalid_result_kind(result, batch)
            if invalid_kind:
                logger.warning("event=file_extraction_invalid kind=%s depth=%d retry=%d",
                               invalid_kind, depth, invalid_retries)
                if invalid_retries == 0:
                    # 不发送失败响应或正文到日志；同一批最多重试一次。
                    pending.appendleft((batch, depth, 1))
                    continue
                parts = _split_batch(batch) if depth < 6 else None
                if parts is not None:
                    logger.warning("event=file_extraction_invalid_split depth=%d", depth + 1)
                    pending.appendleft((parts[1], depth + 1, 0))
                    pending.appendleft((parts[0], depth + 1, 0))
                    continue
                failure_reason = "model_output_invalid"
                pending.appendleft((batch, depth, invalid_retries))
                break
            points.extend(result.points)
            processed_chars += sum(len(block["text"]) for block in batch)
            logger.info("event=file_extraction_batch_completed processed_chars=%d total_chars=%d points=%d",
                        processed_chars, total_chars, len(result.points))
        resume_id = None
        if failure_reason:
            resume_id = uuid4().hex
            self._checkpoints[resume_id] = (question, file_name, content, pending, points, processed_chars)
            logger.warning("event=file_extraction_interrupted reason=%s processed_chars=%d total_chars=%d",
                           failure_reason, processed_chars, total_chars)
        else:
            logger.info("event=file_extraction_completed points=%d", len(points))
        messages = {"output_limit": "模型输出超限，文件提炼未完成。", "model_connection": "模型连接失败，文件提炼未完成。",
                    "model_timeout": "模型请求超时，文件提炼未完成。", "model_output_invalid": "模型返回格式或来源编号无效，文件提炼未完成。",
                    "processing_failed": "文件提炼发生错误，请检查服务日志。"}
        report = FileProcessingReport(stage="extraction", code=failure_reason or "completed",
            message=messages[failure_reason] if failure_reason else "文件提炼完成。",
            has_usable_content=bool(points), warnings=list(content.warnings), pages_without_text=list(content.pages_without_text))
        return FileExtraction(file_name=file_name, points=points, warnings=list(content.warnings),
                              pages_without_text=list(content.pages_without_text),
                              status="interrupted" if failure_reason else "completed",
                              processed_characters=processed_chars, total_characters=total_chars,
                              failure_reason=failure_reason, resume_id=resume_id, report=report)
