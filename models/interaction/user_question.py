"""人工提问的预留数据实体；当前没有提交、保存或回答实现。"""

from dataclasses import dataclass

from validators.interaction.user_question_validator import validate_user_question


@dataclass(frozen=True)
class UserQuestion:
    """描述问题内容的不可变数据，供后续真实人工交互接入时讨论复用。

    frozen=True禁止直接修改字段；options使用tuple，避免调用者在提交后追加选项。
    本类不保存回答，不自动暂停执行，也不是持久化任务或会话。
    """

    # 由未来接入方分配的非空问题编号，不限制为UUID；唯一性由实际接收方保证。
    question_id: str
    # 向用户展示的明确问题，1–2000字符；不得假设用户知道内部对象编号。
    question: str
    # 为什么需要用户决定，1–1000字符；应是简短业务理由，不是模型思考全文。
    reason: str
    # 按展示顺序保存的0–10项选项，每项1–300字符；空元组表示开放问题。
    options: tuple[str, ...]
    # True表示用户可自行输入答案；False表示仅从非空选项中选择，不代表已实现前端。
    allow_free_text: bool

    def __post_init__(self) -> None:
        """构造实体时检查字段；保留的数据定义可以脱离未来工具入口独立使用。"""
        if not isinstance(self.question_id, str) or not self.question_id.strip():
            raise ValueError("问题编号必须为非空字符串。")
        if not isinstance(self.options, tuple):
            raise ValueError("内部问题选项必须为不可变元组。")
        validate_user_question(
            question=self.question, reason=self.reason,
            options=self.options, allow_free_text=self.allow_free_text,
        )
