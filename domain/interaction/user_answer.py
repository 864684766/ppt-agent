"""校验用户回答，不依赖LangGraph或具体业务。"""

from models.interaction.user_question import UserQuestion


def validate_user_answer(*, question: UserQuestion, question_id: str, answer: str) -> str:
    """核对问题编号及回答方式，返回去除首尾空白的答案；无效时抛ValueError。

    仅选项问题要求答案与选项文字完全相同；允许自由输入时接受非空文字。
    本函数不保存状态，不处理文件或网址，也不自动替用户作决定。
    """
    if question_id != question.question_id:
        raise ValueError("回答的问题编号与当前等待的问题不一致。")
    if not isinstance(answer, str) or not answer.strip():
        raise ValueError("用户回答不能为空。")
    value = answer.strip()
    if not question.allow_free_text and value not in question.options:
        raise ValueError("请从当前问题提供的选项中选择。")
    return value
