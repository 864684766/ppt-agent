# 外部接入模块导航

`integrations/`存放连接外部SDK、网络服务和本地文件格式的具体实现。
按接入能力分类，不按“用了哪个框架”分类；例如使用LangChain的模板视觉分析仍放在templates。

| 目录 | 职责 | 当前文件 |
| --- | --- | --- |
| llm/ | 共用模型构造及聊天SDK适配 | langchain_model_factory.py、langchain_chat_client.py |
| web/ | 搜索引擎、HTTP网页读取和HTML提取 | searxng_search_client.py、webpage_http_client.py、http_webpage_reader.py、html_text_extractor.py |
| skills/ | 本地技能介绍扫描、头部解析和完整读取 | local_skill_catalog.py、local_skill_reader.py、skill_header_reader.py、skill_metadata_parser.py |
| storage/ | RustFS/S3只读模板目录及字节下载 | s3_template_catalog.py、s3_template_file_reader.py |
| documents/ | 各格式内存正文读取及PDFium共享锁 | text/pdf/docx/xlsx/pptx_document_reader.py、document_reader_registry.py、pdfium_runtime.py |
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

## 文档正文读取（2026-11-05）

各读取器实现domain/documents/document_reader_contract.py的DocumentReader协议：read(content=bytes, limits=DocumentReadLimits)返回DocumentContent。
注册表只构造无状态读取器，不读配置或文件。API外层选择格式、验证内容并用线程调用；读取器关闭自己创建的文档、工作簿和原生句柄。
PDF正文与模板PDF图片渲染共享documents/pdfium_runtime.py的PDFIUM_LOCK，避免同进程并发使用PDFium。
DOCX使用python-docx1.2.0；XLSX使用openpyxl3.1.5；PPTX/python-pptx、PDF/PDFium沿用锁定版本。
不执行宏、公式、OCR、模型调用或模板角色判断；具体能力边界见[对话附件读取说明](../docs/对话附件读取调试说明.md)。

## RustFS/S3模板目录（2026-11-06）

S3TemplateCatalog接收外层创建的SDK client及固定bucket，实现TemplateResourceCatalog协议；不读取Settings、不创建连接、不依赖HTTP。
ListObjectsV2单页后按.pptx过滤，保留分页与完整object_key，不下载/上传/删除，不构造公共URL。API组装层负责closing(client)；同步操作在工作线程执行。
boto3==1.43.125及关联约束已锁定实装。凭据仅本机.env配置，SDK DEBUG抑制。真实匿名访问ppts返回403，带凭据成功列表仍待验证；见[调试说明](../docs/模板资源列表调试说明.md)。

## OSS模板字节读取（2026-11-06）

S3TemplateFileReader实现TemplateFileReader协议，接收宿主client/bucket及object_key/max_bytes，返回真实bytes。
对get_object.Body使用closing；ContentLength预检查与流式实际下载上限同时执行，失败/超限也关闭流。SDK客户端仍由api/template_resource_dependencies.py的open_template_storage_client管理，目录与下载复用连接组装。
不解析文件或返回HTTP，不写磁盘/Store；API模板处理取得字节后复用已有PPTX校验和读取器。未增加外部依赖。
独立模块测试tests/test_s3_template_file_reader.py（SDK Stubber，非HTTP测试）覆盖读取、关闭、实际超限和不存在；真实chat已从OSS读取公司/暑期两份模板。
