"""网页正文整理的结构化结果；候选编号仅关联本次搜索，不是资料库编号。"""

from typing import TypedDict

from pydantic import BaseModel, Field
from models.web.fetch_webpage_contract import FetchWebpageOutput


class WebSummaryPoint(BaseModel):
    """一条整理后的内容及支持它的网页候选编号。"""

    content: str = Field(min_length=1, description="根据网页正文整理的内容，不得编造。")
    candidate_ids: list[str] = Field(min_length=1, description="支持本条内容的网页候选编号。")


class WebFollowLink(BaseModel):
    """模型建议从已读取页面继续访问的链接。"""

    candidate_id: str = Field(description="包含此链接的已读取页面编号。")
    url: str = Field(description="该页面links中实际存在的链接地址。")


class WebResearchSummary(BaseModel):
    """正文整理结果；不表示已核实网页事实或完成最终PPT大纲。"""

    points: list[WebSummaryPoint] = Field(description="整理后的相关要点；无相关内容时为空列表。")
    gaps: list[str] = Field(description="根据已读取正文仍未满足的需求；没有时为空列表。")
    follow_links: list[WebFollowLink] = Field(description="已读页面中值得继续读取的链接；没有则为空。")


class WebResearchPage(FetchWebpageOutput):
    """网页正文与搜索候选的关联，正文可能因长度限制被截断。"""

    candidate_id: str  # 搜索候选编号，不是资料库source_id。


class WebResearchReadFailure(TypedDict):
    """一个候选未能读取正文的结果。"""

    candidate_id: str  # 失败的候选编号。
    url: str  # 本次请求的地址。
    reason: str  # 公开的读取失败说明；不代表网页一定不存在。



