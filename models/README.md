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
| 联网 | fetch_webpage输入与公开输出 | FetchWebpageInput、FetchWebpageOutput | [fetch_webpage_contract.py](web/fetch_webpage_contract.py) |
| 联网 | 内部网页内容与读取结果 | WebpageContent、WebpageReadResult | [webpage_content.py](web/webpage_content.py) |
| 技能 | 内部技能摘要 | SkillSummary | [skill_summary.py](skills/skill_summary.py) |
| 技能 | list_skills输入、公开输出和条目 | ListSkillsInput、ListSkillsOutput、SkillListItem | [list_skills_contract.py](skills/list_skills_contract.py) |
| 技能 | read_skill输入与公开输出 | ReadSkillInput、ReadSkillOutput | [read_skill_contract.py](skills/read_skill_contract.py) |
| 模板 | 模板结构事实与嵌套对象 | TemplateStructure、TemplateSlide、TemplateLayout、TemplateMaster、TemplateShape | [template_structure.py](templates/template_structure.py) |
| 模板 | inspect_template输入与公开输出 | InspectTemplateInput、InspectTemplateOutput | [inspect_template_contract.py](templates/inspect_template_contract.py) |
| 对话 | HTTP 对话请求 | ChatRequest | [chat_request.py](chat/chat_request.py) |
| 健康检查 | HTTP 健康响应 | HealthResponse | [health_response.py](health/health_response.py) |

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

当前对话回复是SSE事件流，不存在普通JSON的ChatResponse；不要为了目录对称编造输出类。
当前未开发大纲、模板识别等结构化Agent结果，它们尚无可供导航的类型定义。

## 真实数据来源（已确认，登记模块尚未实现）

上传业务文件 → 后端保存原文件到本地磁盘 → 读取实际元数据并创建MaterialSummary → 写入当前项目内存资料目录 → 宿主用目录快照创建list_materials工具。

初始pending、未知页数None；解析/本机OCR成功后用新的不可变摘要替换为ready，失败则failed。正文与来源定位单独保存，不进入目录摘要。资料或状态更新后需重建工具；同轮分页固定快照。第一阶段目录不要求数据库，重启不承诺恢复。模板/技能单独登记。测试样本和正式摘要使用相同类型，但测试样本不作为正式资料写入应用。

## 第二个工具：正文检索数据流（2026-11-02）

解析模块提供MaterialFragment(project_id/source_id/version/block_id/text/page)，工具宿主同时提供目录摘要与正文快照。模型参数用SearchMaterialsInput校验，纯业务检索生成MaterialSearchResult，工具选择公开字段生成SearchMaterialsOutput。正文与目录版本必须一致，片段只能关联当前项目ready来源。page从1开始，未知为None；块ID由解析模块生成，不由搜索工具猜测。

MaterialFragment及内部检索结果为标准库dataclass；SearchMaterialsInput为Pydantic，公开输出为TypedDict。资料正文与目录的正式登记仍未实现，当前通过宿主传样本验证工具；没有新增数据库或全局Store。详情见[search_materials调试说明](../docs/search_materials调试说明.md)。

## 第三个工具：正文读取数据流（2026-11-02）

宿主提供MaterialSummary与MaterialFragment快照 → ReadMaterialInput校验模型定位 → material_reader.read_project_material返回MaterialReadResult → 工具选择公开字段生成ReadMaterialOutput。

MaterialReadResult由读取业务创建、工具适配使用，包含内部fragment，不直接公开；公开输出不含project_id或本机路径。ReadMaterialInput为Pydantic，ReadMaterialOutput与MaterialReadLocation为TypedDict。共享的validate_material_content_data放在domain/materials/material_validator.py，检索和读取各自引用它，不互相依赖。详见[read_material调试说明](../docs/read_material调试说明.md)。

## 联网候选与资料来源的边界（2026-11-02）

SearXNG适配器将供应商结果创建为WebSearchCandidate → WebSearchClient协议交付业务 → search_web工具选择公开字段返回SearchWebOutput。SearchWebInput由运行时校验模型参数。实体为标准库dataclass，输入为Pydantic，公开输出为TypedDict；模型目录不导入执行层。已接入真实SearXNG适配器。

candidate_id由URL的SHA-256生成，标识候选链接，不是资料目录source_id，不承诺创建可恢复的Store。title/url/snippet不代表已抓取正文。fetch_webpage已能抓取静态网页；资料登记尚未接线，不能把工具结果当作可供共用资料工具使用的来源。当前不登记、不落盘、不保存查询历史。

## 字段说明约定（2026-11-03）

当前实体与TypedDict输出逐字段提供中文注释；输入通过Field(description=...)解释。阅读类型时先看字段附近注释，区分条数/字符数、None/null、版本与页码、候选ID与来源ID。源码注释不会自动传给模型，必要的返回字段含义同时写入工具description。具体搜索返回字段见[联网搜索调试说明](../docs/search_web调试说明.md)。

## 网页读取数据流（2026-11-03）

HttpWebpageReader创建WebpageContent → WebpageReader协议返回业务 → read_webpage创建WebpageReadResult → fetch_webpage工具组装FetchWebpageOutput。FetchWebpageInput由运行时校验，输入说明通过Field进入Schema。内部dataclass只依赖标准库，不反向依赖执行层；公开输出不含本机路径或项目内部状态。没有创建资料source_id/版本或新的Store。字段及真实搜索测试见[网页读取调试说明](../docs/fetch_webpage调试说明.md)。

## 技能发现数据流（2026-11-04）

LocalSkillCatalog扫描项目根目录skills/，parse_skill_metadata创建SkillSummary，目录返回SkillSummary元组（不合格式的技能记录日志并跳过）→工具调用filter_skills→组装SkillListItem/ListSkillsOutput。内部dataclass只依赖标准库；输入Pydantic校验keyword，输出TypedDict不自动校验。当前不建立技能注册Store或正文快照、不执行脚本；缺失版本返回None，不与资料version混淆。模型不选择本机目录。未来技能市场通过服务接口及适配器接入，现有协议保留摘要加载边界，具体远程契约待开发时确定。详见[list_skills调试说明](../docs/list_skills调试说明.md)。

## 技能完整读取（2026-11-04）

ReadSkillInput由运行时校验skill_id；LocalSkillReader通过SkillReader协议返回普通str，工具显式组装ReadSkillOutput（skill_id/resource_path/content）。输入来源为list_skills编号，输出供模型阅读，不含本机绝对路径。正文包含YAML头部，不截断、不展开资源、不执行脚本；无新内部结果实体、缓存或状态。共享头部读取位于integrations/skills/skill_header_reader.py。详见[read_skill调试说明](../docs/read_skill调试说明.md)。

## 模板结构数据流（2026-11-04）

宿主登记template_id到Path映射→LocalTemplateInspector读取真实文件并创建TemplateStructure→工具沿用公开事实返回InspectTemplateOutput。TemplateStructure及嵌套TypedDict本身不包含内部路径或SDK对象，因而共用于协议与输出，不复制同形内部实体。Pydantic仅校验工具输入，TypedDict输出不自动校验。模型通过说明理解坐标、关联和限制；页面角色留给后续Agent判断。真实样本登记目前在测试入口，正式上传登记尚未接线。详见[inspect_template调试说明](../docs/inspect_template调试说明.md)。

模板阅读提示（2026-11-05）：`TemplateSlide`是实际页面，`TemplateLayout`是可复用版式，`TemplateMaster`是管理版式的上层设计；三者数量无需一致。详见模板结构文件的逐字段注释及模板调试说明中的初学者章节。本次仅补充说明，类型及公开字段未改变。

## 视觉识别模块（2026-11-05）

[TemplateVisualAnalysis](templates/template_visual_analysis.py)：Pydantic结构化视觉结果，由模型适配器创建并校验，供示例和未来Harness使用；与TemplateStructure的确定性结构事实区分。没有新增工具输入输出或Graph状态。字段为page_role、role_evidence、visible_texts、layout_description、main_colors、limitations；详见Store清单和视觉识别模块调试说明。

配置更新（2026-11-05）：Gotenberg根地址为config/settings.py中的Settings.gotenberg_base_url，字段说明见Store清单；Settings仍放config，不新增或移动数据模型。当前仅完成配置与服务健康检查，转换适配器未实现。

Gotenberg转换（2026-11-05）：输入pptx_bytes: bytes及file_name: str，输出PDF bytes，没有为单一字节结果增加实体。Settings新增gotenberg_timeout_seconds，配置仍放config，协议和错误放domain/templates，字段见Store清单。
