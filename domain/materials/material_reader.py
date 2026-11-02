"""按来源、版本和块ID读取已解析正文；不访问磁盘、网络或模型。"""

from collections.abc import Sequence

from domain.materials.material_validator import validate_material_content_data
from models.materials.material_fragment import MaterialFragment
from models.materials.material_query_results import MaterialReadResult
from models.materials.material_source import MaterialSummary


def read_project_material(
    *, project_id: str, materials: Sequence[MaterialSummary],
    fragments: Sequence[MaterialFragment], source_id: str, version: str,
    block_id: str, offset: int = 0, max_chars: int = 2000,
) -> MaterialReadResult:
    """精确读取一个正文块，按Python字符切片并提供续读位置。

    调用方拥有目录和正文快照。目录/正文关联错误、来源未就绪、版本过期、
    块不存在或参数无效时抛ValueError，不把这些问题伪装为空正文。
    offset等于块长时合法，返回空文本且无下一段；超过块长则报错。
    不strip原文，避免改变字符偏移；不自动读取相邻块或猜测块顺序。
    """
    validate_material_content_data(
        project_id=project_id, materials=materials, fragments=fragments,
    )
    # 纯Python调用不一定经过Pydantic，所以业务入口也检查自己的参数。
    for name, value in (("source_id", source_id), ("version", version), ("block_id", block_id)):
        if not isinstance(value, str) or not value.strip() or len(value) > 200:
            raise ValueError(f"{name}必须为1至200字符的非空字符串。")
    if type(offset) is not int or offset < 0:
        raise ValueError("offset必须为非负整数。")
    if type(max_chars) is not int or not 1 <= max_chars <= 8000:
        raise ValueError("max_chars必须为1至8000的整数。")

    source = next((item for item in materials
                   if item.project_id == project_id and item.source_id == source_id), None)
    if source is None:
        raise ValueError("当前项目未登记指定来源。")
    if source.status != "ready":
        raise ValueError("指定来源尚未ready，不能读取正文。")
    if source.version != version:
        raise ValueError("请求版本与当前资料版本不一致，请重新检索获取定位。")

    # 公共校验已保证块编号唯一，因此找到的块不会存在歧义。
    fragment = next((item for item in fragments
                     if item.project_id == project_id and item.source_id == source_id
                     and item.version == version and item.block_id == block_id), None)
    if fragment is None:
        raise ValueError("指定正文块不存在或尚未载入，请核对检索定位。")
    total_chars = len(fragment.text)
    if offset > total_chars:
        raise ValueError("offset不能超过正文块的总字符数。")
    end_offset = min(offset + max_chars, total_chars)
    return MaterialReadResult(
        fragment=fragment, text=fragment.text[offset:end_offset],
        offset=offset, end_offset=end_offset,
        next_offset=end_offset if end_offset < total_chars else None,
    )
