# 提示词目录

提示词与调用代码分开维护，修改后下次运行读取；不代表运行中任务自动更新。

| 文件 | 调用方 | 状态 |
| --- | --- | --- |
| templates/template_visual_analysis.md | integrations/templates/langchain_template_vision.py（外层读取并注入） | 当前视觉识别模块使用；真实测试入口为tests/test_template_vision.py |
| web/research_query.md / web/research_review.md | 查询与检查子Agent（外层读取并注入） | 搜索后筛选主题、子主题和有用背景，未覆盖的明确要求留在检查结果中 |

普通PPT概述任务中，网页和文件提炼提示建议每个分段提取1至3个主题要点，保留重要事实及来源；用户明确要求细节时按需求覆盖。该数量是模型提示，并非程序硬限制，结果需验证。

该提示词定义视觉观察规则。输出字段Schema由适配器根据TemplateVisualAnalysis动态附加，避免提示词与数据模型重复维护字段定义。正式子Agent提示词后续按任务增加。

网页提炼使用两份提示词，由宿主注入 `WebpageExtractionAgent`：

| 文件 | 作用 |
| --- | --- |
| `web/web_research_page.md` | 单页提炼规则、跟进链接和 JSON 格式。 |
| `web/web_research_page_retry.md` | 单页输出超限后的精简重试要求。 |

图运行期间修改文件不会改变已构造的 Agent；重新构造 Agent 后才会读取更新内容。

`materials/material_summary.md` 包含文字汇总和最终大纲编排两部分。文字汇总返回精简要点和问题。发送给模型前，完全相同的要点只发送一次并携带全部支持编号。生成大纲时，模型按主题安排页标题和要点条目编号 `keys`，程序验证编号后填入已提炼的正文。已有大纲时，`issues` 表达补充建议。缺少核心内容导致无法编排时，模型返回空的 `sections`、可用要点和缺口说明。资料量大时先按字符预算分批压缩。

`materials/material_summary_retry.md` 由宿主单独读取并注入汇总助手。最终只生成文字汇总并遇到输出超限时，追加精简要求后重试一次。最终大纲模型失败而所需资料已就绪时，工作流可交付按提炼顺序编排的草稿，接口同时返回中断状态和失败分类。

`materials/request_analysis.md` 定义独立需求分析Agent的来源选择、顺序及JSON结构；尚未接入工作流。
