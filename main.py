"""FastAPI 应用入口。

直接运行本文件可启动本地服务；也可通过 ``uv run uvicorn main:app``
导入 app，由 Uvicorn 命令管理监听地址和端口。
"""

from fastapi import FastAPI

from api.router import api_router
from config.settings import Settings


def create_app() -> FastAPI:
    """创建应用并注册路由。

    将应用组装放入函数，便于后续注入配置，也便于需要时创建独立实例。
    此阶段仅检查服务是否能够响应，不初始化模型或外部运行时。

    Returns:
        已注册健康检查接口的 FastAPI 应用实例。
    """
    application = FastAPI(
        title="AI PPT 工作台 API",
        description="通过对话、资料和模板生成可编辑 PPTX 的后端服务。",
        version="0.1.0",
    )
    # API 层统一组装各模块，应用入口只挂载总路由。
    application.include_router(api_router)
    return application


# Uvicorn 的 main:app 对应本文件的 app；导入时完成轻量的应用组装。
app = create_app()


if __name__ == "__main__":
    # 仅在直接运行 main.py 时启动监听；被 Uvicorn 或其他模块导入时不执行。
    # 本地调试使用单进程，不启用自动重载，便于 PyCharm 在当前进程命中断点。
    import uvicorn

    settings = Settings()
    uvicorn.run(app, host=settings.app_host, port=settings.app_port)
