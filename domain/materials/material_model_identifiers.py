"""为单次资料汇总转换短编号；不修改公开结果及原始来源编号。"""

from collections.abc import Iterable, Sequence

from models.materials.material_summary import MaterialInputPoint, MaterialSummary


class MaterialModelIdentifiers:
    """维护单次汇总的编号映射；实例只适用于创建时提供的要点集合。

    模型使用短要点编号和短来源编号；调用方持有原始要点，用于还原及查询来源。
    不调用模型、不访问外部资源，也不判断资料是否充分或来源是否可信。
    """

    def __init__(self, points: Sequence[MaterialInputPoint]) -> None:
        """按输入顺序分配编号；原始要点编号重复时抛出 ValueError。"""
        self._points = tuple(points)
        self._original_by_alias: dict[str, str] = {}
        self._aliases_by_original: dict[str, str] = {}
        self._source_by_reference: dict[tuple[str, str], str] = {}
        self._sources_by_alias: dict[str, list[str]] = {}

        for index, point in enumerate(self._points, start=1):
            if point.point_id in self._aliases_by_original:
                raise ValueError("资料要点编号必须在本次汇总中唯一。")
            alias = f"p{index}"
            self._original_by_alias[alias] = point.point_id
            self._aliases_by_original[point.point_id] = alias
            sources: list[str] = []
            for reference in point.references:
                # 来源按类型和编号区分；块号用于定位，不把同一文件当作多个来源。
                key = (reference.kind, reference.source_id)
                if key not in self._source_by_reference:
                    self._source_by_reference[key] = f"s{len(self._source_by_reference) + 1}"
                source = self._source_by_reference[key]
                if source not in sources:
                    sources.append(source)
            self._sources_by_alias[alias] = sources

    def model_data(self) -> list[dict]:
        """返回发给模型的要点文本及短编号，不附带文件正文或完整来源编号。"""
        return [{"point_ids": [self._aliases_by_original[point.point_id]], "content": point.content}
                for point in self._points]

    def source_map(self, aliases: Iterable[str] | None = None) -> dict[str, list[str]]:
        """返回短要点编号到短来源编号的映射；未知要点编号会明确报错。

        aliases 留空返回全部映射；传入时仅包含所选要点，列表中的每个来源
        对应原始引用的类型和来源编号，相同来源在不同要点中使用同一短编号。
        """
        selected = self._original_by_alias if aliases is None else aliases
        result: dict[str, list[str]] = {}
        for alias in selected:
            if alias not in self._sources_by_alias:
                raise ValueError("资料汇总包含未知的要点短编号。")
            result[alias] = self._sources_by_alias[alias].copy()
        return result

    def restore_summary(self, summary: MaterialSummary) -> MaterialSummary:
        """校验全部输出引用后返回新汇总，将短要点编号还原为原始编号。

        points、issues 和大纲要点都必须引用本次已分配的编号；任何未知编号
        均抛 ValueError。当前批次允许引用的范围由调用方在还原前另行检查。
        输入的 summary 不会被修改，也不改变已保留的原始来源关系。
        """
        groups = [item.point_ids for item in summary.points]
        groups.extend(item.point_ids for item in summary.issues)
        if summary.outline:
            groups.extend(bullet.point_ids for slide in summary.outline.slides for bullet in slide.bullets)
        if any(alias not in self._original_by_alias for group in groups for alias in group):
            raise ValueError("模型引用了不存在的要点短编号。")

        result = summary.model_copy(deep=True)
        restored_groups = [item.point_ids for item in result.points]
        restored_groups.extend(item.point_ids for item in result.issues)
        if result.outline:
            restored_groups.extend(bullet.point_ids for slide in result.outline.slides for bullet in slide.bullets)
        for group in restored_groups:
            group[:] = [self._original_by_alias[alias] for alias in group]
        return result
