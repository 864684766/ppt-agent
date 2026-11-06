"""上传校验与纯文本读取共用的严格解码规则，不依赖具体文件读取操作。"""


def decode_document_text(content: bytes) -> str:
    """UTF-8（可含BOM）或带BOM的UTF-16；不猜测任意二进制编码。

    不可解码抛UnicodeError，空白/二进制控制字符抛ValueError，由调用边界映射安全错误。
    """
    encoding = "utf-16" if content.startswith((b"\xff\xfe", b"\xfe\xff")) else "utf-8-sig"
    text = content.decode(encoding)
    if not text.strip() or any(ord(char) < 32 and char not in "\t\n\r\f" for char in text):
        raise ValueError("文本为空白或包含二进制控制字符。")
    return text
