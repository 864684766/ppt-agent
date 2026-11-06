"""FastAPI 应用入口。

直接运行本文件可启动本地服务；也可通过 ``uv run uvicorn main:app``
导入 app，由 Uvicorn 命令管理监听地址和端口。
"""

import logging
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI

from api.api_router import api_router
from api.request_logging_middleware import RequestLoggingMiddleware
from config.logging_config import configure_logging
from config.settings import PROJECT_ROOT, Settings


@asynccontextmanager
async def application_lifespan(application: FastAPI) -> AsyncIterator[None]:
    """定义服务生命周期：yield前初始化，yield后可放退出时的清理操作。

    asynccontextmanager把异步生成器转换为可用于async with的上下文管理器；
    FastAPI负责进入和退出这个上下文。application是FastAPI传入的应用实例，
    当前暂不需要使用；仅导入main不会进入生命周期，也不会创建日志文件。
    """
    settings = Settings()
    configure_logging(
        directory=PROJECT_ROOT / "log", level=settings.log_level, output=settings.log_output,
    )
    logging.getLogger(__name__).info(
        "FastAPI服务启动，日志级别=%s，输出目标=%s。", settings.log_level, settings.log_output,
    )
    # 将控制权交回FastAPI开始处理请求；不是向HTTP客户端返回数据。
    # 服务退出时从这里恢复，后续有资源清理需求可放在try/finally中。
    try:
        yield
    finally:
        logging.getLogger(__name__).info("FastAPI服务关闭。")


def create_app() -> FastAPI:
    """创建应用并注册路由。

    将应用组装放入函数，便于后续注入配置，也便于需要时创建独立实例。
    注册健康检查、文件解析对话和OSS模板列表路由；当前对话不创建模型，
    应用组装本身不发起模型请求，也不初始化 Harness 等外部运行时。

    Returns:
        已注册健康检查与业务路由的 FastAPI 应用实例。
    """
    application = FastAPI(
        title="AI PPT 工作台 API",
        description="通过对话、资料和模板生成可编辑 PPTX 的后端服务。",
        version="0.1.0",
        lifespan=application_lifespan,
    )
    # API 层统一组装各模块，应用入口只挂载总路由。
    application.include_router(api_router)
    application.add_middleware(RequestLoggingMiddleware)
    return application


# Uvicorn 的 main:app 对应本文件的 app；导入时完成轻量的应用组装。
app = create_app()


if __name__ == "__main__":
    # 仅在直接运行 main.py 时启动监听；被 Uvicorn 或其他模块导入时不执行。
    # 本地调试使用单进程，不启用自动重载，便于 PyCharm 在当前进程命中断点。
    import uvicorn

    settings = Settings()
    uvicorn.run(app, host=settings.app_host, port=settings.app_port)
