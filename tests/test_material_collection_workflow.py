"""真实模型、搜索和文件流程：uv run pytest tests/test_material_collection_workflow.py -s。"""

from uuid import uuid4

import httpx
import pytest

from agents.materials.file_extraction_agent import FileExtractionAgent
from agents.materials.material_summary_agent import MaterialSummaryAgent
from config.settings import PROJECT_ROOT, Settings
from domain.documents.document_file_reader import DocumentFileReader
from integrations.documents.document_reader_registry import create_document_readers
from integrations.llm.langchain_model_factory import create_langchain_model
from integrations.web.webpage_http_client import create_webpage_http_client
from models.documents.document_content import DocumentReadLimits
from tests.test_research_workflow import _create_workflow
from workflows.materials.material_collection_workflow import MaterialCollectionWorkflow


@pytest.mark.asyncio
async def test_real_material_collection() -> None:
    """真实DOCX、搜索与模型；根据实际结果核对报告、暂停和来源。"""
    settings = Settings()
    path = PROJECT_ROOT / "data" / "test_file" / "test6.docx"
    # 请根据所选文件内容修改问题；测试不把文件内容当作模拟模型结果。
    question = "介绍前端开发中的HTML、CSS和JavaScript基础知识。"
    reader = DocumentFileReader(readers=create_document_readers(),
        limits=DocumentReadLimits(max_characters=settings.document_max_characters,
            max_blocks=settings.document_max_blocks, max_cells=settings.document_max_cells),
        max_file_bytes=settings.upload_max_file_bytes, max_uncompressed_bytes=settings.upload_max_uncompressed_bytes)
    async with httpx.AsyncClient() as model_http, httpx.AsyncClient(trust_env=False) as search_http, \
            create_webpage_http_client(verify_tls=settings.webpage_tls_verify) as webpage_http:
        model = create_langchain_model(base_url=settings.llm_base_url, api_key=settings.llm_api_key,
            model_name=settings.get_model("outline"), timeout_seconds=settings.llm_timeout_seconds,
            max_tokens=settings.llm_max_tokens, http_client=model_http)
        web = _create_workflow(settings=settings, model=model, search_http=search_http, webpage_http=webpage_http)
        file_agent = FileExtractionAgent(model=model, file_reader=reader,
            prompt=(PROJECT_ROOT / "prompts/materials/file_extraction.md").read_text(encoding="utf-8"))
        summary_agent = MaterialSummaryAgent(model=model, output_tokens=settings.llm_max_tokens,
            prompt=(PROJECT_ROOT / "prompts/materials/material_summary.md").read_text(encoding="utf-8"))
        flow = MaterialCollectionWorkflow(web_workflow=web, file_agent=file_agent,
                                          summary_agent=summary_agent, target_count=settings.research_target_source_count)
        thread_id = uuid4().hex
        result = await flow.run(thread_id=thread_id, question=question, file_name=path.name, file_content=path.read_bytes())
        print("【状态】", result["status"], result["message"])
        print("【网页报告】", result["report"]["web"])
        print("【文件报告】", result["report"]["file"])
        print("【统一报告】", result["report"])
        print("【汇总】", result["summary"])
        print("【等待问题】", result["waiting_question"])
        assert result["status"] != "interrupted", result["message"]
        assert result["web"]["waiting_question"] is None
        assert result["file"] and result["file"]["status"] == "completed"
        if result["status"] == "awaiting_user":
            assert result["waiting_question"]
            answered = await flow.answer(thread_id=thread_id, question_id=result["waiting_question"]["question_id"],
                                         answer="end_conversation")
            assert answered["status"] == "cancelled"
