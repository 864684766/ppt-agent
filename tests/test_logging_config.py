"""验证统一日志输出，不依赖模型、网络或技能脚本。"""

import logging
from collections.abc import Iterator
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from config.logging_config import configure_logging
from config.daily_file_handler import DailyFileHandler


@pytest.fixture(autouse=True)
def restore_logging_after_test() -> Iterator[None]:
    """保存宿主配置；测试结束关闭新增文件句柄，避免影响其他测试。"""
    root_logger = logging.getLogger()
    original_handlers = tuple(root_logger.handlers)
    original_level = root_logger.level
    # 暂时取下应用处理器，避免测试中的重新配置将会话级文件句柄关闭。
    # pytest自己的捕获处理器仍保留，测试结束后再挂回原来的应用处理器。
    for handler in original_handlers:
        if handler.name in {"ppt-agent.file", "ppt-agent.console"}:
            root_logger.removeHandler(handler)
    yield
    for handler in tuple(root_logger.handlers):
        if handler not in original_handlers:
            root_logger.removeHandler(handler)
            handler.close()
    for handler in original_handlers:
        if handler not in root_logger.handlers:
            root_logger.addHandler(handler)
    root_logger.setLevel(original_level)


def test_file_logging_writes_once_in_utf8(tmp_path: Path) -> None:
    """验证中文写入、重复初始化和WARNING切换DEBUG后的阈值变化。"""
    log_path = configure_logging(directory=tmp_path / "log", level="WARNING", output="file")
    assert log_path is not None
    assert configure_logging(directory=tmp_path / "log", level="WARNING", output="file") == log_path
    logger = logging.getLogger("integrations.logging_verification")
    logger.info("此信息不应写入。")
    logger.warning("技能介绍不规范，已忽略。")
    content = log_path.read_text(encoding="utf-8")
    assert content.count("技能介绍不规范，已忽略。") == 1
    assert "WARNING | integrations.logging_verification" in content
    assert "此信息不应写入。" not in content
    configure_logging(directory=tmp_path / "log", level="DEBUG", output="file")
    logger.debug("详细调试信息。")
    assert log_path.read_text(encoding="utf-8").count("详细调试信息。") == 1


@pytest.mark.parametrize("output", ["file", "console", "both"])
def test_output_destination(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], output: str,
) -> None:
    """独立模块共用配置；各目标按需写入，重复初始化没有重复输出。"""
    directory = tmp_path / "log"
    configure_logging(directory=directory, output=output)
    log_path = configure_logging(directory=directory, output=output)
    logging.getLogger("tools.logging_example").info("来自工具模块的日志。")
    logging.getLogger("domain.logging_example").info("来自领域模块的日志。")
    console_text = capsys.readouterr().err
    if output in {"console", "both"}:
        assert console_text.count("来自工具模块的日志。") == 1
        assert console_text.count("来自领域模块的日志。") == 1
    else:
        assert console_text == ""
    if output in {"file", "both"}:
        assert log_path is not None
        content = log_path.read_text(encoding="utf-8")
        assert content.count("来自工具模块的日志。") == 1
        assert content.count("来自领域模块的日志。") == 1
    else:
        assert log_path is None
        assert not directory.exists()


def test_switch_output_closes_old_file(
    tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    """切换到控制台后停止写旧文件，并释放Windows文件句柄。"""
    log_path = configure_logging(directory=tmp_path / "log", output="both")
    assert log_path is not None
    logger = logging.getLogger("api.logging_example")
    logger.warning("切换前。")
    capsys.readouterr()
    configure_logging(directory=tmp_path / "log", output="console")
    previous_content = log_path.read_text(encoding="utf-8")
    logger.warning("切换后。")
    assert "切换后。" in capsys.readouterr().err
    assert log_path.read_text(encoding="utf-8") == previous_content
    log_path.unlink()


def test_daily_files_switch_without_restart_and_append(tmp_path: Path) -> None:
    """模拟连续两天的日志，验证自动分文件和重新初始化后的追加写入。"""
    today = datetime.now().replace(hour=12, minute=0, second=0, microsecond=0)
    tomorrow = today + timedelta(days=1)

    def make_record(at: datetime, message: str) -> logging.LogRecord:
        # 显式设置发生时间，不等待真实午夜，不修改系统时钟。
        record = logging.LogRecord("daily.example", logging.INFO, __file__, 0, message, (), None)
        record.created = at.timestamp()
        return record

    handler = DailyFileHandler(tmp_path)
    try:
        handler.handle(make_record(today, "第一天内容。"))
        handler.handle(make_record(tomorrow, "第二天内容。"))
    finally:
        handler.close()

    # 模拟同日重新初始化：原有文件仍应追加，不覆盖已记录的内容。
    handler = DailyFileHandler(tmp_path)
    try:
        handler.handle(make_record(tomorrow, "第二天追加。"))
    finally:
        handler.close()
    today_path = tmp_path / f"ppt-agent-{today:%Y-%m-%d}.log"
    tomorrow_path = tmp_path / f"ppt-agent-{tomorrow:%Y-%m-%d}.log"
    assert today_path.read_text(encoding="utf-8") == "第一天内容。\n"
    assert tomorrow_path.read_text(encoding="utf-8") == "第二天内容。\n第二天追加。\n"
