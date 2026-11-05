"""PPTX转PDF的可替换接口；业务调用方不需要知道具体转换服务。"""

from typing import Protocol


class PresentationConversionError(RuntimeError):
    """可以给调用方展示的转换错误，不包含文档正文、上游响应或本机路径。"""


class PresentationPdfConverter(Protocol):
    """约定“传入文件字节，得到PDF字节”，不负责读写磁盘或创建HTTP连接。

    Protocol只定义方法签名，不实例化转换器。未来更换转换服务时，
    新实现只需满足这个调用方式，不必修改使用它的业务逻辑。
    """

    async def convert(self, *, pptx_bytes: bytes, file_name: str) -> bytes:
        """转换一份PPTX，返回PDF原始字节；失败抛PresentationConversionError。

        pptx_bytes：调用方读取的非空文件内容，不是文件路径。
        file_name：包含.pptx后缀的纯文件名，用于上传，不允许携带目录。
        返回bytes而不是自定义模型，因为本阶段没有其他转换结果字段。
        输入与输出都由调用方保管；本接口不承诺页数、字体或视觉效果完全一致。
        """
        ...
