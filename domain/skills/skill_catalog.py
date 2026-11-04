"""纯技能摘要筛选，不依赖文件系统、YAML、配置或LangChain。"""

from collections.abc import Sequence

from models.skills.skill_summary import SkillSummary


def filter_skills(skills: Sequence[SkillSummary], *, keyword: str = "") -> tuple[SkillSummary, ...]:
    """按编号、名称、说明字面匹配并排序；不做语义或专业能力判断。

    keyword去首尾空白，大小写不敏感；空关键词返回全部，非法参数抛ValueError。
    不改变原摘要，也不把筛选结果登记成新的Store。
    """
    if not isinstance(keyword, str) or len(keyword.strip()) > 200:
        raise ValueError("keyword必须为不超过200字符的字符串。")
    term = keyword.strip().casefold()
    return tuple(sorted(
        (item for item in skills if not term or any(
            term in value.casefold() for value in (item.skill_id, item.name, item.description)
        )), key=lambda item: item.skill_id,
    ))
