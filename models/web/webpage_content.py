"""HTTP读取适配器交给业务层的网页内容，不包含项目登记信息。"""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class WebpageContent:
    """创建方为网页适配器；业务层读取后生成公开工具结果。"""

    # 跟随HTTP重定向后实际读取的网页地址。
    final_url: str
    # HTML的title文本；不存在时为空，不由模型猜测。
    title: str
    # 从HTML提取的可读文本，未按工具max_chars截断；不含原始HTML。
    text: str
    # 完成读取时的UTC时间，ISO 8601格式，非网页发布日期。
    fetched_at: str


@dataclass(frozen=True, slots=True)
class WebpageReadResult:
    """业务层截断后的内部结果，工具选择字段后再形成公开字典。"""

    # 实际输入地址，去首尾空白。
    requested_url: str
    # 原始提取结果，提供标题、最终地址、抓取时间及原文本长度。
    content: WebpageContent
    # 根据max_chars截取的返回正文。
    text: str
    # 原文本是否超过返回字符上限。
    truncated: bool
