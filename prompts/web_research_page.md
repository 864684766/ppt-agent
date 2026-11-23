这是单页提炼。只返回 JSON：

{
  "points": [{"content": "要点", "candidate_ids": ["本页编号"]}],
  "follow_links": [{"candidate_id": "本页编号", "url": "本页链接"}]
}

每页最多提炼 8 条精简要点；没有则返回空数组。
仅在有必要补充资料时选择最多 3 个本页 links 中的相关链接。
