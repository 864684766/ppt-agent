"""全系统共用的日志配置；启动入口组装，各功能模块只使用标准logging。"""

import logging
from pathlib import Path

from config.daily_file_handler import DailyFileHandler


def configure_logging(
    *, directory: Path, level: str = "INFO", output: str = "both",
) -> Path | None:
    """配置应用日志，启用文件时返回初始化当天路径，仅控制台时返回None。

    level为DEBUG/INFO/WARNING/ERROR/CRITICAL，默认INFO；output为file、
    console或both，默认both。非法值抛ValueError；文件目录不可写时抛OSError。
    控制台写入stderr；文件为UTF-8，按本地日期每天一个文件，同日重启追加。
    跨天自动切换，不按大小拆分，不自动删除历史文件。

    由服务或独立脚本入口初始化，不在业务模块中调用。重复调用会替换并关闭
    本模块创建的处理器，支持调整级别、目标与路径，避免重复写入或泄漏句柄。
    pytest/Uvicorn已有处理器不删除，其独立输出不受output控制。
    只接收传播到根logger且达到级别的记录，不接管独立logger；本版用于单进程。
    """
    if level not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
        raise ValueError("日志级别必须为DEBUG、INFO、WARNING、ERROR或CRITICAL。")
    if output not in {"file", "console", "both"}:
        raise ValueError("日志输出必须为file、console或both。")

    formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s")
    handlers: list[logging.Handler] = []
    log_path: Path | None = None
    if output in {"file", "both"}:
        # 仅在启用文件输出时创建目录；纯控制台模式适合Docker标准日志收集。
        directory = directory.resolve()
        directory.mkdir(parents=True, exist_ok=True)
        file_handler = DailyFileHandler(directory)
        log_path = Path(file_handler.baseFilename)
        file_handler.set_name("ppt-agent.file")
        handlers.append(file_handler)
    if output in {"console", "both"}:
        console_handler = logging.StreamHandler()
        console_handler.set_name("ppt-agent.console")
        handlers.append(console_handler)
    for handler in handlers:
        handler.setLevel(level)
        handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    # 名称标识本项目拥有的处理器，不能使用clear()破坏pytest等宿主的配置。
    for previous in tuple(root_logger.handlers):
        if previous.name in {"ppt-agent.file", "ppt-agent.console"}:
            root_logger.removeHandler(previous)
            previous.close()
    root_logger.setLevel(level)
    for handler in handlers:
        root_logger.addHandler(handler)
    return log_path
