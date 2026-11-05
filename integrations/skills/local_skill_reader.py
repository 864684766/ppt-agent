"""从宿主绑定的本地技能目录读取入口，不检查依赖或执行附属文件。"""


import logging
from pathlib import Path

from diagnostics.operation_logging import log_operation
from domain.skills.skill_reader_contract import SkillReadError
from integrations.skills.skill_header_reader import read_skill_header
from integrations.skills.skill_metadata_parser import parse_skill_metadata


logger = logging.getLogger(__name__)


class LocalSkillReader:
    """目录由外层绑定；只接受一级技能编号，不接受任意资源路径。"""

    def __init__(self, *, directory: Path) -> None:
        """保存根目录，不在构造或导入时读取文件。"""
        self._directory = directory.resolve()

    @log_operation("skills.read")
    def read(self, *, skill_id: str) -> str:
        """校验定位与介绍格式，返回完整UTF-8正文；失败记录安全日志。

        与发现工具共用头部读取和元数据解析，避免维护两套标准。
        显式读取一个无效编号时返回错误，不伪装为成功的空正文；日志不包含原文。
        不扫描依赖，不预读references/assets，不运行scripts，不创建快照或缓存。
        """
        # 即便绕过Agent参数Schema直接使用适配器，也只能读取单层目录。
        if not skill_id or skill_id.startswith(".") or any(char in skill_id for char in "/\\:"):
            raise SkillReadError("技能编号无效，请使用list_skills返回的skill_id。")
        try:
            folder = self._directory / skill_id
            path = folder / "SKILL.md"
            if folder.is_symlink() or folder.is_junction() or path.is_symlink():
                raise ValueError("不读取链接技能目录或文件。")
            if not path.resolve().is_relative_to(self._directory):
                raise ValueError("技能文件不在约定目录内。")
            # 只确认标准介绍可读，不分析正文中的工具、依赖或执行要求。
            parse_skill_metadata(read_skill_header(path), skill_id=skill_id)
            content = path.read_text(encoding="utf-8-sig")
            logger.info("event=skill_read_result content_chars=%s", len(content))
            return content
        except (OSError, UnicodeError):
            reason = "SKILL.md不存在、不可读或不是UTF-8文本。"
        except ValueError as error:
            reason = str(error)
        logger.warning("未读取技能 %r：%s", skill_id, reason)
        raise SkillReadError(f"无法读取技能：{reason}") from None
