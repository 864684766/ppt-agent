# 提示词目录

提示词与调用代码分开维护，修改后下次运行读取；不代表运行中任务自动更新。

| 文件 | 调用方 | 状态 |
| --- | --- | --- |
| templates/template_visual_analysis.md | integrations/templates/langchain_template_vision.py（外层读取并注入） | 当前视觉识别模块使用；真实测试入口为tests/test_template_vision.py |
| web/research_query.md / web/research_review.md | 查询与检查子Agent（外层读取并注入） | 网页研究使用服务器默认引擎，已通过聊天入口调用 |

该提示词定义视觉观察规则。输出字段Schema由适配器根据TemplateVisualAnalysis动态附加，避免提示词与数据模型重复维护字段定义。正式子Agent提示词后续按任务增加。

网页提炼使用两份提示词，由宿主注入 `WebpageExtractionAgent`：

| 文件 | 作用 |
| --- | --- |
| `web/web_research_page.md` | 单页提炼规则、跟进链接和 JSON 格式。 |
| `web/web_research_page_retry.md` | 单页输出超限后的精简重试要求。 |

图运行期间修改文件不会改变已构造的 Agent；重新构造 Agent 后才会读取更新内容。

`materials/material_summary.md` 用于通用资料汇总（包括网页工作流），接收网页及文件提炼要点的统一编号，不读取正文。
