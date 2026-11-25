"""通过终端真实输入体验通用询问和LangGraph暂停恢复。

运行：uv run --locked python -m examples.ask_user_demo
在PyCharm中也可直接运行；这不调用模型、网络或HTTP接口。
"""

from typing import TypedDict
from uuid import uuid4

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command

from models.interaction.user_question import UserQuestion
from workflows.interaction.ask_user import ask_user


class DemoState(TypedDict):
    """演示图状态：问题在进入暂停节点之前创建，保证恢复时编号不变。"""

    question: dict  # 已准备的问题字段，由入口生成。
    answer: str  # 用户实际输入的回答，初始为空。


def wait_for_answer(state: DemoState) -> dict:
    """问一个开放问题；interrupt恢复时会重新进入这个函数。"""
    # 检查点反序列化后，列表保持列表；实体要求不可变tuple，故在边界转换。
    question_data = {**state["question"], "options": tuple(state["question"]["options"])}
    question = UserQuestion(**question_data)
    return {"answer": ask_user(question)}


def main() -> None:
    """创建内存图，打印真实问题，并等待使用者在终端输入答案。"""
    graph = StateGraph(DemoState)
    graph.add_node("ask", wait_for_answer)
    graph.add_edge(START, "ask")
    graph.add_edge("ask", END)
    app = graph.compile(checkpointer=InMemorySaver())
    question_id = uuid4().hex
    config = {"configurable": {"thread_id": uuid4().hex}}
    initial = {"question": {"question_id": question_id, "question": "请补充你希望介绍的主题。",
                            "reason": "当前需求还不明确。", "options": [], "allow_free_text": True}, "answer": ""}
    first = app.invoke(initial, config=config)
    print("【等待用户】", first["__interrupt__"][0].value)
    answer = input("请输入你的回答：")
    result = app.invoke(Command(resume={"question_id": question_id, "answer": answer}), config=config)
    print("【恢复后的真实回答】", result["answer"])


if __name__ == "__main__":
    main()
