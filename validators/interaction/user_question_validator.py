"""提问内容的共享约束，工具边界和内部实体使用同一套规则。"""

from collections.abc import Sequence


# 长度限制只在这里定义；Schema字段与实体校验引用相同数值，避免两边不一致。
MAX_QUESTION_CHARS = 2000
MAX_REASON_CHARS = 1000
MAX_OPTIONS = 10
MAX_OPTION_CHARS = 300


def validate_user_question(
    *, question: str, reason: str, options: Sequence[str], allow_free_text: bool,
) -> None:
    """检查普通字段值，不修改、不保存数据；不符合约束时抛安全的ValueError。

    options为空表示开放问题，此时必须允许自由输入。选项不允许重复，避免用户
    无法区分两个相同选择。中文、换行均按Python字符数计算，不是UTF-8字节数。
    """
    for name, value, limit in (
        ("问题", question, MAX_QUESTION_CHARS), ("提问原因", reason, MAX_REASON_CHARS),
    ):
        if not isinstance(value, str) or not value.strip() or len(value) > limit:
            raise ValueError(f"{name}必须为非空文字，且不超过{limit}个字符。")
    if type(allow_free_text) is not bool:
        raise ValueError("是否允许自由输入必须为布尔值。")
    if isinstance(options, (str, bytes)) or len(options) > MAX_OPTIONS:
        raise ValueError(f"选项必须为序列，且不超过{MAX_OPTIONS}项。")
    if any(not isinstance(item, str) or not item.strip() or len(item) > MAX_OPTION_CHARS for item in options):
        raise ValueError(f"每个选项必须为非空文字，且不超过{MAX_OPTION_CHARS}个字符。")
    if len({item.strip() for item in options}) != len(options):
        raise ValueError("选项不能重复。")
    if not options and not allow_free_text:
        raise ValueError("没有选项时必须允许自由输入。")
