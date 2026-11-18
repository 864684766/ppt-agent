"""多引擎资料收集的输入、两个子Agent结果和图状态。

BaseModel负责在返回后解析和校验模型输出。当前Agent使用json_mode，
字段结构需要在提示词中明确说明，不能假设Field描述已发送给模型。
TypedDict描述字典应有哪些字段，
仅提供类型提示，不会像Pydantic那样在运行时自动校验或创建对象。
"""

from typing import TypedDict

from pydantic import BaseModel, Field
from models.web.search_web_contract import WebSearchItem


class SearchPlan(BaseModel):
    """模型生成、查询Agent使用的搜索计划；当前只有搜索词，不包含地址。"""

    # 必填；长度是字符数而不是token数。搜索词会发送给外部搜索服务。
    query: str = Field(min_length=1, max_length=200, description="适合搜索引擎的简短搜索词，保留用户需求中的关键实体和限定。")


class SearchReview(BaseModel):
    """检查模型的结果；相关仅指摘要初筛，不表示事实或来源已核实。"""

    # 必填；无合适候选时为[]。工作流会再次检查ID是否属于本轮候选。
    relevant_ids: list[str] = Field(description="与用户要求直接相关的候选编号列表，不确定时排除。")
    # 必填；用于下轮改词，工作流会截取前300个字符避免输入持续变长。
    feedback: str = Field(description="给查询Agent的反馈，说明不足或下一次可尝试的方向。")


class ResearchCandidate(TypedDict):
    """经标题和摘要初筛的候选；不是已核实的正文资料。"""

    candidate_id: str  # 源自URL的稳定编号。
    title: str  # 搜索引擎给出的网页标题。
    url: str  # 原始网页地址；按完整URL去重，不移除查询参数。
    snippet: str  # 搜索摘要，不是正文。
    engines: list[str]  # 搜索服务报告的实际来源引擎；未知时为空。
    search_strategies: list[str]  # 查询时使用的策略，server_default不是实际引擎名称。


class ResearchState(TypedDict):
    """一次研究流程的临时状态；调用者负责保管，不提供跨进程持久化。"""

    question: str  # 用户主题和要求。
    target_count: int  # 期望候选数量；不是保证找到的数量。
    max_attempts: int  # 搜索总次数上限，包含第一次服务器默认搜索。
    attempt: int  # 已尝试搜索总次数。
    engine: str  # 当前引擎名称；server_default表示由服务器选择。
    query: str  # 当前实际搜索词。
    feedback: str  # 上一轮检查意见，提供给查询Agent。
    candidates: list[WebSearchItem]  # 当前轮搜索候选，含实际引擎列表。
    accepted: list[ResearchCandidate]  # 跨轮去重后的初筛候选。
    failed_engines: list[str]  # 搜索出错的引擎，可重复；server_default表示兜底失败。
    status: str  # running、completed、awaiting_user、needs_materials、cancelled或failed。
    message: str  # 状态解释，不包含敏感上游错误原文。
    user_options: list[str]  # 等待用户决定时的可选动作；其余情况为空列表。
