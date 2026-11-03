"""search_web输入与公开输出；参数说明进入模型可见的JSON Schema。"""

from typing import TypedDict

from pydantic import BaseModel, ConfigDict, Field


class SearchWebInput(BaseModel):
    """仅开放当前适配器已支持的查询参数，不让模型选择供应商或密钥。"""

    model_config = ConfigDict(extra="forbid", strict=True, str_strip_whitespace=True)

    query: str = Field(min_length=1, max_length=1000, description=(
        "必填，1至1000字符的互联网搜索词，例如健康饮食 均衡膳食 每日食谱。"
        "用于发现主题资料的候选网页，不查询已上传文件，也不搜索PPT设计模板。"
        "不要把本地资料全文或密钥放入搜索词；查询会发送给外部搜索供应商。"
    ))
    max_results: int = Field(default=5, ge=1, le=10, description=(
        "最多返回的候选网页条数，1至10的整数，默认5；例如填3最多返回3条。"
        "供应商可能返回更少结果；不是检索轮数，不会自动翻页或重试。"
    ))


class WebSearchItem(TypedDict):
    """公开候选网页；TypedDict只描述结构，不自动执行运行时校验。"""

    # 候选网页编号，web_加URL的SHA-256；不是source_id，不可传给read_material。
    candidate_id: str
    # 候选网页标题，由搜索供应商提供。
    title: str
    # 候选网页地址，后续抓取正文时使用，不是本地路径。
    url: str
    # 搜索摘要，可能为空；不代表已抓取或核实原网页。
    snippet: str


class SearchWebOutput(TypedDict):
    """returned_count为本次返回条数，不是全网结果总量。"""

    # 本次实际使用的搜索词，已去除首尾空白。
    query: str
    # 本次返回的候选网页列表，每项是WebSearchItem；无候选时为空列表。
    items: list[WebSearchItem]
    # 本次items条数，可能小于max_results；不是互联网结果总数。
    returned_count: int
