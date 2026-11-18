"""资料收集测试：六个真实联网案例及本地逻辑检查，均可在PyCharm调试。

test_real_research会调用真实模型、消耗额度；其余检查使用本地替身。
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


# pytest会对列表中每一个问题各运行一次test_real_research，共六次真实任务。
# 用户可在PyCharm中修改这些问题，或在测试树中只运行其中一个参数案例。
QUESTIONS = [
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
    # 按配置的允许列表组装，顺序决定每一轮使用哪个引擎。
    engines = settings.get_searxng_allowed_engines()
    # async with负责在测试结束或异常时关闭连接。模型沿用系统代理；
    # 本测试的搜索连接不读取系统代理，以直接访问配置的SearXNG服务。
    async with httpx.AsyncClient() as model_http, httpx.AsyncClient(trust_env=False) as search_http:
        model = create_langchain_model(
            base_url=settings.llm_base_url, api_key=settings.llm_api_key,
            model_name=settings.get_model("outline"), timeout_seconds=settings.llm_timeout_seconds,
            # 推理模型可能将思考计入输出预算；当前真实验证至少给4096。
            max_tokens=max(settings.llm_max_tokens, 4096), http_client=model_http,
        )
        # 字典推导式：每个引擎名称对应一个工具；每个工具绑定自己的客户端，
        # 客户端借用同一个search_http连接，不会在这里立即发送搜索请求。
        tools = {
            name: create_search_web_tool(client=SearxngSearchClient(
                client=search_http, base_url=settings.searxng_base_url, engines=name,
                timeout_seconds=settings.web_search_timeout_seconds,
            )) for name in engines
        }
        # 兜底单独绑定空引擎客户端，不能复用可能指定了默认引擎的配置。
        default_tool = create_search_web_tool(client=SearxngSearchClient(
            client=search_http, base_url=settings.searxng_base_url, engines="",
            timeout_seconds=settings.web_search_timeout_seconds,
        ))
        # 读取提示词文字后注入Agent；这里不把文件路径直接传给模型。
        query_prompt = (PROJECT_ROOT / "prompts" / "research_query.md").read_text(encoding="utf-8")
        review_prompt = (PROJECT_ROOT / "prompts" / "research_review.md").read_text(encoding="utf-8")
        workflow = WebResearchWorkflow(
            query_agent=ResearchQueryAgent(model=model, tools=tools, prompt=query_prompt, default_tool=default_tool),
            review_agent=ResearchReviewAgent(model=model, prompt=review_prompt), engines=engines,
        )
        # 在此打断点；可进入两个Agent，观察每轮搜索词和筛选反馈。
        result = await workflow.run(question=question, target_count=2, max_attempts=5)
    print("\n【用户问题】", question)
    print("【状态、次数、失败引擎】", result["status"], result["attempt"], result["failed_engines"])
    print("【用户可选动作】", result["user_options"])
    print("【最后一轮搜索词和检查反馈】", result["query"], result["feedback"])
    print("【候选结果】", json.dumps(result["accepted"], ensure_ascii=False, indent=2))
    assert result["status"] in {"completed", "awaiting_user"}, result["message"]


# 以下为同一文件中的离线流程检查，不调用真实模型或搜索服务。
class SampleQueryAgent:
    """记录搜索顺序与反馈，固定返回同一网页。"""
    has_default_tool = True

    def __init__(self):
        self.calls = []

    async def search(self, *, question, feedback, engine):
        self.calls.append((engine, feedback))
        return "搜索词", [{"candidate_id": "same", "url": "https://example.org/a", "title": "标题", "snippet": "摘要", "engines": [engine or "bing"]}]


class SampleReviewAgent:
    async def review(self, *, question, candidates):
        return SearchReview(relevant_ids=["same", "invented"], feedback="调整搜索词")


@pytest.mark.asyncio
async def test_default_first_then_named_and_user_choices():
    query = SampleQueryAgent()
    workflow = WebResearchWorkflow(query_agent=query, review_agent=SampleReviewAgent(), engines=("a", "b"))
    result = await workflow.run(question="示例", target_count=2, max_attempts=3)
    assert [call[0] for call in query.calls] == [None, "a", "b"]
    assert query.calls[1][1] == "调整搜索词"
    assert result["status"] == "awaiting_user" and len(result["accepted"]) == 1
    assert result["accepted"][0]["search_strategies"] == ["server_default", "a", "b"]
    assert workflow.apply_user_decision(result, "use_current")["status"] == "completed"
    assert workflow.apply_user_decision(result, "provide_materials")["status"] == "needs_materials"
    with pytest.raises(ValueError):
        workflow.apply_user_decision(result, "end_conversation")


@pytest.mark.asyncio
async def test_no_results_asks_for_materials_or_end():
    class EmptyQuery(SampleQueryAgent):
        async def search(self, *, question, feedback, engine):
            return "搜索词", []
    workflow = WebResearchWorkflow(query_agent=EmptyQuery(), review_agent=SampleReviewAgent(), engines=("a",))
    result = await workflow.run(question="示例", max_attempts=1)
    assert result["status"] == "awaiting_user" and not result["accepted"]
    assert result["user_options"] == ["provide_materials", "end_conversation"]
    assert workflow.apply_user_decision(result, "end_conversation")["status"] == "cancelled"
    assert workflow.apply_user_decision(result, "provide_materials")["status"] == "needs_materials"


@pytest.mark.asyncio
async def test_target_reached_stops_after_default():
    query = SampleQueryAgent()
    workflow = WebResearchWorkflow(query_agent=query, review_agent=SampleReviewAgent(), engines=("a",))
    result = await workflow.run(question="示例", target_count=1, max_attempts=3)
    assert result["status"] == "completed" and result["attempt"] == 1
    assert query.calls[0][0] is None


@pytest.mark.asyncio
async def test_default_search_does_not_send_engine_parameter():
    requests = []
    def respond(request):
        requests.append(request)
        return httpx.Response(200, json={"results": []})
    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        await SearxngSearchClient(client=client, base_url="http://localhost").search(query="测试", max_results=1)
    assert "engines" not in requests[0].url.params
    assert requests[0].url.params["categories"] == "general"


@pytest.mark.asyncio
async def test_all_engines_fail_still_offers_user_choice():
    class FailingQuery(SampleQueryAgent):
        async def search(self, *, question, feedback, engine):
            raise ToolException("搜索失败")
    workflow = WebResearchWorkflow(query_agent=FailingQuery(), review_agent=SampleReviewAgent(), engines=("a",))
    result = await workflow.run(question="示例", max_attempts=2)
    assert result["status"] == "awaiting_user"
    assert result["failed_engines"] == ["server_default", "a"]
    assert "全部失败" in result["message"]
