"""隔离目录扫描方式；未来其他技能来源可提供同样的元数据。"""

from typing import Protocol

from models.skills.skill_summary import SkillSummary


class SkillCatalogError(RuntimeError):
    """目录不可用的安全错误，不包含本机绝对路径或文件原文。"""


class SkillCatalog(Protocol):
    """提供一次本地技能元数据快照，不负责安装、启用或执行技能。"""

    def load(self) -> tuple[SkillSummary, ...]:
        """返回成功读取介绍的技能；单个无效目录由实现记录日志并忽略。
        根目录不可用时抛SkillCatalogError。"""
        ...
