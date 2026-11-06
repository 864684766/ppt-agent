"""隔离产物检查实现；工具仅选择编号，不关心文件系统和PPT解析库。"""

from typing import Protocol
from models.presentations.check_presentation_contract import CheckPresentationOutput


class PresentationCheckError(RuntimeError):
    """无法定位或读取登记文件的安全错误；不包含路径、正文或SDK异常原文。"""


class PresentationChecker(Protocol):
    """文件不合格返回报告，编号无效或IO失败才抛PresentationCheckError。"""

    def check(self, *, artifact_id: str) -> CheckPresentationOutput:
        """只读检查宿主登记的PPTX，不修复、生成、覆盖或渲染文件。

        宿主负责登记及注入检查策略；实现关闭自己打开的文件，不缓存用户内容。
        未实现的规则明确not_checked；通过可执行规则不等于内容准确或视觉正常。
        """
        ...
