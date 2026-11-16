"""PPT生成的依赖边界，不绑定文件系统或Agent框架。"""

from typing import Protocol

from models.presentations.build_presentation_contract import BuildPresentationOutput, PresentationPagePlan


class PresentationBuildError(RuntimeError):
    """制作计划无法执行或文件生成失败；只携带可公开的安全说明。"""


class PresentationBuilder(Protocol):
    def build(self, *, template_id: str, pages: list[PresentationPagePlan]) -> BuildPresentationOutput:
        """按确认的页面计划生成新PPTX。"""
        ...
