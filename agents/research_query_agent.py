"""查询子Agent：生成搜索词，再调用宿主提供的搜索工具。"""

from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool

from diagnostics.operation_logging import log_operation
from models.web.research_contract import SearchPlan
from models.web.search_web_contract import WebSearchItem


class ResearchQueryAgent:
    """资料查询子Agent：让模型拟定搜索词，再调用宿主注入的搜索工具。

    注意：本类使用LangChain模型的结构化输出能力，但没有调用create_agent。
    宿主应注入不指定引擎的工具，具体搜索来源由SearXNG服务端决定。
    一次search只执行一次search_web工具，不判断结果是否准确或权威。
    """

    def __init__(self, *, model: BaseChatModel, tool: BaseTool, prompt: str) -> None:
        """保存模型、提示词和宿主组装好的工具；构造时不会请求模型或搜索。

        Args:
            model: 外层模型工厂创建的LangChain聊天模型；须支持JSON模式。
            tool: 宿主注入的搜索工具；实际流程应配置为不指定引擎。
            prompt: 外层从提示词文件读取的文字，说明如何构造搜索词。

        这里的*表示后续参数必须写成model=...这种关键字形式。
        网络连接和工具生命周期属于创建它们的外层调用方，本类不会关闭它们。
        """
        # 将模型回答按SearchPlan解析，便于后续通过plan.query读取搜索词。
        # 该设置要求模型代理支持JSON模式；格式无效时调用阶段会报错。
        self._planner = model.with_structured_output(SearchPlan, method="json_mode")
        self._tool = tool
        self._prompt = prompt

    @log_operation("agent.research_query")
    async def search(self, *, question: str, feedback: str) -> tuple[str, list[WebSearchItem]]:
        """执行一轮查询，返回搜索词和本轮候选网页。

        Args:
            question: 用户原始主题与限制，例如要求资料来自哪一年。
            feedback: 检查Agent对上一轮的意见；首轮传空字符串即可。

        Returns:
            (搜索词, 候选列表)二元组。候选包含编号、标题、URL和摘要；
            摘要来自搜索引擎，不是已经读取和核实的网页正文。

        Raises:
            ValueError: 模型返回类型无效。
            ToolException: 搜索工具报告失败，交给外层工作流决定是否重试。
            模型、网络及输出解析的其他异常继续向上传递，不伪装成空结果。
        """
        # await等待异步模型返回；不会在这里调用search_web以外的工具。
        plan = await self._planner.ainvoke(
            self._prompt + "\n用户要求：" + question + "\n上一轮反馈：" + (feedback or "无")
        )
        if not isinstance(plan, SearchPlan):
            raise ValueError("查询模型未返回有效的搜索词。")
        # ainvoke通过LangChain工具入口执行；5是每轮取回的候选上限，
        # 不是最终目标数量，也不是整个任务的搜索次数。
        result = await self._tool.ainvoke({"query": plan.query, "max_results": 5})
        return plan.query, result["items"]
