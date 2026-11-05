"""通用操作日志：支持普通函数、协程和异步生成器，保持原返回值与异常行为。"""

import asyncio
import inspect
import logging
from collections.abc import Callable, Iterator
from contextlib import aclosing, contextmanager
from functools import wraps
from pathlib import Path
from time import perf_counter
from typing import Any
from uuid import uuid4

from diagnostics.log_context import operation_id


def safe_error_location(error: BaseException) -> str:
    """提取异常类型及代码位置，不输出异常原文、源码行、局部变量或绝对路径。

    from None只隐藏对外异常链，原异常通常仍在__context__，这里也记录它的类型和
    位置，便于区分网络超时/连接失败。最多追溯5层，避免循环或超长错误链。
    """
    chain: list[str] = []
    seen: set[int] = set()
    current: BaseException | None = error
    while current is not None and id(current) not in seen and len(chain) < 5:
        seen.add(id(current))
        frames: list[str] = []
        tb = current.__traceback__
        while tb is not None:
            code = tb.tb_frame.f_code
            frames.append(f"{Path(code.co_filename).name}:{tb.tb_lineno}:{code.co_name}")
            tb = tb.tb_next
        chain.append(type(current).__name__ + "[" + " > ".join(frames[-8:]) + "]")
        current = current.__cause__ if current.__cause__ is not None else current.__context__
    return " <- ".join(chain)


@contextmanager
def operation_scope(logger: logging.Logger, name: str) -> Iterator[None]:
    """记录一次操作生命周期，退出后恢复外层编号；日志本身不吞掉异常。

    name必须由开发者写固定操作名称，不传入用户输入。开始/完成/取消为INFO，
    失败为ERROR，包含毫秒耗时与安全调用位置。取消与主动关闭不算成功。
    """
    parent = operation_id.get()
    token = operation_id.set(uuid4().hex)
    started = perf_counter()
    logger.info("event=start operation=%s parent_operation_id=%s", name, parent)
    try:
        yield
    except (asyncio.CancelledError, GeneratorExit):
        logger.info("event=cancelled operation=%s duration_ms=%.2f", name, (perf_counter() - started) * 1000)
        raise
    except Exception as error:
        # 不使用logger.exception：SDK异常原文可能包含密钥、URL参数或用户正文。
        logger.error(
            "event=failed operation=%s duration_ms=%.2f error_location=%s",
            name, (perf_counter() - started) * 1000, safe_error_location(error),
        )
        raise
    else:
        logger.info("event=completed operation=%s duration_ms=%.2f", name, (perf_counter() - started) * 1000)
    finally:
        operation_id.reset(token)


def log_operation(name: str) -> Callable:
    """给执行边界添加日志的装饰器；不记录函数参数、结果正文或每个token。

    wraps保留原函数名称、注释和__wrapped__，让LangChain仍能识别参数签名。
    仅用于实际操作入口，不装饰Protocol、实体、每个校验函数或每个文本块。
    """
    def decorate(function: Callable) -> Callable:
        logger = logging.getLogger(function.__module__)
        if inspect.isasyncgenfunction(function):
            @wraps(function)
            async def stream_wrapper(*args: Any, **kwargs: Any):
                # 日志覆盖整个消费周期，不是在创建生成器对象时就标记完成。
                with operation_scope(logger, name):
                    async with aclosing(function(*args, **kwargs)) as chunks:
                        async for chunk in chunks:
                            yield chunk
            return stream_wrapper
        if inspect.iscoroutinefunction(function):
            @wraps(function)
            async def async_wrapper(*args: Any, **kwargs: Any):
                with operation_scope(logger, name):
                    return await function(*args, **kwargs)
            return async_wrapper

        @wraps(function)
        def sync_wrapper(*args: Any, **kwargs: Any):
            with operation_scope(logger, name):
                return function(*args, **kwargs)
        return sync_wrapper
    return decorate
