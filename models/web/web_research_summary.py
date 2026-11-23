"""网页正文整理的结构化结果；候选编号仅关联本次搜索，不是资料库编号。"""

from typing import Literal, TypedDict

from pydantic import BaseModel, Field


class WebSummaryPoint(BaseModel):
    """一条整理后的内容及支持它的网页候选编号。"""

    content: str = Field(min_length=1, description="根据网页正文整理的内容，不得编造。")
    candidate_ids: list[str] = Field(min_length=1, description="支持本条内容的网页候选编号。")


class WebFollowLink(BaseModel):
    """模型建议从已读取页面继续访问的链接。"""

    candidate_id: str = Field(description="包含此链接的已读取页面编号。")
    url: str = Field(description="该页面links中实际存在的链接地址。")


class WebContentIssue(BaseModel):
    """模型根据已提炼内容发现的问题；不能当作已经核实的事实。"""

    type: Literal["content_gap", "source_conflict", "version_issue", "source_requirement"] = Field(description="问题类别：内容缺失、来源冲突、版本问题或来源要求。")
    message: str = Field(min_length=1, description="面向用户解释问题及需要补充或核实的内容。")
    candidate_ids: list[str] = Field(description="涉及的真实网页编号；整体缺口可为空。")


class WebPageExtraction(BaseModel):
    """单篇网页的提炼结果，后续汇总使用要点而非再次发送正文。"""

    points: list[WebSummaryPoint] = Field(description="仅依据本页正文提炼的相关要点。")
    follow_links: list[WebFollowLink] = Field(description="本页值得跟进的真实链接。")


class WebResearchSummary(BaseModel):
    """正文整理结果；不表示已核实网页事实或完成最终PPT大纲。"""

    points: list[WebSummaryPoint] = Field(description="整理后的相关要点；无相关内容时为空列表。")
    gaps: list[str] = Field(description="根据已读取正文仍未满足的需求；没有时为空列表。")
    follow_links: list[WebFollowLink] = Field(description="已读页面中值得继续读取的链接；没有则为空。")
    issues: list[WebContentIssue] = Field(description="内容缺失、冲突、版本和来源要求的问题；没有时为空。")


class WebResearchPage(TypedDict):
    """已经提炼的网页元数据，不保存网页正文。"""

    candidate_id: str  # 搜索候选编号，不是资料库source_id。
    requested_url: str  # 请求的地址。
    final_url: str  # 跳转后的最终地址，用于确定性去重。
    title: str  # 网页标题。
    truncated: bool  # 本次提取的文字是否因长度限制被截断。
    returned_chars: int  # 发送给提炼模型的字符数。
    extracted_chars: int  # 读取器提取到的字符数。
    fetched_at: str  # 读取时间，UTC。
    text_hash: str  # 本次返回正文的SHA-256，用于精确去重，不保存正文。


class WebPageExtractionRecord(TypedDict):
    """成功处理一篇网页后保存的来源信息及单页要点。"""

    candidate_id: str  # 本次候选编号，与网页元数据关联。
    title: str  # 网页标题，供汇总时理解来源。
    url: str  # 最终网页地址，不保证来源权威。
    truncated: bool  # 单页提炼是否只看到了截断后的正文。
    points: list[dict]  # WebSummaryPoint序列化后的要点列表，可为空。


class WebResearchReadFailure(TypedDict):
    """一个候选未能读取正文的结果。"""

    candidate_id: str  # 失败的候选编号。
    url: str  # 本次请求的地址。
    reason: str  # 公开的读取失败说明；不代表网页一定不存在。



