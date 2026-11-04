"""技能正文读取边界；工具不依赖文件系统或未来市场的具体实现。"""

from typing import Protocol


class SkillReadError(RuntimeError):
    """技能读取失败；消息可公开，不包含本机路径或文件原文。"""


class SkillReader(Protocol):
    """根据技能编号读取入口文本，不解释执行步骤或运行代码。"""

    def read(self, *, skill_id: str) -> str:
        """返回完整SKILL.md文本；不存在、不规范或不可读取时抛SkillReadError。"""
        ...
