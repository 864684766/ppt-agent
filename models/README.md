# 数据模型导航

先按功能找目录，再按用途找文件。这里的“模型”指数据结构，不是大语言模型客户端。

资料模型集中为 6 个文件：资料来源、正文块、内部查询结果，以及三个工具各自的完整契约。查看一个工具怎么传参、返回什么，只需打开对应的 `_contract.py`；文件里的 Input 和 Output 仍是不同的类。

内部结果与工具契约分开，是为了让业务查询只使用标准库数据结构，不被迫引入 Pydantic 或 LangChain。共享限于真正被复用的资料实体与查询结果，不把所有工具的参数挤进一个大文件。

| 功能 | 你想找什么 | 类型 | 定义位置 |
| --- | --- | --- | --- |
| 资料 | 单份内部资料数据 | MaterialSummary | [material_source.py](materials/material_source.py) |
| 资料 | 内部目录查询的返回页 | MaterialPage | [material_query_results.py](materials/material_query_results.py) |
| 资料 | 解析后的正文块 | MaterialFragment | [material_fragment.py](materials/material_fragment.py) |
| 资料 | 内部正文命中及结果 | MaterialSearchMatch、MaterialSearchResult | [material_query_results.py](materials/material_query_results.py) |
| 资料 | search_materials 工具输入 | SearchMaterialsInput | [search_materials_contract.py](materials/search_materials_contract.py) |
| 资料 | search_materials 工具输出及定位 | SearchMaterialsOutput、MaterialSearchItem、MaterialMatchLocation | [search_materials_contract.py](materials/search_materials_contract.py) |
| 资料 | list_materials 工具输入 | ListMaterialsInput | [list_materials_contract.py](materials/list_materials_contract.py) |
| 资料 | list_materials 工具输出 | ListMaterialsOutput、MaterialListItem | [list_materials_contract.py](materials/list_materials_contract.py) |
| 资料 | 块内读取的内部结果 | MaterialReadResult | [material_query_results.py](materials/material_query_results.py) |
| 资料 | read_material 工具输入与公开输出 | ReadMaterialInput、ReadMaterialOutput、MaterialReadLocation | [read_material_contract.py](materials/read_material_contract.py) |
| 联网 | 内部候选网页 | WebSearchCandidate | [web_search_candidate.py](web/web_search_candidate.py) |
| 联网 | search_web输入与公开输出 | SearchWebInput、SearchWebOutput、WebSearchItem | [search_web_contract.py](web/search_web_contract.py) |
| 联网 | 独立网页资料收集的规划、审查及图状态；ResearchState的review_batches记录待检查批次，unreviewed记录超限未完成的候选；selected_alternatives记录用户明确选择的备用资料，不等同正式候选 | SearchPlan、AlternativeCandidate、SearchReview、ResearchCandidate、ResearchAlternative、ResearchState | [research_contract.py](web/research_contract.py) |
| 联网 | fetch_webpage输入与公开输出 | FetchWebpageInput、FetchWebpageOutput | [fetch_webpage_contract.py](web/fetch_webpage_contract.py) |
| 联网 | 内部网页内容与读取结果 | WebpageContent、WebpageReadResult | [webpage_content.py](web/webpage_content.py) |
| 技能 | 内部技能摘要 | SkillSummary | [skill_summary.py](skills/skill_summary.py) |
| 技能 | list_skills输入、公开输出和条目 | ListSkillsInput、ListSkillsOutput、SkillListItem | [list_skills_contract.py](skills/list_skills_contract.py) |
| 技能 | read_skill输入与公开输出 | ReadSkillInput、ReadSkillOutput | [read_skill_contract.py](skills/read_skill_contract.py) |
| 模板 | 模板结构事实与嵌套对象 | TemplateStructure、TemplateSlide、TemplateLayout、TemplateMaster、TemplateShape | [template_structure.py](templates/template_structure.py) |
| 模板 | inspect_template输入与公开输出 | InspectTemplateInput、InspectTemplateOutput | [inspect_template_contract.py](templates/inspect_template_contract.py) |
| 模板 | complete_template输入、补页计划及公开输出 | CompleteTemplateInput、TemplatePagePlan、CompleteTemplateOutput、CompletedTemplatePage | [complete_template_contract.py](templates/complete_template_contract.py) |
| 模板 | create_template_page输入、绘制对象与公开结果 | CreateTemplatePageInput、PageElement、CreateTemplatePageOutput | [create_template_page_contract.py](templates/create_template_page_contract.py) |
| 成品 | build_presentation输入、逐页计划、文字替换及结果 | BuildPresentationInput、PresentationPagePlan、TextReplacement、BuildPresentationOutput、BuiltPresentationPage | [build_presentation_contract.py](presentations/build_presentation_contract.py) |
| 成品 | 混合内容方案 | TextElement、ImageElement、VideoElement、AudioElement、ChartElement、ChartSeries、TableElement、ListElement、PresentationPageElement | [presentation_page_element.py](presentations/presentation_page_element.py) |
| 成品 | 图表坐标轴和整体显示样式 | ChartAxisStyle、ChartDisplayStyle | [presentation_chart_style.py](presentations/presentation_chart_style.py) |
| 成品 | 表格绘制方案 | PresentationTablePlan | [presentation_table_plan.py](presentations/presentation_table_plan.py) |
| 成品 | 列表绘制方案 | PresentationListPlan、PresentationListItem | [presentation_list_plan.py](presentations/presentation_list_plan.py) |
| 成品 | 位置、尺寸及颜色输入 | PresentationBox、Color | [presentation_object_geometry.py](presentations/presentation_object_geometry.py) |
| 对话 | HTTP 对话请求 | ChatRequest | [chat_request.py](chat/chat_request.py) |
| 对话 | 接收层内部问题与附件 | ChatSubmission、ChatAttachmentInput | [chat_request.py](chat/chat_request.py) |
| 对话 | 附件读取公开响应和安全错误 | ChatReadResponse、ChatAttachmentResponse、ChatErrorDetail、ChatErrorResponse | [chat_response.py](chat/chat_response.py) |
| 文档读取 | 正文块、读取结果、读取规模限制 | DocumentBlock、DocumentContent、DocumentReadLimits | [document_content.py](documents/document_content.py) |
| 健康检查 | HTTP 健康响应 | HealthResponse | [health_response.py](health/health_response.py) |
| 人工交互 | 预留问题正文（未接线） | UserQuestion | [user_question.py](interaction/user_question.py) |
| 人工交互 | 预留提问输入输出（工具已移除） | AskUserInput、AskUserOutput | [ask_user_contract.py](interaction/ask_user_contract.py) |

## 一条资料与三种不同用途

- MaterialSummary：后端登记的一份资料，含内部 project_id；不是工具的调用参数。
- ListMaterialsInput：模型发起一次目录查询时的参数，例如 origin、offset、limit；不含 project_id。
- ListMaterialsOutput：工具执行后给模型的结果，包含 items、total、next_offset；items 中只公开 MaterialListItem 的字段。
- MaterialPage：纯Python目录查询的内部结果，仍包含 MaterialSummary。它与对外工具输出不同，工具负责选择公开字段。

## 创建方与使用方

```text
宿主提供 MaterialSummary 列表
    ↓
create_list_materials_tool 绑定项目和目录快照
    ↓
模型提出调用参数 → ListMaterialsInput 校验
    ↓
list_project_materials 执行查询 → MaterialPage
    ↓
工具选择公开字段 → ListMaterialsOutput → 返回模型
```

实体构造后调用 validators/materials/material_metadata_validator.py，保证元数据合法。
查询代码在 domain/materials/material_catalog.py，Agent入口在 tools/materials/list_materials_tool.py。

## 类型与校验

- MaterialSummary、MaterialFragment、MaterialPage、MaterialSearchMatch、MaterialSearchResult：标准库 dataclass；前两种实体构造时执行各自字段校验。
- ListMaterialsInput、SearchMaterialsInput、ChatRequest、HealthResponse：Pydantic BaseModel，用于声明边界数据结构和执行校验。
- ListMaterialsOutput、MaterialListItem、SearchMaterialsOutput、MaterialSearchItem、MaterialMatchLocation：TypedDict，只描述字典类型，不自动执行运行时校验。
- 调用描述和参数描述会用于模型工具定义；普通Python注释和输出类型标注不会自动成为模型可见的返回Schema。

## 命名和扩展规则

1. 先按业务功能分组，如 materials、chat、health。新增功能只在实际开发时创建目录。
2. 模型工具统一用 `<操作>_contract.py`，集中定义该操作的输入、公开输出及其条目；类型仍用 `<操作>Input` / `<操作>Output`。
3. HTTP契约用 `<业务>_request.py` / `<业务>_response.py`，类型用 Request / Response；与Agent工具的Input / Output区分。
4. 业务数据按对象命名，例如 material_source.py；不使用笼统的 models.py、data.py、query.py。
5. 同一操作的输入输出放在同一契约文件；相关内部查询结果集中在 material_query_results.py。按职责、依赖和实际复用需求拆分，不按类数量机械拆文件，不强制复用HTTP与工具类型。
6. __init__.py不批量加载所有类型，使用时显式导入具体模块，避免依赖扩散。

对话流的result返回ChatReadResponse：需求分析、资料汇总、来源映射、报告和询问；选中文件时会解析并提炼，模板仍单独解析。
分页大纲的结构定义在 outlines/presentation_outline.py；模板识别等功能按各自模型说明。

## 当前附件数据来源（2026-11-05）

用户问题＋附件 → HTTP接收并关闭表单句柄 → 需求分析 → 选择文件时校验、读取和提炼 → 汇总 → ChatReadResponse。
不长期保存原文件，不创建项目/会话/资料目录Store，也不直接调用模型。DocumentBlock编号仅本次读取唯一。
之前的项目目录/落盘设计已按用户最新要求延期；MaterialSummary/MaterialFragment等既有工具结构暂时保留，尚未接收当前附件数据，不能当作已接线。
ChatAttachmentInput由接收层创建，包含原始bytes（禁止序列化/日志）；ChatSubmission仅内部使用，JSON客户端只能提交ChatRequest（message、可选template_key、可选previous_task_id）。
各读取器创建DocumentBlock/DocumentContent；DocumentReadLimits由API宿主从Settings组装。ChatAttachmentResponse/ChatReadResponse由API创建并公开，读取数据模型不依赖API、SDK或执行层。

## 第二个工具：正文检索数据流（2026-11-02）

解析模块提供MaterialFragment(project_id/source_id/version/block_id/text/page)，工具宿主同时提供目录摘要与正文快照。模型参数用SearchMaterialsInput校验，纯业务检索生成MaterialSearchResult，工具选择公开字段生成SearchMaterialsOutput。正文与目录版本必须一致，片段只能关联当前项目ready来源。page从1开始，未知为None；块ID由解析模块生成，不由搜索工具猜测。

MaterialFragment及内部检索结果为标准库dataclass；SearchMaterialsInput为Pydantic，公开输出为TypedDict。资料正文与目录的正式登记仍未实现，当前通过宿主传样本验证工具；没有新增数据库或全局Store。详情见[search_materials调试说明](../docs/调试/search_materials调试说明.md)。

## 第三个工具：正文读取数据流（2026-11-02）

宿主提供MaterialSummary与MaterialFragment快照 → ReadMaterialInput校验模型定位 → material_reader.read_project_material返回MaterialReadResult → 工具选择公开字段生成ReadMaterialOutput。

MaterialReadResult由读取业务创建、工具适配使用，包含内部fragment，不直接公开；公开输出不含project_id或本机路径。ReadMaterialInput为Pydantic，ReadMaterialOutput与MaterialReadLocation为TypedDict。共享的validate_material_content_data放在domain/materials/material_validator.py，检索和读取各自引用它，不互相依赖。详见[read_material调试说明](../docs/调试/read_material调试说明.md)。

## 联网候选与资料来源的边界（2026-11-02）

SearXNG适配器将供应商结果创建为WebSearchCandidate → WebSearchClient协议交付业务 → search_web工具选择公开字段返回SearchWebOutput。SearchWebInput由运行时校验模型参数。实体为标准库dataclass，输入为Pydantic，公开输出为TypedDict；模型目录不导入执行层。已接入真实SearXNG适配器。

candidate_id由URL的SHA-256生成，标识候选链接，不是资料目录source_id，不承诺创建可恢复的Store。engines记录SearXNG实际报告的来源列表，未知为空；研究流程的search_strategies另记请求策略。title/url/snippet不代表已抓取正文。fetch_webpage已能抓取静态网页；资料登记尚未接线，不能把工具结果当作可供共用资料工具使用的来源。当前不登记、不落盘、不保存查询历史。

## 字段说明约定（2026-11-03）

当前实体与TypedDict输出逐字段提供中文注释；输入通过Field(description=...)解释。阅读类型时先看字段附近注释，区分条数/字符数、None/null、版本与页码、候选ID与来源ID。源码注释不会自动传给模型，必要的返回字段含义同时写入工具description。具体搜索返回字段见[联网搜索调试说明](../docs/调试/search_web调试说明.md)。

## 网页读取数据流（2026-11-03）

HttpWebpageReader创建WebpageContent → WebpageReader协议返回业务 → read_webpage创建WebpageReadResult → fetch_webpage工具组装FetchWebpageOutput。FetchWebpageInput由运行时校验，输入说明通过Field进入Schema。内部dataclass只依赖标准库，不反向依赖执行层；公开输出不含本机路径或项目内部状态。没有创建资料source_id/版本或新的Store。字段及真实搜索测试见[网页读取调试说明](../docs/调试/fetch_webpage调试说明.md)。

## 技能发现数据流（2026-11-04）

LocalSkillCatalog扫描项目根目录skills/，parse_skill_metadata创建SkillSummary，目录返回SkillSummary元组（不合格式的技能记录日志并跳过）→工具调用filter_skills→组装SkillListItem/ListSkillsOutput。内部dataclass只依赖标准库；输入Pydantic校验keyword，输出TypedDict不自动校验。当前不建立技能注册Store或正文快照、不执行脚本；缺失版本返回None，不与资料version混淆。模型不选择本机目录。未来技能市场通过服务接口及适配器接入，现有协议保留摘要加载边界，具体远程契约待开发时确定。详见[list_skills调试说明](../docs/调试/list_skills调试说明.md)。

## 技能完整读取（2026-11-04）

ReadSkillInput由运行时校验skill_id；LocalSkillReader通过SkillReader协议返回普通str，工具显式组装ReadSkillOutput（skill_id/resource_path/content）。输入来源为list_skills编号，输出供模型阅读，不含本机绝对路径。正文包含YAML头部，不截断、不展开资源、不执行脚本；无新内部结果实体、缓存或状态。共享头部读取位于integrations/skills/skill_header_reader.py。详见[read_skill调试说明](../docs/调试/read_skill调试说明.md)。

## 模板结构数据流（2026-11-04）

宿主登记template_id到Path映射→LocalTemplateInspector读取真实文件并创建TemplateStructure→工具沿用公开事实返回InspectTemplateOutput。TemplateStructure及嵌套TypedDict本身不包含内部路径或SDK对象，因而共用于协议与输出，不复制同形内部实体。Pydantic仅校验工具输入，TypedDict输出不自动校验。模型通过说明理解坐标、关联和限制；页面角色留给后续Agent判断。真实样本登记目前在测试入口，正式上传登记尚未接线。详见[inspect_template调试说明](../docs/调试/inspect_template调试说明.md)。

模板阅读提示（2026-11-05）：`TemplateSlide`是实际页面，`TemplateLayout`是可复用版式，`TemplateMaster`是管理版式的上层设计；三者数量无需一致。详见模板结构文件的逐字段注释及模板调试说明中的初学者章节。本次仅补充说明，类型及公开字段未改变。

## 视觉识别模块（2026-11-05）

[TemplateVisualAnalysis](templates/template_visual_analysis.py)：Pydantic结构化视觉结果，由模型适配器创建并校验，供示例和未来Harness使用；与TemplateStructure的确定性结构事实区分。没有新增工具输入输出或Graph状态。字段为page_role、role_evidence、visible_texts、layout_description、main_colors、limitations；详见Store清单和视觉识别模块调试说明。

配置更新（2026-11-05）：Gotenberg根地址为config/settings.py中的Settings.gotenberg_base_url，字段说明见Store清单；Settings仍放config，不新增或移动数据模型。当前仅完成配置与服务健康检查，转换适配器未实现。

Gotenberg转换（2026-11-05）：输入pptx_bytes: bytes及file_name: str，输出PDF bytes，没有为单一字节结果增加实体。Settings新增gotenberg_timeout_seconds，配置仍放config，协议和错误放domain/templates，字段见Store清单。

## PDF页面图片（2026-11-05）

[PdfPageImage、PdfRenderResult](templates/pdf_page_image.py)：渲染器创建的不可变内部结果，测试及未来页面分析使用；定义PNG字节、PDF页码、像素尺寸、文件指纹、总页数和DPI，不包含PPT页码或磁盘路径。标准库dataclass不依赖PDFium、Pillow或Agent。不是Agent工具输入输出。字段详见Store清单，操作见[PDF页面图片调试说明](../docs/调试/PDF页面图片调试说明.md)。

## 日志诊断字段（2026-11-05）

request_id、operation_id等是diagnostics管理的运行上下文与日志摘要，不是业务实体或LangGraph状态，不新建数据模型。HTTP响应头X-Request-ID仅用于查日志；字段解释见[字段清单](../docs/Store清单.html)及[日志说明](../docs/调试/日志使用说明.md)。本次未改变工具输入输出字段。

## 人工提问数据定义（2026-11-05，仅预留）

按用户决定移除ask_user工具、内存收集器与对应测试。仅保留UserQuestion、AskUserInput、AskUserOutput及其共享字段校验，当前没有实际创建/提交/存储/回答流程。UserQuestion.question_id只要求非空字符串，未来由实际接入方分配，不限制UUID格式或提前冻结图状态。

这些类型不会自动提问、显示界面或暂停程序；后续在子智能体与LangGraph开发中讨论真实交互，再决定如何复用字段。无新增环境变量或依赖，字段说明见[Store清单](../docs/Store清单.html)。

## 对话附件读取（2026-11-05）

旧models/uploads及FileUploadRequest/Response已移除；现由chat/chat_request.py、chat/chat_response.py和documents/document_content.py描述输入输出。
实际读取器归integrations/documents，纯内容/Office包检查归domain/uploads；文件检查能力仍保留，移除的是独立上传HTTP入口。
详见[对话附件读取说明](../docs/调试/对话附件读取调试说明.md)。

## RustFS模板资源（2026-11-06）

[template_resource_response.py](templates/template_resource_response.py)集中定义TemplateResourceItem、TemplateResourceListResponse、TemplateResourceErrorDetail、TemplateResourceErrorResponse。
存储适配器创建条目和分页结果，API公开返回；错误由HTTP边界选择。条目为候选，不含模板正文/凭据/下载URL，不承诺兼容或授权验证。object_key完整保留桶内路径，file_name仅展示，不能用文件名判唯一。
聊天ChatAttachmentInput/ChatAttachmentResponse已删除purpose；multipart仅message和可选file，全部参考资料。template_key已接下载和PPTX解析，ChatTemplateResponse独立返回模板内容；没有跨请求模板选择状态。

## 当前对话字段调整（2026-11-06）

ChatRequest及其内部派生ChatSubmission新增template_key: str | None，默认None，1–1024字符，保留完整对象名（含目录/空格），不是URL；指定后真实下载读取。
历史版本仅回显解析结果；当前ChatReadResponse通过SSE result返回资料图状态。
此前旧版api/chat_dependencies.py已移除；当前/chat/stream接入网页资料研究和SSE。

## OSS模板读取响应（2026-11-06）

ChatTemplateResponse位于chat/chat_response.py，复用文件元数据/内容字段并增加object_key。chat_template_processing从下载和现有读取结果创建，API公开返回为ChatReadResponse.template；没有模板时null。
S3TemplateFileReader通过TemplateFileReader协议返回bytes，不创建HTTP模型、文件路径或Store；字节由本次宿主持有，解析后不承诺可再次取回。

## 公共图片OCR（2026-11-06）

[ocr/ocr_result.py](ocr/ocr_result.py)定义OcrTextRegion和OcrResult。由integrations/ocr的识别器创建，供测试与未来文档读取器使用，当前为内部返回数据，不是HTTP、Agent或LangGraph状态。字段包括文字、四边形像素位置、置信分、EXIF校正后尺寸；text属性派生全文。来源ID/页码由调用方关联，不塞入OCR结果。协议与OcrError位于domain/ocr，不放进models。详见[字段清单](../docs/Store清单.html#ocr-fields)与[OCR调试说明](../docs/调试/OCR模块调试说明.md)。

## PDF OCR读取字段语义（2026-11-06）

未新增类型或字段。DocumentBlock.text允许来自本地OCR，DocumentContent.pages_without_text表示本次读取后仍无文字的页（PDF启用OCR时为OCR后）；page保留原PDF页码。OCR区域结果由PDF读取器内部消费，不直接成为HTTP输出。本地OCR不是云端视觉大模型调用。见[PDF OCR说明](../docs/调试/PDF文字与OCR调试说明.md)。

## PPTX检查工具（2026-11-06）

[presentations/check_presentation_contract.py](presentations/check_presentation_contract.py)集中定义CheckPresentationInput（模型输入artifact_id）、CheckPresentationOutput及PresentationCheckItem（检查器创建、工具公开）。输入由Pydantic校验，TypedDict结果只描述类型；工具不公开宿主路径/SDK对象。passed只覆盖本轮必过规则；未知值null，未实现规则not_checked。PresentationChecker协议和PresentationCheckError在domain/presentations。字段详见[字段清单](../docs/Store清单.html#presentation-check-fields)及[调试说明](../docs/调试/check_presentation调试说明.md)。

网页资料整理：`web/web_research_summary.py` 中 `WebResearchPage` 是不含正文的网页元数据；`WebPageExtraction` 是单页模型提炼，`WebResearchSummary`、`WebSummaryPoint` 和 `WebContentIssue` 是累计要点的模型汇总及内容问题。工作流检查候选编号并维护 `ResearchState.page_extractions`；临时正文仅用于单页模型调用，不进入图状态或检查点，也不是已登记资料。

网页内容包含最多100条静态链接links；ResearchState的max_pages限制读取次数，effective_count统计模型要点引用的来源数，summary.follow_links记录已读页面编号及其实际链接。该计数不保证事实可靠，也不保证识别语义转载。

通用问询：UserQuestion由宿主创建并在进入中断节点前保存；workflows/interaction/ask_user.py输出问题数据并校验恢复时的question_id和answer。ask_user_contract.py仍为模型工具预留契约，当前不是已接入的Agent工具。终端演示见examples/ask_user_demo.py。

询问演示的图状态使用列表保存options，恢复后构造UserQuestion时转成tuple；LangGraph检查点反序列化不应被假定会保留tuple。

ResearchState.stop_reason运行中为空字符串，结束后按目标达到、全部搜索失败、读取上限、搜索上限顺序标识主要原因（Literal仅静态提示）：target_reached、search_limit、page_limit或search_failed；模型缺口见summary.gaps，失败见read_failures，截断见pages.truncated。

网页检查报告：`web/research_report.py` 的ResearchReport与ResearchIssue由domain/web/research_report_builder.py在网页图结束后生成；报告包含可用内容、当前与目标来源数、停止原因和问题列表，不包含内部feedback，不直接实现前端卡片。

网页候选检查超时时ResearchState.stop_reason为model_timeout、status为interrupted，review_timeout_candidates保留当前及本轮剩余未检查候选；报告issues中类型review_timeout逐条关联编号。已结束图不支持直接resume，进程退出内存状态丢失。

网页资料汇总中，`ResearchState.summary_length_exceeded` 表示累计汇总因输出超限未完成；`summary` 与 `effective_count` 是上次成功汇总的结果，最新单页要点仍在 `page_extractions`。最终 `stop_reason=summary_length_exceeded`，报告 `issues` 中的 `summary_unfinished` 指向尚未完成汇总的候选编号；不能据此判断资料不足或充分。图已结束，不支持直接通过 `resume` 重试该结束状态。

网页资料图 `ResearchState.waiting_question` 保存由finalize节点创建的待回答问题字典，含question_id、question、reason、options、allow_free_text；ask_user暂停前写入检查点。无待回答问题时为None，回答后清空；数据在工作流实例内存中；/chat/stream通过waiting_question公开，HTTP回答接口尚未实现。

ChatReadResponse、ChatResearchSource和ChatQuestion定义在chat/chat_response.py，由API根据资料图构造：analysis为需求分析，summary及summary_inputs保留要点和来源映射，sources为网页来源，report为阶段报告，waiting_question为待回答问题；attachment_analyzed表示文件提炼成功，attachment_file_name为上传文件名。模板仍单独解析；不返回附件字节或正文。

/chat/stream 的SSE start/progress/result/error公开字段见 docs/Store清单.html 和接口调试说明；result复用ChatReadResponse；资料充分且生成成功时包含outline；thinking事件仅在配置开启且LangChain返回标准推理块时出现。

网页工作流使用MaterialSummaryAgent进行通用汇总，并映射回网页契约；MaterialSummaryAgent使用materials/material_summary.py的通用要点、来源引用、汇总要点及问题契约，可汇总网页与文件提炼结果；网页工作流已接入，文件尚未通过HTTP接入。FileExtractionAgent 通过注入的 DocumentFileReader 校验并按格式解析文件，也可接收已解析的 DocumentContent；输出 materials/file_extraction.py 中的 FileExtraction（文件名、要点、读取警告和无文字页）；FileExtractionPoint 的 block_ids 在本次解析结果中定位原文。FileExtractionBatch 仅用于模型分批输出。这些是内部模型，文件尚未登记为资料，也未接入HTTP。

文件提炼结果新增 status（completed/interrupted）、processed_characters、total_characters 和 failure_reason；字符计数不等于 token，interrupted 的要点只覆盖已处理部分。

FileExtraction.resume_id：中断时为同一Agent实例内一次性恢复编号，完成时为None；结果本身不包含待处理正文，进程重启或实例销毁后无法恢复。

通用汇总内部契约：materials/material_summary.py的MaterialInputPoint由转换函数创建并供MaterialSummaryAgent使用；MaterialReference记录来源类型、调用方来源编号及文件块编号；MaterialSummary的point_ids引用输入要点，通过references_for还原来源。均非HTTP公开模型，编号不是资料库登记编号。

ResearchState.defer_user_question由run调用方设置，默认False；True时网页资料不足返回insufficient及报告、不创建等待问题；模型处理失败仍为interrupted。该字段保存在当前图检查点，不是HTTP输入。

文件处理报告：materials/file_extraction.py 的 FileProcessingReport 由 FileExtractionAgent 创建并返回上层，包含阶段、固定错误代码、安全提示、是否已有要点及读取警告；校验或读取失败为 failed，模型处理未完成为 interrupted。报告不是正文，不由汇总模型当作资料使用；历史手工构造样本的 report 可为空。

ResearchState.workflow_error_stage和workflow_error_kind在网页图执行失败时保存节点与固定分类（model_connection/model_timeout/execution_failed），初始为None。返回status=interrupted、stop_reason=workflow_error及workflow_failed报告；错误原文不进入状态。状态快照用于同实例resume，返回报告本身不覆盖检查点。

FileExtraction.failure_reason包含processing_failed：未知文件读取或批次模型处理故障，以安全报告返回；取消和调用参数错误不作为业务成功返回。

MaterialCollectionState、MaterialCollectionReport 定义在 materials/material_collection_state.py，由资料图在内存检查点创建：记录问题、可选附件、网页与文件阶段结果、汇总输入与报告、状态和待回答问题；附件字节只在内存，非HTTP契约。

需求分析：materials/request_analysis.py 的 RequestAnalysis 由 RequestAnalysisAgent 返回，包含来源模式、执行顺序、是否询问、问题及简短原因；资料工作流使用它选择分支，不保证意图理解准确，尚未接入HTTP。

RequestAnalysisResult为需求分析调用的内部结果：status、plan、error_code和安全message；失败时plan为None，不允许继续按计划执行。尚未接入HTTP。

当前 `/chat/stream` 的 ChatReadResponse 是资料收集首轮SSE result：status、notice、analysis、summary、summary_inputs、sources、report、waiting_question、attachment_analyzed、attachment_file_name、template；尚未提供HTTP回答和上传补充资料后的恢复。旧版附件仅解析/网页专用结果描述属于历史。

PresentationOutline、OutlineSlide、OutlineBullet 定义在 outlines/presentation_outline.py，供资料工作流和 ChatReadResponse 使用。`slides` 顺序即页序，`role` 可为 `cover`、`content` 或 `closing`，大纲要点的 `point_ids` 通过 `summary_inputs` 关联实际网页或文件块。最终模型正常编排时由 MaterialSummaryAgent 构造大纲，模型整理失败且所需来源已就绪时可由程序按提炼顺序编排草稿。返回草稿时 `status=interrupted`，`outline_error` 保留故障分类。

网页研究内部状态 ResearchState.provided_urls_only 表示本轮直接使用用户提供的网址及其同站相关链接；ResearchReport.stop_reason 的 provided_pages_exhausted 表示这些候选已处理完但仍不足，followup_unread 问题列出达到读取上限时未处理的候选编号。该状态由网页工作流创建，HTTP仅通过报告公开结果，不表示来源事实已核验。

MaterialSummary.outline 在最终资料汇总中可包含 PresentationOutline，中间汇总为 `null`。MaterialCollectionState.use_current 记录用户是否选择使用现有资料。聊天有可用要点即可交付当前大纲。覆盖范围和内容问题随报告返回。

MaterialSummaryContent 包含 `points` 和 `issues`，供聊天响应的 `summary` 使用。MaterialSummary 增加可选的 `outline`，供汇总和工作流使用，聊天响应单独公开 `outline`。最终编排模型输出 materials/material_summary.py 中的 MaterialOutlineDraft。它提供 `title`、`sections` 和 `issues`，未编排时 `title` 为空、`sections` 为空，可在 `points` 中返回精简要点。每项 MaterialOutlineSection 有页标题 `title` 和按顺序引用的 `keys`，例如 `k1`。程序验证编号后从已提炼的资料填入正文，并把大纲引用还原为原始 `point_id`。

ResearchState.summary_deferred 表示网页要点统一汇总留给上层；状态 collected 和停止原因 summary_deferred 仅表示单页提炼已结束，不是资料充分结论。ResearchReport.content_review_deferred 明确提示该边界；source_count在此表示有提炼要点的网页数。

网页流程发生workflow_error且尚无汇总时，ResearchReport.source_count为已有非空单页提炼的网页数，has_usable_content仅表示已有要点；上层中断结果的summary_inputs保留成功提炼的要点。HTTP重试及使用部分资料继续尚未接线。

搜索候选WebSearchCandidate与WebSearchItem的engines仅表示供应商提供的来源引擎；Tavily不提供时为空。WEB_SEARCH_PROVIDER和TAVILY_API_KEY由Settings读取，密钥不进入数据模型或工具输出。

ChatRequest.previous_task_id 接受上一轮任务编号，ChatReadResponse 回显父轮并返回新的 task_id。ChatReadResponse.file_sources 将累计文件来源编号关联到文件名。MaterialCollectionState 通过 prior_topic、prior_inputs、prior_pages、file_sources 和 file_source_id 保留编排所需的上下文及来源。