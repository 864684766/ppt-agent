"""真实文件与模型验证：uv run pytest tests/test_file_extraction_agent.py -s。"""

import httpx
import pytest

from agents.materials.file_extraction_agent import FileExtractionAgent
from config.settings import PROJECT_ROOT, Settings
from domain.documents.document_file_reader import DocumentFileReader
from integrations.documents.document_reader_registry import create_document_readers
from integrations.llm.langchain_model_factory import create_langchain_model
from integrations.ocr.rapidocr_text_recognizer import RapidOcrTextRecognizer
from integrations.templates.pdfium_page_renderer import PdfiumPageRenderer
from models.documents.document_content import DocumentReadLimits


@pytest.mark.asyncio
async def test_real_file_extraction() -> None:
    """根据文件名选择实际解析器；修改路径和问题即可测试其他真实文件。"""
    settings = Settings()
    path = PROJECT_ROOT / "data" / "test_file" / "test6.docx"
    question = "总结文件的主要内容。"
    # question="总结应知应会的主要内容"
    reader = DocumentFileReader(
        readers=create_document_readers(recognizer=RapidOcrTextRecognizer(model_directory=PROJECT_ROOT / "ocr-models"),
                                        renderer=PdfiumPageRenderer(), gotenberg_base_url=settings.gotenberg_base_url,
                                        gotenberg_timeout_seconds=settings.gotenberg_timeout_seconds),
        limits=DocumentReadLimits(max_characters=settings.document_max_characters,
                                 max_blocks=settings.document_max_blocks, max_cells=settings.document_max_cells),
        max_file_bytes=settings.upload_max_file_bytes, max_uncompressed_bytes=settings.upload_max_uncompressed_bytes,
    )
    async with httpx.AsyncClient() as client:
        model = create_langchain_model(base_url=settings.llm_base_url, api_key=settings.llm_api_key,
            model_name=settings.get_model("outline"), timeout_seconds=settings.llm_timeout_seconds,
            max_tokens=settings.llm_max_tokens, http_client=client)
        prompt = (PROJECT_ROOT / "prompts" / "materials" / "file_extraction.md").read_text(encoding="utf-8")
        agent = FileExtractionAgent(model=model, prompt=prompt, file_reader=reader)
        result = await agent.extract_file(question=question, file_name=path.name, content=path.read_bytes())
        if result.resume_id:
            # 演示同一实例内恢复一次；真实应用由调用方决定何时恢复。
            print("【首次中断】", result.failure_reason, "已处理", result.processed_characters, flush=True)
            result = await agent.resume(resume_id=result.resume_id)
    print("【用户问题】", question)
    print("【文件提炼结果】", result.model_dump_json(indent=2))
    assert result.report is not None
    assert result.report.stage == "extraction"
    assert result.report.has_usable_content == bool(result.points)
    assert result.status == "completed", f"文件提炼中断：{result.failure_reason}"
    assert result.points, "真实模型未提炼出相关要点，需人工检查模型配置或返回内容。"
    assert all(point.block_ids for point in result.points)
