# 第一个工具：list_materials

状态：已完成（独立工具与约定的两项测试）；正式资料与HTTP/聊天接线仍按后续任务开发。

本工具仅实现“查看已登记的业务参考资料目录”。正文检索已作为独立的search_materials工具实现；上传、网页抓取、数据库、MCP 和聊天中的工具选择循环尚未接入。这里的样本不代表真实上传文件，也不会写入应用状态。

模型位置总索引见 [models/README.md](../models/README.md)。同一功能的所有输入、输出与业务数据集中在 models/materials/。

## 文件与依赖方向

- `models/materials/material_source.py`：单份资料字段与构造校验入口。
- `models/materials/material_query_results.py`：目录业务查询的内部返回类型。
- `validators/materials/material_metadata_validator.py`：资料自身的字段和字段组合合法性规则，仅依赖标准库。
- `domain/materials/material_catalog.py`：项目隔离、来源/名称筛选、稳定排序和分页。
- `models/materials/list_materials_contract.py`：集中查看工具输入与公开输出。Input用Pydantic和`Field(description=...)`校验、解释参数；Output及条目用TypedDict描述字典结构，不自动校验。
- `tools/materials/list_materials_tool.py`：LangChain `@tool` 薄入口，声明工具使用场景并选择可公开返回字段。
- `tests/test_list_materials.py`：只保留工具定义JSON与调用结果两个测试，并打印供人查看。

导入方向为 `tools → domain → models.materials.material_source`，工具另引用 `models.materials.list_materials_contract`；实体另调用纯校验模块 `validators.materials.material_metadata_validator`；校验模块不反向引用实体。models 不反向引用查询或执行模块。domain 不依赖 LangChain、FastAPI、配置、网络或数据库。调用方负责提供已经登记好的业务资料，不把模板和技能资源混入其中。目录按 source_id 字符串升序排列，不按上传时间排列。

## 如何创建与调用

在项目根目录运行 `uv run --locked python`，将下列代码粘贴到 Python 交互窗口；也可以在 PyCharm 使用项目虚拟环境的 Python Console 执行。若 Console 无法导入包，先把其工作目录设置为项目根目录。

```python
from models.materials.material_source import MaterialSummary
from tools.materials import create_list_materials_tool

# 示例数据由宿主提供，不是工具自动扫描硬盘得到的。
materials = [
    MaterialSummary(
        project_id="demo",
        source_id="s01",
        name="员工手册.docx",
        origin="uploaded",
        format="docx",
        status="ready",
        version="v1",
    ),
    MaterialSummary(
        project_id="demo",
        source_id="s02",
        name="政策公告",
        origin="web",
        format="html",
        status="ready",
        version="v1",
        url="https://example.org/policy",
    ),
]

# 这里先由宿主绑定项目，不让模型自行切换项目。
material_tool = create_list_materials_tool(project_id="demo", materials=materials)

# 直接调用入口用于测试；接入 Agent 后，由运行时执行模型的调用请求。
print(material_tool.invoke({"origin": "uploaded", "limit": 10}))
```

预期返回（展示为 JSON）：

```json
{
  "items": [
    {
      "source_id": "s01",
      "name": "员工手册.docx",
      "origin": "uploaded",
      "format": "docx",
      "status": "ready",
      "version": "v1",
      "url": null,
      "page_count": null
    }
  ],
  "total": 1,
  "next_offset": null
}
```

查看供模型使用的 function-tool 定义：

```python
from langchain_core.utils.function_calling import convert_to_openai_tool
import json
print(json.dumps(convert_to_openai_tool(material_tool), ensure_ascii=False, indent=2))
```

模型只会得到 `origin`、`name_contains`、`offset`、`limit` 这些参数，不会得到项目选择参数或完整目录。外层未来可将该工具绑定到 Agent；当前 `/ppt-agent/v1/chat` 有附件时返回读取结果，无附件只回显消息；全部JSON、不调用模型，也不会调用资料目录工具，尚无正式目录接线。

## 模型怎样看懂工具和参数

参考用户的 `3_1_tool_decorator_demo.py` 中显式 `description` 和 `args_schema` 的写法：

```python
@tool(
    "list_materials",
    description="当需要查看当前项目业务资料目录时使用……",
    args_schema=ListMaterialsInput,
)
```

`description` 告诉模型什么时候选这个工具，优先于函数文档字符串。`ListMaterialsInput` 的每个 `Field(description=...)` 解释参数如何填。普通 `#` 注释用于人学习，不会自动发送给模型。`parse_docstring=True` 是另一种提取参数说明的方式，本工具已有显式参数模型，无须再维护一套自动解析来源。

当前版本转换后的工具定义保留字段 description 和 default，但省略 examples。为保证例子确实可见，必要例子也写进 description；例如 offset 告诉模型把上次返回的 next_offset 用于下一次查询。`examples` 仍保留在原始 Pydantic Schema 里，供本地查看。当前测试打印转换后的完整JSON，并检查工具及参数说明存在，方便直接查看。

实体现在从 `models.materials.material_source` 导入，查询从 `domain.materials` 导入，工具工厂仍从 `tools.materials` 导入。阅读顺序建议是业务实体 → validators/materials/material_metadata_validator.py → domain/materials/material_catalog.py → 工具入参/结果 → tools/materials/list_materials_tool.py。

## 如何查找输入、输出和校验

- 实体文件 `material_source.py` 回答“一份业务资料有什么字段”。其 `__post_init__` 调用规则，保证通过正常构造路径不能创建非法资料。
- `validators/materials/material_metadata_validator.py` 回答“这些资料字段组合是否合法”，例如网页资料必须有URL。它接收普通值，不导入实体，不查询文件和网络。
- `list_materials_contract.py` 同时回答“模型怎么调用”和“允许公开什么结果”。Input声明分页、筛选参数，Pydantic Field负责校验和模型Schema说明；Output与条目使用TypedDict，只描述公开字典类型，不自动做运行时校验。
- `domain/materials/material_catalog.py` 回答“在当前项目中如何查”，负责项目范围筛选；多条记录的source_id唯一性由共享的material_validator.py检查。

## 参数与结果

| 参数 | 默认值 | 规则 |
| --- | --- | --- |
| `origin` | `all` | `all` / `uploaded` / `web` |
| `name_contains` | 空字符串 | 名称字面子串，不区分大小写，忽略两端空白；最多 200 字符，不是全文或正则搜索 |
| `offset` | 0 | 非负整数，从 0 开始；超出结果数返回空页 |
| `limit` | 20 | 1–100 的整数 |

拒绝未知参数以及把字符串、布尔值当作整数。`total` 是筛选后、分页前的总数；`next_offset` 为下一页偏移，没有下一页时为 `None`。Python 的 `None` 在 JSON 中显示为 `null`。

`pending` 表示尚待解析，`ready` 表示正文可供后续读取，`failed` 表示解析失败；三种状态均可列出。页数未知为 `None`。模型可依据状态选择后续操作，但本工具不会执行解析或重试。

当前使用不可变目录快照：修改原来的 materials 列表不会改变已创建工具的结果；需要反映新增或更新资料时，宿主重新提供快照并创建工具。分页应持续使用同一工具/快照。没有全局可变 Store、数据库或持久化。

模型参数错误抛 `pydantic.ValidationError`；宿主提供空项目 ID、重复 source_id 或非法元数据时抛 `ValueError`。这些错误不会伪装成空列表。工具运行时的错误消息适配在接入 Agent 循环时另做，本次未向 HTTP 暴露异常。

## 单元测试与断点：只看两件事

当前文件只保留两个测试：

1. `test_tool_calling_json`：打印转换后的完整function-tool JSON，验证JSON可解析且有工具名、说明和四个参数。
2. `test_tool_return_result`：打印调用参数与实际返回值，和样本预期对比。

运行并显示输出：

```powershell
uv run --locked python -m pytest tests/test_list_materials.py -s -q
```

`-s` 关闭pytest的输出捕获，让成功测试的print也显示；`-q`减少测试框架的提示。只运行第二项：

```powershell
uv run --locked python -m pytest tests/test_list_materials.py::test_tool_return_result -s -q
```

PyCharm使用项目`.venv`解释器；右键运行/调试此测试文件，在pytest运行配置的Additional Arguments（附加参数）填写`-s`，即可直接查看print输出。在`convert_to_openai_tool(...)`或`material_tool.invoke(arguments)`设置断点，观察工具定义和返回值。

测试文件的`material_tool` fixture创建两条演示资料：员工手册（uploaded）与政策公告（web）。第二项传入`{"origin": "uploaded", "limit": 10}`，预期只返回员工手册。需要尝试其他输入时，修改该测试中的arguments，并同步调整预期结果。

已验证：2026-11-02，按用户最新范围收敛后的2个测试通过。此前的34项详细检查已从当前测试文件移除，当前不宣称这2项覆盖那些场景。测试不调用真实模型，不访问网络。

第一项输出是“提供给模型的工具定义”，不是模型已经生成了tool_calls，也不表示已验证模型会正确选用工具。第二项是直接invoke工具的实际返回结果。当前无新增HTTP工具接口，不能直接使用Postman调用；现有聊天接口还没有工具调用循环。

## 公共目录校验的职责（2026-11-02）

`../domain/materials/material_validator.py`中的`validate_material_catalog`只校验项目编号和当前项目内的来源编号唯一性，通过时返回`None`，失败抛出`ValueError`。目录查询和正文关联校验直接复用它，不再通过查询、排序和分页来间接触发校验。目录查询和正文检索各自依赖这一共享模块，彼此不导入对方的操作模块。它是内部业务函数，不是Agent工具。单份实体字段校验仍在实体构造时执行。目录公共校验现在先于查询参数校验；多项输入同时无效时，可能优先报告目录错误。
