"""真实模型、搜索和文件流程：uv run pytest tests/test_material_collection_workflow.py -s。"""

from uuid import uuid4

import httpx
import pytest

from agents.materials.file_extraction_agent import FileExtractionAgent
from agents.materials.material_summary_agent import MaterialSummaryAgent
from agents.materials.request_analysis_agent import RequestAnalysisAgent
from config.settings import PROJECT_ROOT, Settings
from domain.documents.document_file_reader import DocumentFileReader
from integrations.documents.document_reader_registry import create_document_readers
from integrations.llm.langchain_model_factory import create_langchain_model
from integrations.web.webpage_http_client import create_webpage_http_client
from models.documents.document_content import DocumentReadLimits
from tests.test_research_workflow import _create_workflow
from workflows.materials.material_collection_workflow import MaterialCollectionWorkflow

# cases = [
#     ("根据这个文件分析，给我一个PPT。", True, "file", "single", False),
#     ("搜集健康饮食资料，制作PPT。", False, "web", "single", False),
#     ("结合上传文件和网上资料介绍健康饮食。", True, "both", "parallel", False),
#     ("先分析文件内容，再根据文件主题搜索相关资料。", True, "both", "file_then_web", False),
#     ("根据上传文件制作PPT。", False, "file", "single", True),
#     ("帮我做一个PPT。", False, "undetermined", "undetermined", True),
# ]

@pytest.mark.asyncio
async def test_real_material_collection() -> None:
    """用真实文件和模型验证仅文件分支，检查报告、暂停和来源。"""
    settings = Settings()
    path = PROJECT_ROOT / "data" / "test_file" / "test6.docx"
    # 请根据所选文件内容修改问题；测试不把文件内容当作模拟模型结果。
    question = "只根据上传文件介绍面试题，不要联网"
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
        summary_agent = MaterialSummaryAgent(model=model, output_tokens=settings.llm_max_tokens, timeout_seconds=settings.llm_timeout_seconds,
            retry_prompt=(PROJECT_ROOT / "prompts/materials/material_summary_retry.md").read_text(encoding="utf-8"),
            prompt=(PROJECT_ROOT / "prompts/materials/material_summary.md").read_text(encoding="utf-8"))
        request_agent = RequestAnalysisAgent(model=model,
            prompt=(PROJECT_ROOT / "prompts/materials/request_analysis.md").read_text(encoding="utf-8"))
        flow = MaterialCollectionWorkflow(request_agent=request_agent, web_workflow=web, file_agent=file_agent,
                                          summary_agent=summary_agent,
                                          target_count=settings.research_target_source_count)
        thread_id = uuid4().hex
        result = await flow.run(thread_id=thread_id, question=question, file_name=path.name, file_content=path.read_bytes())
        print("【状态】", result["status"], result["message"])
        print("【需求分析】", result["analysis"])
        print("【网页报告】", (result["report"] or {}).get("web"))
        print("【文件报告】", (result["report"] or {}).get("file"))
        print("【统一报告】", result["report"])
        print("【汇总】", result["summary"])
        print("【大纲】", result["outline"], "【大纲错误】", result["outline_error"])
        print("【等待问题】", result["waiting_question"])
        assert result["status"] != "interrupted", result["message"]
        analysis = result["analysis"]
        assert analysis and analysis.get("plan")
        assert analysis["plan"]["source_mode"] == "file"
        assert result["web"] is None, "仅文件分析不应启动网页搜索。"
        file_result = result["file"]
        assert file_result and file_result["status"] == "completed"
        if result["status"] == "completed":
            outline = result["outline"]
            assert outline and outline["slides"]
        if result["status"] == "awaiting_user":
            waiting_question = result["waiting_question"]
            assert waiting_question
            assert result["outline"] is None, "资料不足等待用户时不应提前生成大纲。"
            answered = await flow.answer(thread_id=thread_id, question_id=waiting_question["question_id"],
                                         answer="end_conversation")
            assert answered["status"] == "cancelled"
