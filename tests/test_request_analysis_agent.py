"""真实模型需求判断：uv run pytest tests/test_request_analysis_agent.py -s。"""

import httpx
import pytest

from agents.materials.request_analysis_agent import RequestAnalysisAgent
from config.settings import PROJECT_ROOT, Settings
from integrations.llm.langchain_model_factory import create_langchain_model


@pytest.mark.asyncio
async def test_real_request_analysis() -> None:
    """逐条打印真实模型计划，断言核心分支；具体语义仍需人工核对。"""
    cases = [
        ("根据这个文件分析，给我一个PPT。", True, "file", "single", False),
        ("搜集健康饮食资料，制作PPT。", False, "web", "single", False),
        ("结合上传文件和网上资料介绍健康饮食。", True, "both", "parallel", False),
        ("先分析文件内容，再根据文件主题搜索相关资料。", True, "both", "file_then_web", False),
        ("根据上传文件制作PPT。", False, "file", "single", True),
        ("帮我做一个PPT。", False, "undetermined", "undetermined", True),
    ]
    settings = Settings()
    async with httpx.AsyncClient() as client:
        model = create_langchain_model(base_url=settings.llm_base_url, api_key=settings.llm_api_key,
            model_name=settings.get_model("outline"), timeout_seconds=settings.llm_timeout_seconds,
            max_tokens=settings.llm_max_tokens, http_client=client)
        agent = RequestAnalysisAgent(model=model, prompt=(PROJECT_ROOT / "prompts/materials/request_analysis.md").read_text(encoding="utf-8"))
        for message, has_file, mode, order, clarify in cases:
            outcome = await agent.analyze(message=message, has_file=has_file)
            print("\n【输入】", message, "有文件:", has_file, flush=True)
            print("【分析结果】", outcome.model_dump_json(indent=2), flush=True)
            assert outcome.status == "completed", outcome.message
            result = outcome.plan
            assert result is not None
            assert result.needs_clarification == clarify
            if not clarify:
                assert (result.source_mode, result.execution_order) == (mode, order)
        offline = await agent.analyze(message="只根据上传文件介绍健康饮食，不要联网。", has_file=True, allow_web=False)
        print("\n【禁止联网计划】", offline.model_dump_json(indent=2), flush=True)
        assert offline.status == "completed", offline.message
        assert offline.plan is not None and offline.plan.source_mode == "file" and not offline.plan.needs_clarification
