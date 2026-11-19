"""资料收集测试：多个真实联网案例，可在PyCharm调试。

test_real_research会调用真实模型和搜索服务，并消耗模型额度。
"""

import json

import httpx
import pytest

from agents.research_query_agent import ResearchQueryAgent
from agents.research_review_agent import ResearchReviewAgent
from config.settings import PROJECT_ROOT, Settings
from integrations.llm.langchain_model_factory import create_langchain_model
from integrations.web.searxng_search_client import SearxngSearchClient
from tools.web.search_web_tool import create_search_web_tool
from workflows.web_research_workflow import WebResearchWorkflow
from langchain_core.tools import ToolException
from models.web.research_contract import SearchReview
from models.web.search_web_contract import WebSearchItem


class DisplayQueryAgent(ResearchQueryAgent):
    """仅用于测试：显示每轮实际搜索词、策略和原始候选。"""

    async def search(self, *, question: str, feedback: str) -> tuple[str, list[WebSearchItem]]:
        print("\n【本轮搜索策略】服务器默认（不指定引擎）", flush=True)
        try:
            query, candidates = await super().search(question=question, feedback=feedback)
        except ToolException:
            print("【本轮搜索失败】工具返回错误，工作流将根据剩余次数继续。", flush=True)
            raise
        print("【本轮搜索词】", query, flush=True)
        print("【本轮搜索候选】", json.dumps(candidates, ensure_ascii=False, indent=2), flush=True)
        return query, candidates


class DisplayReviewAgent(ResearchReviewAgent):
    """仅用于测试：展示当前批次的检查结果，不修改工作流状态。"""

    async def review(self, *, question: str, candidates: list[WebSearchItem]) -> SearchReview:
        result = await super().review(question=question, candidates=candidates)
        print("【本轮检查结果】", result.model_dump_json(indent=2), flush=True)
        print("【说明】这是本轮检查；最终备用候选会跨轮按URL合并，尚未交给用户确认。", flush=True)
        return result


# pytest会对列表中每一个问题各运行一次test_real_research。
# 用户可在PyCharm中修改这些问题，或在测试树中只运行其中一个参数案例。
QUESTIONS = [
    "介绍一下黄芪。",
    "查找中国居民膳食指南2022关于平衡饮食的资料。",
    "查找《本草纲目》中关于黄芪的记载。",
    "查找中国劳动合同解除的法律规定。",
    "查找成年人每周身体活动建议。",
    "查找中国垃圾分类的基本类别。",
    "查找Python异步编程中async与await的官方说明。",
]


@pytest.mark.asyncio
@pytest.mark.parametrize("question", QUESTIONS)
async def test_real_research(question: str) -> None:
    """真实模型和搜索服务集成测试，结果需要人工判断。

    pytest根据parametrize依次把QUESTIONS中的一条文字传给question；asyncio
    标记让pytest等待异步函数执行。每题建立和关闭独立HTTP连接；测试通过
    仅表示流程以completed或awaiting_user结束，不证明结果准确或来源权威。
    配置缺失、服务故障或模型输出不合法会导致测试失败并显示相应错误。
    """
    settings = Settings()
    # async with负责在测试结束或异常时关闭连接。模型沿用系统代理；
    # 本测试的搜索连接不读取系统代理，以直接访问配置的SearXNG服务。
    async with httpx.AsyncClient() as model_http, httpx.AsyncClient(trust_env=False) as search_http:
        model = create_langchain_model(
            base_url=settings.llm_base_url, api_key=settings.llm_api_key,
            model_name=settings.get_model("outline"), timeout_seconds=settings.llm_timeout_seconds,
            # 推理模型可能将思考计入输出预算；当前真实验证至少给4096。
            max_tokens=max(settings.llm_max_tokens, 4096), http_client=model_http,
        )
        # 显式使用空引擎配置；所有轮次不发送engines参数，由服务器决定。
        default_tool = create_search_web_tool(client=SearxngSearchClient(
            client=search_http, base_url=settings.searxng_base_url, engines="",
            timeout_seconds=settings.web_search_timeout_seconds,
        ))
        # 读取提示词文字后注入Agent；这里不把文件路径直接传给模型。
        query_prompt = (PROJECT_ROOT / "prompts" / "research_query.md").read_text(encoding="utf-8")
        review_prompt = (PROJECT_ROOT / "prompts" / "research_review.md").read_text(encoding="utf-8")
        workflow = WebResearchWorkflow(
            query_agent=DisplayQueryAgent(model=model, tool=default_tool, prompt=query_prompt),
            review_agent=DisplayReviewAgent(model=model, prompt=review_prompt),
        )
        print("\n【用户问题】", question, flush=True)
        # 在此打断点；可进入两个Agent，观察每轮搜索词和筛选反馈。
        result = await workflow.run(question=question, target_count=2, max_attempts=5)
    print("\n【用户问题】", question)
    print("【状态、次数、搜索调用失败次数】", result["status"], result["attempt"], result["failed_attempts"])
    print("【用户可选动作】", result["user_options"])
    print("【工作流提示】", result["message"])
    print("【最后一轮搜索词和检查反馈】", result["query"], result["feedback"])
    print("【候选结果】", json.dumps(result["accepted"], ensure_ascii=False, indent=2))
    print("【累计备用候选及原因】", json.dumps(result["alternatives"], ensure_ascii=False, indent=2))
    print("【用户已选择的备用候选】", json.dumps(result["selected_alternatives"], ensure_ascii=False, indent=2))
    assert result["status"] in {"completed", "awaiting_user"}, result["message"]
