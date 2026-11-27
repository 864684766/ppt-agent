"""资料收集图的进程内状态；不作为HTTP公开契约。"""

from typing import Any, TypedDict

from models.web.research_report import ResearchReport


class MaterialCollectionReport(TypedDict):
    """上层整合的来源报告；模型问题不表示事实核验。"""

    web: ResearchReport | None  # 网页收集报告；阶段失败前未产生时为None。
    file: dict[str, Any] | None  # FileProcessingReport字典；未提供文件或异常未产生时为None。
    source_count: int | None  # 最终要点实际引用的来源数量；图故障未能计算时为None。
    target_source_count: int  # 调用方配置的目标来源数量。
    issues: list[dict[str, Any]]  # 通用汇总模型的缺口、冲突、版本或来源问题。


class MaterialCollectionState(TypedDict):
    """图节点通过字典读写状态，原始附件只保存在当前进程检查点。"""

    question: str  # 用户需求。
    prior_topic: str  # 初始需求，用来解释本轮追加要求；首轮为空。
    prior_inputs: list[dict[str, Any]]  # 上一轮累计的提炼要点和引用；不包含文件字节或网页原文。
    prior_pages: list[dict[str, Any]]  # 之前已读网页的公开来源元数据，用于跨轮还原引用。
    file_sources: dict[str, str]  # 累计文件来源编号与文件名，用于区分多个附件的块编号。
    file_source_id: str | None  # 本轮附件来源编号；无新附件时为空。
    allow_web: bool | None  # False明确禁止联网；None由需求分析判断。
    analysis: dict[str, Any] | None  # 最近一次需求分析结果，失败时不包含计划。
    question_kind: str | None  # clarification为需求澄清；materials为资料不足询问。
    use_current: bool  # 用户已明确选择现有资料时为True；允许在资料不足时形成大纲。
    file_name: str | None  # 可选附件文件名；没有附件时为None。
    file_content: bytes | None  # 附件字节，仅内存；不写日志或对外返回。
    target_count: int  # 搜索阶段的收集目标，不是交付大纲的最低来源数。
    web: dict[str, Any] | None  # 网页流程结果，包含提炼要点和报告。
    file: dict[str, Any] | None  # 单文件提炼结果；没有附件时为None。
    summary: dict[str, Any] | None  # 通用汇总；无要点或失败时为None。
    summary_inputs: list[dict[str, Any]]  # 汇总输入及来源，供还原引用。
    outline: dict[str, Any] | None  # 生成成功的分页大纲；未生成或失败时为None。
    outline_error: str | None  # 最终汇总及大纲生成失败的安全分类；未失败时为None。
    status: str  # running/completed/awaiting_user/interrupted/needs_materials/cancelled。
    message: str  # 给调用方的状态说明，不包含异常原文。
    report: MaterialCollectionReport | None  # 来源阶段报告、数量和内容问题。
    waiting_question: dict[str, Any] | None  # 预先生成的问题，供ask_user恢复时使用。
