"""解析SKILL.md YAML头部；只读取数据，不执行技能正文或导入技能模块。"""

from collections.abc import Mapping

import yaml

from models.skills.skill_summary import SkillSummary


def parse_skill_metadata(header: str, *, skill_id: str) -> SkillSummary:
    """解析必需name/description及可选版本，忽略不属于发现工具的其他字段。

    使用safe_load，不构造YAML自定义Python对象。无效结构抛ValueError，
    不把包含文件原文的YAML异常交给调用方。多行description按YAML语义保留。
    """
    try:
        metadata = yaml.safe_load(header)
    except yaml.YAMLError:
        raise ValueError("SKILL.md头部不是有效YAML。") from None
    if not isinstance(metadata, Mapping):
        raise ValueError("SKILL.md头部必须是字段映射。")
    name = metadata.get("name")
    description = metadata.get("description")
    if not isinstance(name, str) or not name.strip():
        raise ValueError("SKILL.md缺少非空字符串name。")
    if not isinstance(description, str) or not description.strip():
        raise ValueError("SKILL.md缺少非空字符串description。")
    nested = metadata.get("metadata")
    version = metadata.get("version")
    if version is None and isinstance(nested, Mapping):
        version = nested.get("version")
    # 版本不属于技能介绍的必需字段：无法识别则忽略，不因此拒绝name/description。
    valid_version = isinstance(version, (str, int, float)) and not isinstance(version, bool)
    version_text = str(version).strip() if valid_version else None
    return SkillSummary(
        skill_id=skill_id, name=name.strip(), description=description.strip(),
        version=version_text or None,
    )
