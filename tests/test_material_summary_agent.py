"""真实模型汇总验证：uv run pytest tests/test_material_summary_agent.py -s。"""

import httpx
import pytest

from agents.materials.material_summary_agent import MaterialSummaryAgent
from config.settings import PROJECT_ROOT, Settings
from integrations.llm.langchain_model_factory import create_langchain_model
from models.materials.file_extraction import FileExtraction, FileExtractionPoint
from domain.materials.material_summary_inputs import file_summary_points, web_summary_points


@pytest.mark.asyncio
async def test_real_material_summary() -> None:
    """真实模型整理网页和文件的示例要点；模型去重质量需人工检查。"""
    web = [{"candidate_id": "web_demo", "points": [{"content": "成年人每天应食用不少于300克蔬菜。", "candidate_ids": ["web_demo"]}]}]
    file = FileExtraction(file_name="资料.docx", points=[FileExtractionPoint(content="成年人每日蔬菜摄入应至少300克。", block_ids=["b000001"])], warnings=[], pages_without_text=[], status="completed", processed_characters=20, total_characters=20)
    settings = Settings()
    async with httpx.AsyncClient() as client:
        model = create_langchain_model(base_url=settings.llm_base_url, api_key=settings.llm_api_key,
            model_name=settings.get_model("outline"), timeout_seconds=settings.llm_timeout_seconds,
            max_tokens=settings.llm_max_tokens, http_client=client)
        agent = MaterialSummaryAgent(model=model, prompt=(PROJECT_ROOT / "prompts/materials/material_summary.md").read_text(encoding="utf-8"),
                                     retry_prompt=(PROJECT_ROOT / "prompts/materials/material_summary_retry.md").read_text(encoding="utf-8"),
                                     output_tokens=settings.llm_max_tokens, timeout_seconds=settings.llm_timeout_seconds)
        points = web_summary_points(extractions=web) + file_summary_points(extraction=file, source_id="file_demo")
        summary = await agent.summarize(question="介绍成年人每日蔬菜建议。", points=points)
    print("【输入】", [p.model_dump() for p in points])
    print("【汇总】", summary.model_dump_json(indent=2))
    for point in summary.points:
        print("【实际来源】", [ref.model_dump() for ref in summary.references_for(point, points)])
    assert summary.points
    assert all(summary.references_for(point, points) for point in summary.points)
    print("【人工检查】请确认相同建议已合并，且合并结果保留网页及文件两个来源。")
