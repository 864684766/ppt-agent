"""网页研究进度通知；任务上下文隔离，不承载传输或模型正文。"""
from contextvars import ContextVar
from collections.abc import Callable

research_progress: ContextVar[Callable[[str], None] | None] = ContextVar("research_progress", default=None)


def notify_progress(stage: str) -> None:
    """只通知执行阶段；未注册接收方时普通工作流仍可独立运行。"""
    callback = research_progress.get()
    if callback is not None:
        callback(stage)
