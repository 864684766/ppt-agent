"""读取OSS模板字节的独立能力；不依赖SDK、HTTP或配置。"""

from typing import Protocol


class TemplateFileReader(Protocol):
    """实现负责关闭下载流；调用方持有返回字节，后续校验和解析由读取模块执行。"""

    def read_file(self, *, object_key: str, max_bytes: int) -> bytes:
        """从固定桶读取一个对象，严格限制字节数；失败抛TemplateResourceError。"""
        ...
