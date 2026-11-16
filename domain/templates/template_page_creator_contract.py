"""页面创建协议及安全错误；不依赖LangChain或文件路径。"""

from typing import Protocol

from models.templates.create_template_page_contract import CreateTemplatePageOutput, PageElement


class TemplatePageCreationError(RuntimeError):
    """设计方案无法执行，或模板读取保存失败。"""


class TemplatePageCreator(Protocol):
    def create(self, *, template_id: str, layout_id: str, background_color: str,
               elements: list[PageElement]) -> CreateTemplatePageOutput:
        """按明确方案追加一页，返回新文件信息。"""
        ...
