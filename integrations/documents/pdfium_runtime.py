"""PDFium的进程内共享锁：文本读取与页面渲染必须使用同一把锁。"""

from threading import Lock


# PDFium非线程安全。不同文档、不同功能也不能绕开此锁并发调用原生库。
PDFIUM_LOCK = Lock()
