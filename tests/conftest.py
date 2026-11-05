"""pytest统一日志入口，让单独Debug任何测试时也会创建应用日志。"""

import logging
from collections.abc import Iterator

import pytest
from pydantic import ValidationError

from config.logging_config import configure_logging
from config.settings import PROJECT_ROOT, Settings


@pytest.fixture(scope="session", autouse=True)
def initialize_test_logging() -> Iterator[None]:
    """pytest自动执行一次。只初始化日志，不访问网络、不创建模型。

    conftest.py会被pytest自动发现，不需每个测试再复制日志初始化代码。
    服务入口仍由FastAPI lifespan初始化，独立示例则在其main函数初始化。
    """
    try:
        settings = Settings()
    except ValidationError:
        raise RuntimeError("测试配置格式不正确，请检查.env；为避免泄露配置值不输出原始异常。") from None
    configure_logging(directory=PROJECT_ROOT / "log", level=settings.log_level, output=settings.log_output)
    logger = logging.getLogger(__name__)
    logger.info("pytest日志初始化完成。")
    yield
    logger.info("pytest执行结束。")
