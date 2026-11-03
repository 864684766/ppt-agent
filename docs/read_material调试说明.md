# 第三个工具：read_material

状态：已完成（独立业务模块、LangChain工具及约定的两项测试）；未接HTTP、真实模型选工具、MCP、文件上传、解析/OCR或正式内存仓库。测试样本是手写文本，不是实际上传资料或法律依据。

## 运行与断点

```powershell
uv run --locked python -m pytest tests/test_read_material.py -s -q
```

2026-11-02验证：2项通过；三个工具一起运行共6项通过。

1. `test_tool_calling_json`打印完整function-tool JSON，确认可解析、必填字段及所有参数说明可见。
2. `test_tool_return_result`打印首次和续读参数、返回字典，并对比样本预期。仍只有这两项测试，不新增边界测试矩阵。

PyCharm用pytest配置调试，在Additional Arguments填`-s`显示print。可在`material_read_tool.invoke(arguments)`、`read_material`、`read_project_material`内设置断点；停在print行时需F8执行后才能看到输出。当前没有HTTP入口，不能直接用Postman调用这个工具。

## 参数与例子

```json
{"source_id":"s01","version":"v1","block_id":"block_31","offset":0,"max_chars":5}
```

source_id、version和block_id必填，通常取自search_materials的source_id、version、location.block_id，不是文件路径或页码。项目由宿主绑定，不交给模型。offset默认0、必须非负；max_chars默认2000、范围1–8000，都是Python字符单位，不是字节或token。

样本完整块为“演示正文：请核对完整条件。”，共13个字符，首次返回：

```json
{
  "source_id": "s01",
  "version": "v1",
  "location": {"block_id": "block_31", "page": 12},
  "text": "演示正文：",
  "offset": 0,
  "end_offset": 5,
  "total_chars": 13,
  "next_offset": 5
}
```

续读保持定位不变，offset填5，省略max_chars使用默认值；返回剩余“请核对完整条件。”，end_offset=13、next_offset=null。范围是[offset,end_offset)，右端不包含；块完整不代表文件完整，不自动读取相邻段落。offset等于总长返回空正文、null续读位置；超过总长报错。缺少来源、未ready、版本过期、块不存在明确报错，不当成空结果。ready表示解析状态，不保证事实准确。

## 文件职责与依赖

| 文件 | 职责 |
| --- | --- |
| models/materials/read_material_contract.py | Pydantic输入、模型参数说明，以及TypedDict公开输出 |
| models/materials/material_query_results.py | MaterialReadResult内部结果 |
| domain/materials/material_validator.py | 公共目录及正文关联校验，检索和读取共同引用 |
| domain/materials/material_reader.py | 精确定位、版本检查、块内字符切片与续读位置 |
| tools/materials/read_material_tool.py | 绑定快照、LangChain入口、错误适配及公开字段选择 |
| tests/test_read_material.py | 两项可打印测试及内存样本 |

宿主用`create_read_material_tool(project_id=..., materials=..., fragments=...)`创建工具；目录和正文复制成不可变快照，更新后重建。工具无文件或网络连接需要释放。输入经Pydantic校验；业务入口也检查独立调用参数；ValueError在工具执行时转换为ToolException。输出TypedDict仅描述字典形状，不自动校验。

公共正文校验从检索模块移到material_validator.py，并由validate_material_search_data改名为validate_material_content_data；项目内引用已更新。读取和检索互不导入对方，业务模块不依赖LangChain、Pydantic、FastAPI或配置。真实解析模块未来负责提供MaterialFragment，工具不自行扫描硬盘。
