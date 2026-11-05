"""人工提问的预留输入/输出定义；尚无ask_user工具或实际交互流程。

保留字段供后续接入时讨论，Pydantic校验仍可独立使用；这些类型不会自行执行
提问、保存、暂停或回答，最终运行时契约可根据实际工作流调整。
"""

from typing import Annotated, Literal, Self, TypedDict

from pydantic import BaseModel, ConfigDict, Field, model_validator

from validators.interaction.user_question_validator import (
    MAX_OPTION_CHARS, MAX_OPTIONS, MAX_QUESTION_CHARS, MAX_REASON_CHARS,
    validate_user_question,
)


class AskUserInput(BaseModel):
    """预留的提问内容结构；不接受问题编号、用户答案或任意任务状态。"""

    model_config = ConfigDict(extra="forbid", strict=True, str_strip_whitespace=True)

    question: str = Field(min_length=1, max_length=MAX_QUESTION_CHARS, description=(
        "必填，向用户提出的明确问题，1–2000字符。例如：模板缺少来源页，你希望如何处理？"
        "一次围绕一个待决定事项，不替用户回答。"
    ))
    reason: str = Field(min_length=1, max_length=MAX_REASON_CHARS, description=(
        "必填，说明为什么需要用户决定，1–1000字符。"
        "例如：最终PPT需要列出资料来源，当前模板没有对应页面。只写简短理由，不输出内部思考全文。"
    ))
    options: list[Annotated[str, Field(min_length=1, max_length=MAX_OPTION_CHARS)]] = Field(
        default_factory=list, max_length=MAX_OPTIONS, description=(
            "可选，按展示顺序提供0–10个不同选项，每项1–300字符，不含空白选项。"
            "例如：[沿用内容页样式制作来源页, 由我补传模板]。默认空列表表示开放问题，"
            "此时allow_free_text必须为true。"
        ),
    )
    allow_free_text: bool = Field(default=True, description=(
        "可选，是否允许用户自行输入答案，默认true。false表示仅允许选择所列选项，"
        "此时options不能为空。本参数只声明回答方式，不代表已接入前端或收到用户回答。"
    ))

    @model_validator(mode="after")
    def validate_question_content(self) -> Self:
        """字段解析后检查组合约束；与实体共用规则，不在这里保存或提交问题。"""
        validate_user_question(
            question=self.question, reason=self.reason,
            options=self.options, allow_free_text=self.allow_free_text,
        )
        return self


class AskUserOutput(TypedDict):
    """预留的提交结果结构，当前没有代码产出；TypedDict不自动执行校验。"""

    # 预留问题关联编号，由未来实际接入方生成，与UserQuestion.question_id对应。
    question_id: str
    # 预留waiting_for_user语义为尚待回答；此类型存在不表示已提交或实现运行时暂停。
    status: Literal["waiting_for_user"]
