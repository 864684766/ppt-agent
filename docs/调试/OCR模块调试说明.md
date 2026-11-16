# 公共图片OCR模块

2026-11-06。公共模块负责单张图片本地文字识别；现已由PDF读取器组合并接入chat无文字页回退，不新增Agent工具或LangGraph。
OCR在这里表示“从图片像素识别文字”，不是视觉大模型分析版式，也不负责生成PPT。

## 模块边界与目录

```text
外层调用方（准备图片字节、决定模型目录、关联来源/页码）
    ↓ ImageTextRecognizer.recognize(image_bytes=...)
integrations/ocr/rapidocr_text_recognizer.py
    ├─ ocr_image_decoder.py：检查图片、方向校正、透明背景合成白色
    └─ RapidOCR + ONNX Runtime：本地CPU文字检测/方向判断/识别
    ↓ OcrResult
外层调用方（显示结果或组装文档正文）
```

- models/ocr/ocr_result.py：OcrResult和OcrTextRegion，标准库不可变dataclass，不依赖SDK。
- domain/ocr/image_text_recognizer_contract.py：ImageTextRecognizer协议和OcrError；不依赖Settings或HTTP。
- integrations/ocr/：本地引擎适配与图片解码，统一复用系统诊断日志。
- tests/test_image_ocr.py：仅保留读取一张真实图片、调用一次OCR、打印文字的断点入口。

OCR只认识图片，不知道PDF页码、来源ID或文件名。这些关联由PDF、Word、PPT或图片调用方负责。
今后更换OCR引擎只需实现相同协议；不要求所有文档使用同一种提取图片的方法。
目前没有新增Agent工具，没有tool-calling JSON，没有新的上传接口或环境变量。
PDF无文字页已接入公共OCR；普通图片上传尚未成为chat支持格式。

## 版本、选择依据与依赖

2026-11-06查询官方PyPI发布元数据：

| 组件 | 最新稳定及本次锁定版本 | 最高可用预发布 | 说明 |
| --- | --- | --- | --- |
| rapidocr | 3.10.0 | 发布记录中未发现有文件的预发布 | Python >=3.8,<4；通用Python wheel；Apache-2.0 |
| onnxruntime | 1.31.1 | 发布记录中未发现有文件的预发布 | Python >=3.11；提供cp313-win_amd64 wheel；MIT |

同日查看PaddleOCR最新稳定为3.7.0，但它另需推理框架及更大的依赖组合。本轮先采用RapidOCR的ONNX CPU路线，原因是当前目标仅为可复用的图片文字识别，且已在Windows Python3.13.9实装运行；没有做两种引擎的识别质量或速度对比，不宣称其中一种更准确。

pyproject.toml声明、uv.lock和实际安装已同步，uv sync --locked、uv lock --check通过。沿用现有Pillow13.0.0。
关联实装包括numpy2.5.4、opencv-python-headless5.0.0.93、shapely2.2.0、omegaconf2.4.0、pyclipper1.4.0、flatbuffers25.12.19、protobuf7.36.2；完整传递依赖以uv.lock为准。
新增OCR没有改动LangChain、MCP或Harness约束；依赖解析通过不等于已完成它们与OCR的工作流集成。
Linux/Docker本轮未运行验证，不承诺部署后的字体、性能和识别结果完全一致。OCR本身不要求安装Office或LibreOffice。

官方依据：[RapidOCR PyPI](https://pypi.org/pypi/rapidocr/json)、[RapidOCR文档](https://rapidai.github.io/RapidOCRDocs)、[ONNX Runtime PyPI](https://pypi.org/pypi/onnxruntime/json)、[PaddleOCR PyPI](https://pypi.org/pypi/paddleocr/json)。
本轮另外核对了已安装3.10.0发行包内的config.yaml、default_models.yaml、下载器和RapidOCROutput源码；GitHub原始文件请求失败，未将无法访问的在线源码作为已读证据。

## 模型文件：准备阶段联网，识别阶段本地运行

OCR权重与Python包是两回事。当前本机ocr-models/已备好并通过官方下载器的SHA-256检查：

| 文件 | 职责 | 字节数 |
| --- | --- | --- |
| PP-OCRv6_det_small.onnx | 找到文字位置 | 9929594 |
| ch_ppocr_mobile_v2.0_cls_mobile.onnx | 判断文字方向 | 585532 |
| PP-OCRv6_rec_small.onnx | 将文字图片识别为字符 | 21234383 |

约30.3MiB，不包含推理时内存。它们是本地OCR模型，不是GLM等大语言模型，不需要API key。
ocr-models/是项目根目录下长期保留的运行资源，不按data/测试数据目录清理。移动到根目录不自动代表权重已提交Git；换机器或构建Docker时必须确认模型文件已随部署提供。
运行时显式使用本地文件，缺失报OcrError，不在用户识别请求中自动下载。不要随意替换成不兼容的同名ONNX文件。

若以后需要重新准备，可在项目根目录用以下PowerShell命令，借助发行包自带配置和官方模型下载器：

```powershell
@'
from pathlib import Path
import rapidocr
import yaml
from rapidocr.utils.download_models import download_models

model_directory = Path("ocr-models").resolve()
model_directory.mkdir(parents=True, exist_ok=True)
# 复制所锁定版本的完整默认配置，只改变模型保存位置。
config = yaml.safe_load((Path(rapidocr.__file__).parent / "config.yaml").read_text(encoding="utf-8"))
config["Global"]["model_root_dir"] = str(model_directory)
config_path = model_directory / "download-config.yaml"
config_path.write_text(yaml.safe_dump(config, allow_unicode=True), encoding="utf-8")
download_models(config_path)
'@ | uv run --locked --no-sync python -
```

模型下载地址和校验值来自该版本default_models.yaml。首次下载需要能访问其官方模型托管地址；网络受限可在能联网的机器准备后复制这三个文件。
该命令属于人工环境准备，不是业务接口；官方下载器有自己的控制台日志，不等同于系统应用日志。
代码包许可与模型权重许可应分别按上游发行说明核对；本轮未开展对外再分发许可审核。

## 你如何在PyCharm测试

打开tests/test_image_ocr.py，只需修改顶部的IMAGE_PATH：

```python
from pathlib import Path
IMAGE_PATH = Path("E:/我的资料/截图.png")
```

默认IMAGE_PATH指向data/vision-demo/template-thumbnail.png，这是现有图片，不再从PPT的docProps/thumbnail提取预览。
MODEL_DIRECTORY在测试入口指定本地模型目录，正式模块不硬编码项目根目录，也不读取.env。
点击test_recognize_real_image左侧图标选择Debug，在result = recognizer.recognize(...)这一行打断点。
控制台只打印图片路径和识别文字；区域坐标可在断点查看result.regions。正式日志只写数量/尺寸，不写正文。

```powershell
uv run --locked --no-sync python -m pytest tests/test_image_ocr.py -s -q
```

也可以只调试真实图片入口：

```powershell
uv run --locked --no-sync python -m pytest tests/test_image_ocr.py::test_recognize_real_image -s -q
```

## 输入、返回值与资源说明

recognize(image_bytes=bytes)只接收完整图片文件字节，不接收URL、路径、PDF或base64。
默认支持PNG、JPEG、WEBP、BMP和单页TIFF；多帧、多页图片明确拒绝，不能悄悄只识别第一页。
默认20MiB文件字节、2500万像素，先检查尺寸再解码；Pillow自身防解压炸弹规则也生效。

构造参数由外层注入，不是环境变量：model_directory为模型目录，max_image_bytes为图片压缩字节上限，max_image_pixels为宽×高上限，cpu_threads默认2且这些数值须为正整数。
默认识别分过滤阈值0.5，低于阈值的区域可能被引擎滤掉；空结果不证明原图绝无文字。

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| OcrResult.width_px / height_px | int | EXIF方向校正后图片宽、高，单位像素 |
| OcrResult.regions | tuple[OcrTextRegion,...] | 引擎顺序的区域，未检出文字为空元组 |
| OcrResult.text | str属性 | 各区域text以换行拼接；空结果为空字符串，不重复存储 |
| OcrTextRegion.text | str | 引擎识别文字，不让大模型补写 |
| OcrTextRegion.polygon_px | 四个(x,y)浮点数点的tuple | 以校正后原图左上角为原点的像素坐标；保留倾斜四边形，不是EMU/PDF坐标，也不承诺每个点都落在画布内 |
| OcrTextRegion.confidence | float，0~1 | 引擎识别置信分，不是事实正确率 |

调用方持有输入字节；适配器关闭自己创建的图片，不归档文件。引擎在实例内复用且加锁串行执行，避免并发修改SDK状态；不是整个系统的并发配额。
这是同步CPU工作，未来异步HTTP接入时由外层移入工作线程，取消等待不保证立即停止原生识别。
SDK会在首次推理时延迟创建ONNX会话，首张图通常包括加载时间，不等于每张图固定耗时。

## 日志与当前验证

系统日志仍由config/logging_config.py和pytest入口统一初始化，遵守LOG_LEVEL、LOG_OUTPUT。
ocr.recognize_image记录开始/完成/安全失败位置及耗时；ocr.load_engine为嵌套模型构造操作。首次推理的真实会话加载耗时仍包含在识别操作内。
ocr_result只记录尺寸、区域数、字符数，无文字记录WARNING。正常日志不写文字、图片字节、完整对象或SDK原始异常。
RapidOCR有独立logger，适配器将其原文日志压到CRITICAL，本项目不接管它或原生运行时的输出。

历史验证（测试简化前）3 passed（7.26秒）：现有1743×981图片返回4个区域；合成OCR TEST 12345图片识别成功；空白图返回空结果；损坏图片明确失败且日志包含安全位置，不含输入原文。
合成/空白图测试阻止Python socket连接，真实引擎识别，没有伪造返回值。该检查不等同操作系统级网络隔离。
使用者需人工核对中文、错字、漏字、倾斜文字等效果；不保证复杂分栏顺序、手写、公式及表格结构还原。
此处初次验证时尚无PDF回退；当前已接入，详见[PDF文字与OCR调试说明](PDF文字与OCR调试说明.md)。无新增Agent工具。

历史验证（测试简化前）：3 passed（7.82秒），包括在阻止Python socket连接后创建新的识别器并首次推理；已有日志配置/诊断、模板结构及PDF渲染回归14 passed（2.23秒）。应用、LangChain、MCP、Harness导入通过，uv lock --check及git diff --check通过。没有发送大语言模型请求；用户人工效果验收仍待进行。

2026-11-06按用户要求简化：当前只保留test_recognize_real_image，一个图片、一次识别、打印文字；移除fixture、合成图片、socket替换、空白与错误断言及区域JSON打印。上述3项结果仅为历史记录，不作为当前测试范围。是否用视觉模型替代本地OCR仍在讨论，当前未移除OCR或修改视觉模块。

简化后实跑：1 passed（3.06秒），控制台仅打印图片路径及识别文字；git diff --check通过。测试通过表示调用完成，文字准确性仍由用户对照原图核对。

2026-11-06用户将模型移动至项目根目录ocr-models/，测试入口已使用PROJECT_ROOT / "ocr-models"；此目录为长期运行资源，不作为可清理的data/。识别器仍接收外层传入路径，无需修改公共模块。目录内旧download-config.yaml可能仍保存迁移前绝对路径；重新下载时请运行上方命令生成新配置，不直接复用旧配置。

2026-11-06后续接线完成：PDF无文字页由现有chat文件读取流程自动调用本模块，保留真实页码与正文上限。有文字层页面不调用OCR；同页内嵌图片识别尚未实现。详见[PDF调试说明](PDF文字与OCR调试说明.md)。
