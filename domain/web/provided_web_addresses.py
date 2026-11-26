"""从用户消息提取明确提供的网页地址，不发起网络请求。"""

import re
from hashlib import sha256
from urllib.parse import urlsplit

from models.web.research_contract import ResearchCandidate


def provided_web_candidates(question: str) -> list[ResearchCandidate]:
    """保留有效HTTP(S)地址并按完整地址去重；不是搜索或正文相关性判断。"""
    candidates: list[ResearchCandidate] = []
    seen: set[str] = set()
    for match in re.finditer(r'https?://[^\s<>"\'，。！？、）】]+', question, flags=re.IGNORECASE):
        url = match.group().rstrip('.,;:!?)]}，。！？；：）】')
        try:
            parts = urlsplit(url)
            if not parts.hostname or parts.username or parts.password or url in seen or len(url) > 4096:
                continue
        except ValueError:
            continue
        seen.add(url)
        candidates.append({"candidate_id": "web_" + sha256(url.encode()).hexdigest(), "url": url,
                           "title": "用户提供的网页", "snippet": "", "engines": [],
                           "search_strategies": ["user_provided"]})
    return candidates
