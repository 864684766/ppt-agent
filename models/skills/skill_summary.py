"""本地技能目录元数据，不导入技能代码，不保存完整技能正文。"""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SkillSummary:
    """目录适配器创建，业务筛选与工具输出使用的不可变技能摘要。"""

    # 内置skills目录下的一级文件夹名，作为技能定位编号；不是任意文件路径。
    skill_id: str
    # SKILL.md YAML头部的name；不根据正文猜测名称。
    name: str
    # YAML头部的description，保留多行用途说明；不代表专业能力已验证。
    description: str
    # 顶层version或metadata.version；两者均缺失时None，不生成虚构版本。
    version: str | None

