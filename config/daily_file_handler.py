"""按日志发生日期选择文件，避免长时间运行的服务把多天日志混在同一文件。"""

import logging
import time
from datetime import datetime
from pathlib import Path


class DailyFileHandler(logging.FileHandler):
    """以运行环境本地日期分文件；同一天重启追加，不自动删除历史日志。

    复用标准FileHandler的UTF-8写入、刷新和关闭；Handler.handle持有线程锁，
    文件切换与写入在同一锁内进行。本类不支持多进程协调。
    """

    def __init__(self, directory: Path) -> None:
        """directory由外层确保存在，初始化打开当天文件以尽早发现权限问题。"""
        self._directory = directory.resolve()
        super().__init__(self._path_for_timestamp(time.time()), encoding="utf-8", mode="a")

    def _path_for_timestamp(self, timestamp: float) -> Path:
        """timestamp是记录创建时的Unix秒数，按本机时区转换为日期。"""
        date_text = datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d")
        return self._directory / f"ppt-agent-{date_text}.log"

    def emit(self, record: logging.LogRecord) -> None:
        """每条记录写入前检查日期；跨天后的首条记录触发切换，无需重启。"""
        target = self._path_for_timestamp(record.created)
        if str(target) != self.baseFilename:
            if self.stream is not None:
                # 先刷新并关闭前一天的句柄；FileHandler.emit会打开新路径。
                self.stream.flush()
                self.stream.close()
                self.stream = None
            self.baseFilename = str(target)
        super().emit(record)
