"""合并每轮检查通过的网页候选，使用完整URL做确定性去重。"""

from models.web.research_contract import ResearchAlternative, ResearchCandidate, SearchReview
from models.web.search_web_contract import WebSearchItem


def merge_research_candidates(
    *, accepted: list[ResearchCandidate], alternatives: list[ResearchAlternative],
    candidates: list[WebSearchItem], review: SearchReview, strategy: str,
) -> tuple[list[ResearchCandidate], list[ResearchAlternative]]:
    """返回新的正式池和备用池，不修改传入列表或其中的对象。

    candidates是本轮搜索结果；review的编号只与本轮数据匹配，虚构编号忽略。
    strategy记录本轮搜索策略；实际引擎来自候选的engines。按完整URL去重，
    不剥离查询参数或猜测不同网址是否是转载。若同一网址先是备用、后被判为
    正式，则升级到正式并保留来源；已是正式的不会被后续备用判断降级。
    备用原因跨轮去重累积；这些判断基于摘要，不代表网页内容已经核实。
    """
    # 深复制列表：LangGraph节点不应就地改变传入状态中的嵌套数据。
    formal = [ResearchCandidate(candidate_id=x["candidate_id"], title=x["title"], url=x["url"],
              snippet=x["snippet"], engines=list(x["engines"]),
              search_strategies=list(x["search_strategies"])) for x in accepted]
    backup = [ResearchAlternative(candidate_id=x["candidate_id"], title=x["title"], url=x["url"],
              snippet=x["snippet"], engines=list(x["engines"]), search_strategies=list(x["search_strategies"]),
              unmet_reasons=list(x["unmet_reasons"])) for x in alternatives]
    formal_by_url = {item["url"]: item for item in formal}
    backup_by_url = {item["url"]: item for item in backup}
    formal_ids = set(review.relevant_ids)
    reasons = {item.candidate_id: item.unmet_requirement for item in review.alternatives}

    for item in candidates:
        candidate_id = item["candidate_id"]
        is_formal = candidate_id in formal_ids
        reason = reasons.get(candidate_id)
        if not is_formal and reason is None:
            continue
        current = _select_candidate(item, is_formal=is_formal, reason=reason, formal=formal, backup=backup,
                                    formal_by_url=formal_by_url, backup_by_url=backup_by_url)
        for engine in item["engines"]:
            if engine not in current["engines"]:
                current["engines"].append(engine)
        if strategy not in current["search_strategies"]:
            current["search_strategies"].append(strategy)
    return formal, backup


def _select_candidate(item: WebSearchItem, *, is_formal: bool, reason: str | None,
                      formal: list[ResearchCandidate], backup: list[ResearchAlternative],
                      formal_by_url: dict[str, ResearchCandidate],
                      backup_by_url: dict[str, ResearchAlternative]) -> ResearchCandidate:
    """按URL选取或创建候选；必要时将备用候选提升为正式候选。"""
    url = item["url"]
    current = formal_by_url.get(url)
    if current is None and is_formal:
        previous = backup_by_url.pop(url, None)
        if previous is not None:
            backup.remove(previous)
            current = ResearchCandidate(candidate_id=previous["candidate_id"], title=previous["title"],
                url=previous["url"], snippet=previous["snippet"], engines=list(previous["engines"]),
                search_strategies=list(previous["search_strategies"]))
        else:
            current = ResearchCandidate(candidate_id=item["candidate_id"], title=item["title"], url=url,
                snippet=item["snippet"], engines=[], search_strategies=[])
        formal.append(current)
        formal_by_url[url] = current
    if current is not None:
        return current
    alternative = backup_by_url.get(url)
    if alternative is None:
        alternative = ResearchAlternative(candidate_id=item["candidate_id"], title=item["title"], url=url,
            snippet=item["snippet"], engines=[], search_strategies=[], unmet_reasons=[])
        backup.append(alternative)
        backup_by_url[url] = alternative
    if reason and reason not in alternative["unmet_reasons"]:
        alternative["unmet_reasons"].append(reason)
    return alternative
