# PDF文字读取与OCR回退

2026-11-06：已接入现有POST /ppt-agent/v1/chat，无新增接口、环境变量或依赖。
本轮只处理PDF整页没有原生文字的情况，不识别Word/PPT内嵌图片，也不开放普通图片上传。

## 运行流程

1. API校验附件，按格式选择PdfDocumentReader，注入公共OCR与页面渲染器。
2. PDFium提取每页原生文字并关闭原生句柄，保留页顺序；提前检查页数与文字上限。
3. 有非空文字的页面直接使用原生结果，不加载OCR模型。
4. 无文字页按144DPI逐页渲染为PNG，交给根目录ocr-models/中的本地模型识别。
5. 通过DocumentContentBuilder统一检查正文字符与单元数量上限，返回每个非空页一个块。

文字读取与渲染共用PDFIUM_LOCK，必须先释放原生提取锁再调用渲染，避免重复获取普通Lock造成死锁。OCR计算不持有PDFium锁。当前复用渲染器的公开render接口，每页会重新打开PDF，未做性能对比；一次只持有一页图片，不把所有扫描页图片同时放进内存。

PDF识别器由API每次请求创建，各页复用同一实例；没有全局模型缓存、数据库或文件归档。首次无文字页包括模型加载时间，长扫描PDF会明显比原生提取慢。线程取消等待不会立即中止底层渲染或OCR。单页绘制默认2000万像素，OCR默认20MiB/2500万像素，DOCUMENT_MAX_*继续有效；超限不静默降分辨率或截断。

## Postman测试

先重启服务，向POST http://127.0.0.1:<APP_PORT>/ppt-agent/v1/chat发送请求，主机及端口以本机实际启动配置为准。
Body选择form-data，不手填Content-Type，让Postman生成multipart边界：

| 字段 | 类型 | 内容 |
| --- | --- | --- |
| message | Text | 请读取这份PDF |
| file | File | 一份扫描PDF（先用1至2页的小文件） |

template_key可以不传。保持现有参数和JSON响应，不调用云端大语言模型，不返回SSE。
预期200、status=attachment_read、model_called=false、retained=false；attachment.content中：

- blocks[].text包含OCR识别文字，kind为page，page为PDF真实页码，从1开始。
- page_count仍为原PDF总页数，不是识别成功页数。
- pages_without_text表示处理后仍无文字的页；空白页或未识别成功页可能出现其中。
- warnings提示本地OCR可能错漏、阅读顺序不准确，不能把识别结束当成准确性保证。

再上传一份有文字层的PDF：应该直接返回原生文字，日志ocr_pages=0，不加载OCR模型。
扫描与文字混排的PDF按页决定；同一页只要有文字层，就不会识别该页图片，可能漏掉页内图片文字。原生文字乱码但非空，也暂不自动触发OCR。

## 错误与断点

- 根目录ocr-models缺模型、OCR运行失败或页面渲染失败：503，detail.code=document_ocr_failed，提示具体PDF页码；整个请求失败，不交付半份内容。
- OCR正文使累计字符超限：413，document_limit_exceeded。
- PDF损坏/密码无法打开：400，document_unreadable。
- 原有上传格式/大小校验继续有效。

断点顺序：api/chat_attachment_processing.py的validate_and_read → PdfDocumentReader.read → renderer.render → recognizer.recognize → builder.add。
有文字的PDF不会走render/recognize断点，这是预期行为。
HTTP由用户通过Postman和PyCharm验收，不创建tests/test_chat_attachments.py或Postman文件。

## 模块边界、字段和日志

PdfDocumentReader只依赖ImageTextRecognizer与PdfPageRenderer协议，不构造引擎、不读取路径配置。create_document_readers可接收成对的recognizer/renderer；省略时仍可独立读取文字，遇到无文字页明确说明未配置OCR。
API只对PDF组装RapidOcrTextRecognizer(model_directory=PROJECT_ROOT / "ocr-models")和PdfiumPageRenderer。其他格式行为不变；root OCR目录是长期运行资源。

未新增响应字段。DocumentBlock.text现在可来自本地OCR；DocumentContent.pages_without_text的PDF含义变为OCR后仍无文字（启用OCR时）。model_called=false专指未调用对话/云端视觉大模型，并非未使用任何本地机器学习模型。

日志document.read_pdf → pdf.render / ocr.recognize_image → ocr.load_engine继承操作编号，INFO摘要含总页数、OCR处理页数及无文字页数；DEBUG含页码及字符数量，不写正文、图片或模型路径。失败沿用safe_error_location；OCR和渲染错误不伪装空白，纯正文限额错误仍为413。日志配置与请求编号规则不变。

## 实际验证

独立模块tests/test_pdf_ocr.py：3 passed（8.28秒）。真实生成两页无文字层PDF，第一页文字图片识别为PDF OCR TEST 12345，第二页空白；结果为总页数2、正文第1页、无文字页[2]。有原生文字的PDF验证不调用渲染/OCR；另外验证正文超限与OCR失败不返回部分成功。
真实识别使用本地CPU权重，无网络模型调用；分支单测使用替身隔离外部识别，不伪造真实识别测试结果。
另直接调用附件处理组装函数，真实扫描PDF返回pdf/2页/1块/无文字页(2,)。这是模块接线验证，不是用户Postman验收，也没有保存HTTP测试文件。

```powershell
uv run --locked --no-sync python -m pytest tests/test_pdf_ocr.py -s -q
```

用户可直接使用Postman验收接口，不必先阅读该模块验证文件。Linux/Docker、批量扫描、手写、复杂表格及人工准确性尚未验证。

回归：既有日志/诊断及PDF渲染12 passed（1.34秒）；FastAPI导入、git diff --check通过，无依赖升级。
