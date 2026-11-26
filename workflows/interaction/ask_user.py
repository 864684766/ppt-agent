"""LangGraph内通用的人工询问：暂停并取得用户真实回答。"""

from dataclasses import asdict

from langgraph.types import interrupt

from domain.interaction.user_answer import validate_user_answer
from models.interaction.user_question import UserQuestion


def ask_user(question: UserQuestion) -> str:
    """暂停当前LangGraph节点，恢复后校验并返回用户回答。

    question由调用方在进入节点前创建并保存在图状态中，编号在恢复时必须稳定。
    interrupt把可序列化的问题发送给宿主；宿主展示后用Command(resume=...)传回
    {"question_id": 问题编号, "answer": 回答文字}。回答不合法抛ValueError。
    节点恢复时会从头执行，因此interrupt前不可重复执行有副作用的操作。
    需要宿主提供Checkpointer及稳定thread_id；此函数不管理存储、网络和前端。
    """
    response = interrupt({"status": "waiting_for_user", **asdict(question)})
    if not isinstance(response, dict):
        raise ValueError("用户回答必须包含问题编号和回答文字。")
    question_id, answer = response.get("question_id"), response.get("answer")
    if not isinstance(question_id, str) or not isinstance(answer, str):
        raise ValueError("用户回答必须包含问题编号和回答文字。")
    return validate_user_answer(question=question, question_id=question_id, answer=answer)
