"""将已提炼的网页和文件要点交给通用汇总；不负责搜索、读取或HTTP。"""

from agents.materials.material_summary_agent import MaterialSummaryAgent
from diagnostics.operation_logging import log_operation
from domain.materials.material_summary_inputs import file_summary_points, web_summary_points
from models.materials.file_extraction import FileExtraction
from models.materials.material_summary import MaterialInputPoint, MaterialSummary


class MaterialCollectionWorkflow:
    """组合现有提炼结果并执行汇总；Agent及模型资源由调用方持有。"""

    def __init__(self, *, summary_agent: MaterialSummaryAgent) -> None:
        self._summary_agent = summary_agent

    @log_operation("workflow.material_collection")
    async def run(self, *, question: str, webpages: list[dict],
                  files: list[tuple[str, FileExtraction]]) -> tuple[MaterialSummary, list[MaterialInputPoint]]:
        """返回汇总及其输入，以便调用方通过输入编号还原来源。

        webpages是网页图的page_extractions；files每项为本次唯一文件来源编号和
        提炼结果。文件中断、来源编号重复或没有要点时抛ValueError，不能伪装成完成。
        不自动处理中断后的用户选择、文件上传或全局资料充分性。
        """
        source_ids = [source_id for source_id, _ in files]
        if len(set(source_ids)) != len(source_ids):
            raise ValueError("文件来源编号必须在本次任务内唯一。")
        points = web_summary_points(extractions=webpages)
        for source_id, extraction in files:
            points.extend(file_summary_points(extraction=extraction, source_id=source_id))
        summary = await self._summary_agent.summarize(question=question, points=points)
        return summary, points
