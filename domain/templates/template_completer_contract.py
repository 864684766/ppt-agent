"""模板补全的依赖边界；实现、配置和Agent框架由外层负责。"""

from typing import Protocol

from models.templates.complete_template_contract import CompleteTemplateOutput, TemplatePagePlan


class TemplateCompletionError(RuntimeError):
    """无法补全或保存模板时抛出，只携带可公开的安全说明。"""


class TemplateCompleter(Protocol):
    """根据明确计划创建新模板；原文件保留，失败不返回成功报告。"""

    def complete(self, *, template_id: str, target_slide_count: int, pages: list[TemplatePagePlan]) -> CompleteTemplateOutput: ...
