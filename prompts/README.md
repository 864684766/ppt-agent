# 提示词目录

提示词与调用代码分开维护，修改后下次运行读取；不代表运行中任务自动更新。

| 文件 | 调用方 | 状态 |
| --- | --- | --- |
| template_visual_analysis.md | integrations/templates/langchain_template_vision.py（外层读取并注入） | 当前视觉识别模块使用；真实测试入口为tests/test_template_vision.py |
| research_query.md / research_review.md | 查询与检查子Agent（外层读取并注入） | 独立多引擎研究流程使用，不代表已接聊天 |

该提示词定义视觉观察规则。输出字段Schema由适配器根据TemplateVisualAnalysis动态附加，避免提示词与数据模型重复维护字段定义。正式子Agent提示词后续按任务增加。

网页资料整理使用四份提示词，均由宿主读取文字后注入 `WebResearchSummaryAgent`：

| 文件 | 作用 |
| --- | --- |
| `web_research_summary.md` | 单页提炼和累计汇总共用的规则。 |
| `web_research_page.md` | 单页提炼、跟进链接和 JSON 格式。 |
| `web_research_merge.md` | 累计要点合并、内容问题和 JSON 格式。 |
| `web_research_page_retry.md` | 单页输出超限后的精简重试要求。 |

图运行期间修改文件不会改变已构造的 Agent；重新构造 Agent 后才会读取更新内容。
