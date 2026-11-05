"""list_materials 工具的组装和执行入口。

输入与公开输出在 models/materials/list_materials_contract.py；
资料实体在 models/materials/material_source.py，查询规则在 domain.materials。
这个文件只连接它们，不承担文件上传、解析、HTTP 或存储职责。
"""


from collections.abc import Sequence
from typing import Literal

from langchain.tools import tool
from langchain_core.tools import BaseTool

from diagnostics.operation_logging import log_operation
from models.materials.material_source import MaterialSummary
from domain.materials import list_project_materials
from models.materials.list_materials_contract import (
    ListMaterialsInput,
    ListMaterialsOutput,
    MaterialListItem,
)


def create_list_materials_tool(
    *, project_id: str, materials: Sequence[MaterialSummary]
) -> BaseTool:
    """创建绑定某项目和不可变目录快照的工具，交给 Agent 注册。

    project_id 必须由宿主根据当前任务确定，不能接受模型的项目选择。
    复制序列并预先检查登记数据；无效范围或重复来源抛 ValueError，
    属于宿主组装问题。模型的非法参数由 Pydantic 抛 ValidationError，
    尚未涉及外部服务，所以没有伪造的网络错误或统一成功返回。

    此版是快照查询，不是热更新仓库；外层更新资料后需重建工具。
    不读配置、不创建线程，也没有需要调用方关闭的资源。
    """
    # tuple 保存序列快照；MaterialSummary 也不可变，因此查询期间内容稳定。
    snapshot = tuple(materials)
    list_project_materials(snapshot, project_id=project_id, limit=1)

    # description 面向模型，说明使用场景和边界；函数 docstring 面向开发者。
    # args_schema 的 Field.description 则分别解释每个参数怎样填写。
    # 不使用 return_direct=True：资料结果仍需交回 Agent 继续分析。
    @tool(
        "list_materials",
        description=(
            "当需要知道当前项目有哪些已登记业务参考资料、取得source_id、"
            "查看解析状态，或按来源/名称筛选资料目录时使用。"
            "包括上传业务文件和已抓取并登记的网页正文；不含设计模板、"
            "技能、未关联历史文件或搜索候选链接。只返回目录摘要，不返回正文，"
            "不上传、不联网搜索。来源或source_id已知时不必为了走流程先调用它。"
            "返回items、筛选后总数total和下一页偏移next_offset；"
            "next_offset为null表示结束。status为pending/ready/failed分别表示"
            "待解析/可供后续读取/解析失败，列出来不等于正文已可读取。"
        ),
        args_schema=ListMaterialsInput,
    )
    @log_operation("tool.list_materials")
    def list_materials(
        origin: Literal["all", "uploaded", "web"] = "all",
        name_contains: str = "",
        offset: int = 0,
        limit: int = 20,
    ) -> ListMaterialsOutput:
        """执行一次目录查询并选择公开字段。

        Args:
            origin: 模型请求的来源类型，由参数模型限制为三个可选值。
            name_contains: 名称过滤文本，不用于正文检索。
            offset: 当前结果集中的起始偏移，不是文件页码。
            limit: 当前目录页最多返回几条摘要。

        Returns:
            资料摘要列表、筛选后总数和可继续翻页的位置。

        project_id 和 snapshot 来自外层工厂。内层函数能读取外层变量，
        这种写法称为“闭包”，避免把内部项目范围暴露成模型参数。
        """
        page = list_project_materials(
            snapshot, project_id=project_id, origin=origin,
            name_contains=name_contains, offset=offset, limit=limit,
        )
        # 只公开工具契约中的元数据；隐藏内部项目绑定和未来可能增加的字段。
        items: list[MaterialListItem] = [
            {
                "source_id": item.source_id, "name": item.name,
                "origin": item.origin, "format": item.format,
                "status": item.status, "version": item.version,
                "url": item.url, "page_count": item.page_count,
            }
            for item in page.items
        ]
        return {"items": items, "total": page.total, "next_offset": page.next_offset}

    # 装饰后的 list_materials 已是工具对象，支持 .invoke() 和模型工具绑定。
    return list_materials
