"""文件接收的安全错误；HTTP状态码由API层映射，不写入业务异常。"""


class FileUploadError(ValueError):
    """code为固定错误分类，message为开发者提供的安全中文提示。

    不用上传内容或第三方异常原文拼接message，避免响应或日志泄露文件正文。
    """

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
