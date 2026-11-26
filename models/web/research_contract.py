"""资料收集的输入、两个子Agent结果和图状态。

BaseModel负责在返回后解析和校验模型输出。当前Agent使用json_mode，
字段结构需要在提示词中明确说明，不能假设Field描述已发送给模型。
TypedDict描述字典应有哪些字段，
仅提供类型提示，不会像Pydantic那样在运行时自动校验或创建对象。
"""

from typing import Literal, TypedDict

from pydantic import BaseModel, Field
from models.web.search_web_contract import WebSearchItem
from models.web.web_research_summary import WebPageExtractionRecord, WebResearchPage, WebResearchReadFailure
from models.web.research_report import ResearchReport


class SearchPlan(BaseModel):
    """模型生成、查询Agent使用的搜索计划；当前只有搜索词，不包含地址。"""

    # 必填；长度是字符数而不是token数。搜索词会发送给外部搜索服务。
    query: str = Field(min_length=1, max_length=200, description="适合搜索引擎的简短搜索词，保留用户需求中的关键实体和限定。")


class AlternativeCandidate(BaseModel):
    """主题相关但不满足明确要求的备用候选，由检查模型提出。"""

    candidate_id: str = Field(description="本轮搜索结果中真实存在的候选编号。")
    unmet_requirement: str = Field(min_length=1, description="该候选不满足的用户明确要求，例如不是官方来源。")


class SearchReview(BaseModel):
    """检查模型的结果；相关仅指摘要初筛，不表示事实或来源已核实。"""

    # 必填；无合适候选时为[]。工作流会再次检查ID是否属于本轮候选。
    relevant_ids: list[str] = Field(description="与用户要求直接相关的候选编号列表，不确定时排除。")
    # 备用候选仅供后续用户决定；不能自动当作符合原始要求的资料。
    alternatives: list[AlternativeCandidate] = Field(description="主题相关但不满足明确限定的候选及原因；没有时为空数组。")
    # 记录当前批次尚未满足的要求；不是对整个互联网的结论。
    unmet_requirements: list[str] = Field(description="本轮候选未满足的用户明确要求；没有时为空数组。")
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


class ResearchAlternative(ResearchCandidate):
    """备用候选：除网页信息外，保留各轮指出的不满足要求原因。"""

    unmet_reasons: list[str]  # 不重复的原因；仅表示摘要判断，不代表已核实正文。


class ResearchState(TypedDict):
    """一次研究流程的临时状态；调用者负责保管，不提供跨进程持久化。"""

    question: str  # 用户主题和要求。
    provided_urls_only: bool  # 用户明确提供网址时优先读取其同站链接，不自动扩展互联网搜索。
    defer_user_question: bool  # True时资料不足由上层判断，网页图不生成问题、不暂停；默认False。
    workflow_error_stage: str | None  # 图执行失败的节点名；无故障为None，不包含异常原文。
    workflow_error_kind: str | None  # 固定分类model_connection/model_timeout/execution_failed；无故障为None。
    target_count: int  # 期望有效网页来源数；不是保证找到的数量。
    max_attempts: int  # 搜索总次数上限，每轮由服务器选择引擎。
    max_pages: int  # 网页读取次数上限，包含失败。
    attempt: int  # 已尝试搜索总次数。
    query: str  # 当前实际搜索词。
    feedback: str  # 上一轮检查意见，提供给查询Agent。
    candidates: list[WebSearchItem]  # 当前轮搜索候选，含实际引擎列表。
    review_batches: list[list[WebSearchItem]]  # 本轮尚待检查的批次；超限时拆成更小批次。
    unreviewed: list[WebSearchItem]  # 单条检查仍超限的候选；不是无关结果，可能在后续轮次重新检查。
    review_timeout_candidates: list[WebSearchItem]  # 超时批次及本轮尚未检查的候选，不表示无关。
    accepted: list[ResearchCandidate]  # 跨轮去重后的初筛候选。
    alternatives: list[ResearchAlternative]  # 跨轮去重备用候选，不计入正式候选数量。
    selected_alternatives: list[ResearchAlternative]  # 用户明确选中的备用候选；仍不视为满足原要求的正式资料。
    read_index: int  # 下一条待读正式候选的下标；每次读取后写入检查点。
    pages: list[WebResearchPage]  # 已提炼网页的元数据，不含正文。
    page_extractions: list[WebPageExtractionRecord]  # 单页提炼要点与来源，供后续汇总；不含网页正文。
    needs_summary: bool  # 本页有新要点，需要重新检查累计要点。
    summary_deferred: bool  # True表示网页只交出单页提炼，由上层进行内容汇总和充分性判断。
    summary_length_exceeded: bool  # 累计汇总输出超限且未完成；之前的汇总和单页要点保留。
    read_failures: list[WebResearchReadFailure]  # 读取失败的网页和原因。
    summary: dict | None  # 上次成功汇总的JSON；尚无成功汇总时为None。
    effective_count: int  # 上次成功汇总实际引用的网页数；汇总失败时可能未包含最新单页。
    failed_attempts: int  # 整次搜索工具调用失败次数，不代表某个具体引擎失败。
    status: str  # running、completed、collected（上层汇总）、insufficient、awaiting_user、interrupted等。
    message: str  # 状态解释，不包含敏感上游错误原文。
    user_options: list[str]  # 等待用户决定时的可选动作；其余情况为空列表。
    waiting_question: dict | None  # 提问节点的稳定问题字段；等待时非空，回答后清空。
    # 图运行中为空字符串；运行结束由工作流_finalize填写主要停止原因：
    # target_reached：模型引用的网页来源数达到目标，且未报告明确缺口或内容问题。
    # search_limit：搜索轮次用完，仍未满足上述目标和缺口条件。
    # page_limit：网页读取次数用完（包含失败），仍未满足停止条件。
    # search_failed：本次所有搜索调用均失败，而非某一轮或某个引擎失败。
    # model_timeout：检查模型响应超时，本轮剩余候选未检查，已有结果保留。
    # summary_length_exceeded：累计汇总输出超限，最新单页要点尚未纳入汇总检查。
    # 同时满足多个原因时，优先报告模型超时，再判断目标、搜索失败和各项上限。
    # 这是内部状态，不自动传给模型；Literal只提供静态类型提示，不做运行时校验。
    stop_reason: Literal["", "target_reached", "search_limit", "page_limit", "search_failed", "provided_pages_exhausted", "summary_deferred", "model_timeout", "summary_length_exceeded", "workflow_error"]
    report: ResearchReport | None  # 程序生成的网页检查报告；图运行中为None，不含搜索feedback。
