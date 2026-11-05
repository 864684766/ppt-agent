"""隔离PPTX结构提取实现，便于工具复用或更换解析器。"""

from typing import Protocol

from models.templates.template_structure import TemplateStructure


class TemplateInspectionError(RuntimeError):
    """可公开的模板读取错误，不包含本机路径或上游异常原文。"""


class TemplateInspector(Protocol):
    """宿主绑定可读模板；本协议不负责上传、页面角色判断或生成。"""

    def inspect(self, *, template_id: str) -> TemplateStructure:
        """返回模板结构事实；标识无效或解析失败时抛TemplateInspectionError。"""
        ...
