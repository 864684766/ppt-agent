# 数据模型导航

先按功能找目录，再按用途找文件。这里的“模型”指数据结构，不是大语言模型客户端。

| 功能 | 你想找什么 | 类型 | 定义位置 |
| --- | --- | --- | --- |
| 资料 | 单份内部资料数据 | MaterialSummary | [material_summary.py](materials/material_summary.py) |
| 资料 | 内部目录查询的返回页 | MaterialPage | [material_page.py](materials/material_page.py) |
| 资料 | list_materials 工具输入 | ListMaterialsInput | [list_materials_input.py](materials/list_materials_input.py) |
| 资料 | list_materials 工具输出 | ListMaterialsOutput、MaterialListItem | [list_materials_output.py](materials/list_materials_output.py) |
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

- MaterialSummary、MaterialPage：标准库 dataclass；MaterialSummary 构造时执行业务字段校验。
- ListMaterialsInput、ChatRequest、HealthResponse：Pydantic BaseModel，用于声明边界数据结构和执行校验。
- ListMaterialsOutput、MaterialListItem：TypedDict，只描述字典类型，不自动执行运行时校验。
- 调用描述和参数描述会用于模型工具定义；普通Python注释和输出类型标注不会自动成为模型可见的返回Schema。

## 命名和扩展规则

1. 先按业务功能分组，如 materials、chat、health。新增功能只在实际开发时创建目录。
2. 模型工具统一用 `<操作>_input.py` / `<操作>_output.py`，类型统一用 `<操作>Input` / `<操作>Output`。
3. HTTP契约用 `<业务>_request.py` / `<业务>_response.py`，类型用 Request / Response；与Agent工具的Input / Output区分。
4. 业务数据按对象命名，例如 material_summary.py；不使用笼统的 models.py、data.py、query.py。
5. 输入输出属于同一操作，放在同一功能目录；只对真正复用的数据结构做共享，不强制复用HTTP与工具类型。
6. __init__.py不批量加载所有类型，使用时显式导入具体模块，避免依赖扩散。

当前对话回复是SSE事件流，不存在普通JSON的ChatResponse；不要为了目录对称编造输出类。
当前未开发大纲、模板识别等结构化Agent结果，它们尚无可供导航的类型定义。
