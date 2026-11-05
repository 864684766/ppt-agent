# 外部接入模块导航

`integrations/`存放连接外部SDK、网络服务和本地文件格式的具体实现。
按接入能力分类，不按“用了哪个框架”分类；例如使用LangChain的模板视觉分析仍放在templates。

| 目录 | 职责 | 当前文件 |
| --- | --- | --- |
| llm/ | 共用模型构造及聊天SDK适配 | langchain_model_factory.py、langchain_chat_client.py |
| web/ | 搜索引擎、HTTP网页读取和HTML提取 | searxng_search_client.py、webpage_http_client.py、http_webpage_reader.py、html_text_extractor.py |
| skills/ | 本地技能介绍扫描、头部解析和完整读取 | local_skill_catalog.py、local_skill_reader.py、skill_header_reader.py、skill_metadata_parser.py |
| templates/ | PPTX结构解析和页面视觉模型适配 | local_template_inspector.py、pptx_shape_extractor.py、langchain_template_vision.py、gotenberg_converter.py、pdfium_page_renderer.py |

## 如何选择位置

- 需要创建LangChain模型，使用`integrations.llm.langchain_model_factory.create_langchain_model`；不要在其他目录重复写ChatOpenAI构造。
- 操作模板文件或分析PPT页面图片，查看templates；模型名称、连接参数由外层决定。
- 连接搜索服务或读取网页，查看web；资料如何筛选和形成大纲不放在这里。
- 扫描或读取SKILL.md，查看skills；不在技能发现时分析依赖或运行脚本。

domain定义业务协议，models定义数据结构，tools封装模型可选工具，api处理HTTP。
这些职责不因为增加子文件夹而移动进integrations。当前没有MCP/Harness适配实现，
不提前建空目录；等实际接入时再按职责增加。

## 导入和资源归属

直接从具体模块导入，例如：

```python
from integrations.llm.langchain_model_factory import create_langchain_model
from integrations.templates.langchain_template_vision import LangChainTemplateVisionAnalyzer
```

各级`__init__.py`仅说明包职责，不批量导出类或初始化模型，不保留旧路径的转发文件。
调用方仍负责配置组装及HTTP资源关闭；业务协议和数据模型不反向依赖此目录。
包移动后`logging.getLogger(__name__)`的日志来源会包含新的子包路径，日志输出配置不变。

2026-11-05：仅调整模块位置、导入、代码注释中的路径及关联文档；无依赖、配置、公开字段或业务行为变化。

GotenbergPdfConverter为PPTX转PDF具体适配器，返回PDF字节；协议位于domain/templates/presentation_pdf_converter_contract.py。真实配置、磁盘读写和HTTP资源生命周期在外层组装。详见[转换调试说明](../docs/Gotenberg转换调试说明.md)。

PdfiumPageRenderer是本地同步PDF页面渲染器，输出PNG字节及PDF页码。它不启动Gotenberg、不调用模型；PDFium通过模块锁串行访问，调用方负责异步线程桥接和文件读写。详见[PDF页面图片调试说明](../docs/PDF页面图片调试说明.md)。

## 诊断日志（2026-11-05）

各外部操作通过diagnostics/operation_logging.py记录生命周期、耗时及安全异常位置；摘要只记录数量/状态，不记录用户正文或原始SDK异常。PDF逐页细节为DEBUG。日志初始化仍在应用/pytest/脚本入口，适配器不读取日志配置。详见[日志说明](../docs/日志使用说明.md)。
