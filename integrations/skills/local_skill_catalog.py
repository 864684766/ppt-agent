"""扫描宿主传入目录的一级技能包，只读取SKILL.md头部，不执行代码。"""


import logging
from pathlib import Path

from diagnostics.operation_logging import log_operation
from domain.skills.skill_catalog_contract import SkillCatalogError
from integrations.skills.skill_metadata_parser import parse_skill_metadata
from integrations.skills.skill_header_reader import read_skill_header
from models.skills.skill_summary import SkillSummary


logger = logging.getLogger(__name__)


class LocalSkillCatalog:
    """目录由宿主绑定，模型不能切换；每次load重新扫描以看到手动文件变更。"""

    def __init__(self, *, directory: Path) -> None:
        """仅保存根目录，不在创建工具或模块导入时扫描。"""
        self._directory = directory.resolve()

    @log_operation("skills.scan")
    def load(self) -> tuple[SkillSummary, ...]:
        """返回可读取介绍的技能；格式不合要求时记录日志并跳过。

        单个技能异常不打断扫描；根目录不可读仍明确报错，不伪装为空目录。"""
        try:
            if not self._directory.is_dir():
                raise SkillCatalogError("本地技能目录不存在，请检查宿主提供的目录。")
            folders = sorted(self._directory.iterdir(), key=lambda path: path.name)
        except OSError:
            raise SkillCatalogError("无法读取本地技能目录，请检查目录权限。") from None
        items: list[SkillSummary] = []
        for folder in folders:
            # 跳过普通文件；不跨链接/junction寻找技能，保持约定的本地目录边界。
            if folder.is_symlink() or folder.is_junction():
                logger.warning("跳过技能目录 %r：不读取链接目录。", folder.name)
                continue
            if not folder.is_dir():
                continue
            path = folder / "SKILL.md"
            try:
                if path.is_symlink() or not path.resolve().is_relative_to(self._directory):
                    raise ValueError("SKILL.md不是目录内的普通文件。")
                header = read_skill_header(path)
                items.append(parse_skill_metadata(header, skill_id=folder.name))
            except (OSError, UnicodeError):
                logger.warning("跳过技能 %r：SKILL.md缺失、不可读或不是UTF-8文本。", folder.name)
            except ValueError as error:
                logger.warning("跳过技能 %r：%s", folder.name, error)
        logger.info("event=skill_scan_result accepted_count=%s", len(items))
        return tuple(items)
