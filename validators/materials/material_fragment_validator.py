"""单条正文片段的字段校验，只接收普通字段，不依赖实体或框架。"""


def validate_material_fragment(
    *, project_id: str, source_id: str, version: str,
    block_id: str, text: str, page: int | None,
) -> None:
    """标识/正文须非空，已知页码须为正整数；失败抛ValueError。

    来源是否已登记、版本是否一致涉及多条数据，由业务层另行检查。
    不strip正文后存储，避免改变原文位置和内容。
    """
    values = {
        "project_id": project_id, "source_id": source_id,
        "version": version, "block_id": block_id, "text": text,
    }
    for field, value in values.items():
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{field} 必须为非空字符串。")
    if page is not None and (type(page) is not int or page < 1):
        raise ValueError("page 必须为从1开始的正整数或None。")
