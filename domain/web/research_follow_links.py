"""将已确认属于网页的链接转换成后续可读取的同站候选。"""

from hashlib import sha256
from urllib.parse import urlsplit

from models.web.fetch_webpage_contract import FetchWebpageOutput
from models.web.research_contract import ResearchCandidate
from models.web.web_research_summary import WebFollowLink


def select_followup_candidates(*, page: FetchWebpageOutput, follow_links: list[WebFollowLink],
                               accepted: list[ResearchCandidate]) -> list[ResearchCandidate]:
    """只保留页面中的同站链接，按完整URL去重；不请求网络或核实文章内容。"""
    existing = {item["url"] for item in accepted}
    origin_host = urlsplit(page["final_url"]).hostname
    result: list[ResearchCandidate] = []
    for follow in follow_links:
        url = follow.url
        link = next(link for link in page["links"] if link["url"] == url)
        if url in existing or urlsplit(url).hostname != origin_host:
            continue
        result.append({"candidate_id": "web_" + sha256(url.encode()).hexdigest(), "url": url,
                       "title": link["text"], "snippet": "", "engines": [],
                       "search_strategies": ["site_link"]})
        existing.add(url)
    return result
