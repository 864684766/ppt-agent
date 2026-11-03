"""搜索得到的候选网页；不是已经登记并解析的业务资料。"""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class WebSearchCandidate:
    """候选标识用于比较搜索结果，不能当成资料目录中的source_id。

    snippet是搜索供应商给出的摘要，可能为空，不代表网页完整正文。
    candidate_id由适配器根据URL生成，不意味着已经保存网页或创建Store。
    """

    # 候选网页标识，由URL生成；不能当成已登记资料的source_id。
    candidate_id: str
    # 搜索供应商返回的网页标题，不代表已核实内容。
    title: str
    # 候选网页的HTTP/HTTPS地址，供后续选择抓取。
    url: str
    # 供应商返回的搜索摘要，可为空；不是完整网页正文。
    snippet: str
