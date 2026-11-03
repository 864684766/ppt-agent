# 第二个工具：search_materials

状态：已完成（独立Python/LangChain工具及约定的两项测试）。未接真实上传、解析/OCR、网页抓取、内存登记仓库、HTTP或聊天工具调用循环。示例正文是手写演示句子，不是法律依据。

## 运行：只看JSON定义和返回结果

```powershell
uv run --locked python -m pytest tests/test_search_materials.py -s -q
```

测试只保留两项：

1. `test_tool_calling_json`：打印转换给模型的function-tool JSON，确认能解析、工具名称和五个参数说明存在。
2. `test_tool_return_result`：打印调用参数和实际返回值，对比明确的样本答案。

`-s`显示成功测试的print输出。只运行结果测试：

```powershell
uv run --locked python -m pytest tests/test_search_materials.py::test_tool_return_result -s -q
```

2026-11-02已验证：新工具2项通过；与第一个工具一起运行共4项通过。未扩大到其他边界测试，也未调用真实模型或网络。

## 输入和输出去哪找

| 文件 | 职责 |
| --- | --- |
| `models/materials/material_fragment.py` | 已解析的正文块，保留项目、来源、版本、块ID和原页码 |
| `models/materials/search_materials_contract.py` | 集中定义输入与公开输出：Input含Field说明和Pydantic校验；Output及条目为TypedDict，不自动运行校验 |
| `models/materials/material_query_results.py` | 业务内部命中及结果，保留原正文块 |
| `validators/materials/material_fragment_validator.py` | 正文块的非空与页码检查 |
| `domain/materials/material_search.py` | 数据关联检查、关键词匹配与片段截取 |
| `tools/materials/search_materials_tool.py` | 项目/快照绑定、@tool入口及公开结果组装 |
| `tests/test_search_materials.py` | 两项可打印测试与样本 |

总体导航见 [模型索引](../models/README.md)。依赖方向是工具 → 纯业务检索 → 数据及纯校验；内部检索不依赖LangChain、FastAPI、Pydantic、Office或真实文件。

## 模型调用参数

| 参数 | 默认值 | 含义 |
| --- | --- | --- |
| `queries` | 必填 | 1–8个关键词，各1–200字符；任意词命中即可，不是所有词必须出现 |
| `source_ids` | `null` | 限定来源ID，1–100项；省略时查询当前项目全部ready资料，不允许空列表 |
| `origin` | `all` | all / uploaded / web；与来源ID共同过滤 |
| `max_results` | 10 | 最多返回1–50个命中正文块，不是词出现次数 |
| `max_chars_per_match` | 300 | 每块返回最多50–1000个Python字符，不是字节/token |

模型不传project_id或全文，宿主通过 `create_search_materials_tool(project_id=..., materials=..., fragments=...)` 绑定它们。目录和正文复制为快照，更新后需要重建工具。

测试中的调用：

```json
{
  "queries": ["经济补偿", "解除劳动合同"],
  "max_results": 10
}
```

测试返回两条命中：一条来自上传PDF的第12页，一条来自网页、页码为null。输出示意：

```json
{
  "matches": [
    {
      "source_id": "s01",
      "version": "v1",
      "location": {"block_id": "block_31", "page": 12},
      "matched_queries": ["经济补偿", "解除劳动合同"],
      "text": "演示资料：讨论解除劳动合同与经济补偿的处理流程。",
      "text_truncated": false
    },
    {
      "source_id": "s02",
      "version": "v1",
      "location": {"block_id": "paragraph_02", "page": null},
      "matched_queries": ["经济补偿"],
      "text": "演示网页：经济补偿的适用条件需要核对原文。",
      "text_truncated": false
    }
  ],
  "total_matches": 2,
  "truncated": false
}
```

total_matches=2是命中块数；第一块命中两个词，也只计一块。

## 首版检索行为

- 字面子串检索，忽略大小写；正则符号会转义，模型不能传正则表达式。使用标准库re；没有引入ripgrep或向量库。
- 不自动扩展同义词。需要“辞退、解除、终止”时，调用方明确传多个词；概念是否等价由Agent核实。
- 一个块只返回一次，matched_queries列出完整原块命中的输入词。
- 按来源ID、页码、块ID排序；未知页码排在已知页码之后，不做相关性排名。
- 长块围绕最早命中截取窗口；text_truncated表示该块未完整返回。其他命中词可能在窗口外，matched_queries仍描述完整块。
- total_matches是全部命中块数；truncated仅表示max_results限制丢弃了后续块。首版没有offset分页，可收窄来源/关键词或在上限内调大max_results。
- source_id、version、block_id共同定位原块；page只记录真实原页码，不能用块序号猜页码。`read_material`尚未实现。
- 未登记的来源、显式指定未ready来源、选中ready来源的正文未载入，明确报错；不当作空命中。若没有任何选中ready资料或关键词没有匹配，则返回空matches。
- 组装时检查正文关联当前项目的ready资料、版本一致、同来源版本块ID唯一。宿主数据错误抛ValueError；模型参数错误由Pydantic抛ValidationError，执行期业务错误适配为ToolException。当前没有HTTP/SSE错误映射。

## 真实资料如何接入

后续上传登记模块提供MaterialSummary；解析/OCR模块创建MaterialFragment并保留原页码/块ID。一个来源可对应多个块，版本应与目录一致。只有ready来源的正文进入该版本的检索快照。

这次只定义正文契约并接收调用方样本，没有创建全局Store或磁盘正文缓存。真实数据进入内存目录/正文集合的登记功能仍待后续任务，不会把测试样本当作正式数据。

PyCharm可在 `search_materials_tool.py` 的业务函数调用、`material_search.py` 的 `for block in blocks` 和 `matches.append(...)` 处设断点；使用项目.venv解释器，测试附加参数填写 `-s`。

## 公共目录校验的职责（2026-11-02）

`../domain/materials/material_validator.py`中的`validate_material_catalog`只校验项目编号和当前项目内的来源编号唯一性，通过时返回`None`，失败抛出`ValueError`。目录查询和正文关联校验直接复用它，不再通过查询、排序和分页来间接触发校验。目录查询和正文检索各自依赖这一共享模块，彼此不导入对方的操作模块。它是内部业务函数，不是Agent工具。单份实体字段校验仍在实体构造时执行。目录公共校验现在先于查询参数校验；多项输入同时无效时，可能优先报告目录错误。
