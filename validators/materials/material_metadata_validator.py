"""业务资料元数据校验规则，仅依赖 Python 标准库。

这里回答“资料本身是否合法”，不校验工具分页参数或查询权限。
不导入实体、Pydantic、HTTP 或工具模块，避免实体和校验器循环引用。
"""


def validate_material_metadata(
    *,
    project_id: str,
    source_id: str,
    name: str,
    origin: str,
    format: str,
    status: str,
    version: str,
    url: str | None,
    page_count: int | None,
) -> None:
    """检查一条资料的字段及字段组合；成功无返回值，失败抛 ValueError。

    核心约束：标识和名称不能为空；来源/状态必须为约定值；页数非负；
    网页应有原URL，上传资料不填写网页URL。此处不联网验证URL可访问性。
    同项目source_id是否重复需要查看多条记录，仍由目录查询模块检查。
    """
    # 用映射收集同一类非空规则；没有修改传入对象或任何外部状态。
    values = {
        "project_id": project_id, "source_id": source_id,
        "name": name, "format": format, "version": version,
    }
    for field in ("project_id", "source_id", "name", "format", "version"):
        value = values[field]
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{field} 必须为非空字符串。")
    if origin not in ("uploaded", "web"):
        raise ValueError("origin 必须为 uploaded 或 web。")
    if status not in ("pending", "ready", "failed"):
        raise ValueError("status 必须为 pending、ready 或 failed。")
    if page_count is not None and (
        # bool 是 int 的子类；这里刻意不把 True 当作 1 页。
        type(page_count) is not int or page_count < 0
    ):
        raise ValueError("page_count 必须为非负整数或 None。")
    if origin == "web" and (
        not isinstance(url, str) or not url.strip()
    ):
        raise ValueError("网页资料必须提供原始 url。")
    if origin == "uploaded" and url is not None:
        raise ValueError("上传资料不填写网页 url。")
