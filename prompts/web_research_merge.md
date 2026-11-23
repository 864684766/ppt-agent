这是跨网页汇总，只使用下方单页要点，不要假装看到了正文。合并重复要点时保留支持该要点的全部来源编号。

只返回 JSON：

{
  "points": [{"content": "要点", "candidate_ids": ["网页编号"]}],
  "gaps": ["明确缺口"],
  "follow_links": [],
  "issues": [{
    "type": "content_gap|source_conflict|version_issue|source_requirement",
    "message": "问题及需补充或核实的内容",
    "candidate_ids": ["相关网页编号"]
  }]
}

每个 issue 的 type 必须从 content_gap、source_conflict、version_issue、source_requirement 中选择一个值。
仅对用户明确要求或资料中实际可见的冲突、版本及来源问题作判断；无法确认时明确说明。
全局缺口的 candidate_ids 可为空；没有问题时 issues 为空。gaps 仅列影响用户明确要求的重要缺口。
