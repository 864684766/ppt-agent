"""通用 SSE 传输格式；不依赖模型或具体业务事件。"""

import json
from collections.abc import Mapping


# 递归类型：JSON 对象或数组内部仍可包含其他 JSON 值。
# 不接收 SDK 对象、异常、bytes 或 datetime；调用方先转换为明确的公开字段。
type JsonValue = str | int | float | bool | None | list[JsonValue] | dict[str, JsonValue]


def encode_event(event: str, data: Mapping[str, JsonValue]) -> str:
    """构造一个 SSE 事件；空行标志事件结束，JSON 转义正文中的换行。

    Args:
        event: 非空事件名，不能包含 CR、LF 或空字符，以免破坏事件边界。
        data: 字符串键的 JSON 数据，支持嵌套对象、数组、数值、布尔值和 null。
            使用 Mapping 表示只读取调用方数据，不修改它；顶层转为普通 dict 编码。

    Returns:
        一个完整 SSE 帧的字符串。ensure_ascii=False 保留中文字符，真正的 UTF-8
        编码由 StreamingResponse 完成。客户端按事件解析，不假设网络包等于事件。

    Raises:
        ValueError: 事件名无效、数据循环引用或包含 NaN/Infinity 等非标准 JSON 数值。
        TypeError: 数据包含不能直接编码的对象。

    本函数只负责传输编码，不决定哪些工具或推理信息可以公开，也不负责界面展示。
    不使用 default=str，避免意外将 SDK 内部对象或异常细节直接暴露给客户端。
    """
    if not event.strip() or any(char in event for char in ("\r", "\n", "\x00")):
        raise ValueError("SSE 事件名不能为空或包含换行、空字符。")
    payload = json.dumps(dict(data), ensure_ascii=False, allow_nan=False)
    return f"event: {event}\ndata: {payload}\n\n"
