"""check_presentation的模型可见输入及公开检查报告；TypedDict不自动校验。"""

from typing import Literal, TypedDict

from pydantic import BaseModel, ConfigDict, Field


class CheckPresentationInput(BaseModel):
    """模型仅选择已登记产物，不能传本机路径或降低宿主检查要求。"""

    model_config = ConfigDict(extra="forbid", strict=True, str_strip_whitespace=True)
    artifact_id: str = Field(min_length=1, max_length=200, description=(
        "必填，宿主提供的PPTX产物编号，例如demo-presentation；不是URL、文件路径或模板编号。"
        "只能检查本次宿主登记的文件，一次返回整份报告。页数要求与大小限额由宿主设定，不能通过工具参数修改。"
    ))


class PresentationCheckItem(TypedDict):
    """一条规则的结果，由检查器创建；不放正文或内部路径。"""

    # 稳定规则名称，如package_structure、page_count，用于识别具体检查项。
    rule_id: str
    # pass通过、fail不满足、warning需关注、not_checked未检查（含前置失败）。
    status: Literal["pass", "fail", "warning", "not_checked"]
    # 是否为本轮必须通过的规则；只能由宿主/实现决定，不能由模型关闭。
    required: bool
    # 安全中文结论，解释失败或未检查原因，不包含SDK原始异常或正文。
    message: str
    # 当前规则预期：数值范围说明或要求文本；无需期待每条均为同一类型。
    expected: str | None
    # 实际数值、状态说明或问题页码；未取得事实时None，不以0伪装未知。
    actual: int | str | list[int] | None
    # 对应真实幻灯片序号，从1开始；文件级规则或无问题时为空列表。
    slide_numbers: list[int]


class CheckPresentationOutput(TypedDict):
    """宿主检查器返回、工具公开的报告；不等于PowerPoint真实打开验收。"""

    # 回显本次检查的登记编号；不是全局项目、会话或持久化产物系统。
    artifact_id: str
    # 仅展示文件名，不暴露宿主绝对路径。
    file_name: str
    # 本次实际读取字节的SHA-256；文件超限未完整读取时None。
    sha256: str | None
    # PPT解析成功后的实际页数；包校验/解析失败时None。
    slide_count: int | None
    # 仅当所有required规则为pass时True；不代表未检查项目也通过。
    passed: bool
    # 已读全部字节时为实际大小，超限中止时None；文件大小规则仍解释超限。
    size_bytes: int | None
    # 固定顺序规则结果，失败后不能执行的检查标not_checked，不伪造通过。
    checks: list[PresentationCheckItem]
