# PDF指定页转PNG（2026-11-05）

已实现独立同步渲染模块，输入PDF原始字节，输出指定页的PNG字节、页码和图片尺寸。
没有新增Agent工具或HTTP接口，不连接Gotenberg、不调用视觉模型、不自动关联PPT页码。
本机不需要安装LibreOffice或Poppler；PDFium随pypdfium2对应平台的安装包提供。

## PyCharm测试

打开tests/test_pdf_page_renderer.py，在test_render_selected_pdf_pages左侧点击Debug。
附加参数-s可显示打印，工作目录是项目根目录。测试没有独立命令行主入口。

```powershell
uv run --locked --no-sync python -m pytest tests/test_pdf_page_renderer.py -s -q
```

测试顶部有三项可修改：

```python
PDF_PATH: Path | None = None
PAGE_NUMBERS: list[int] | None = [1, 3]
RENDER_DPI = 144
```

PDF_PATH=None时选data/gotenberg-test中最近修改的PDF，测试会打印实际选择的绝对路径。
也可改为Path("E:/具体文件.pdf")。PAGE_NUMBERS=None时处理全部页，[3, 1]按3、1顺序返回；
页码从1开始，不允许空序列、重复值、布尔值或越界值。RENDER_DPI是每英寸像素数，不是图片宽度。

在`result = renderer.render(...)`处打断点。result.total_pages是原PDF全部页数，
result.images是本次选中页的元组；展开每项查看page_number、width_px、height_px和png_bytes。
不要将png_bytes完整打印。测试把图片保存到data/pdf-page-test/日期时间-随机后缀/page-001.png等路径，
不覆盖原PDF，不覆盖上一次结果，不自动清理历史目录。

当前仅保留正常渲染测试，检查PNG能重新解码、尺寸和请求顺序一致、源文件hash不变；用户已删除越界及不可读PDF两项测试。渲染失败的诊断日志由正式模块提供。
这是真实本地PDF验证，不使用模型替身；通过不代表画面与原PPT完全一致，请打开图片对照PDF对应页。

## 模块职责与调用方式

| 文件 | 职责 |
| --- | --- |
| models/templates/pdf_page_image.py | PdfPageImage和PdfRenderResult不可变dataclass；逐字段中文说明 |
| domain/templates/pdf_page_renderer_contract.py | PdfPageRenderer协议与PdfRenderError，不依赖渲染库 |
| integrations/templates/pdfium_page_renderer.py | PDFium页面绘制、Pillow编码PNG、资源关闭 |
| tests/test_pdf_page_renderer.py | 选择真实PDF、指定页码、保存输出及打印结果 |

```python
renderer = PdfiumPageRenderer()
result = renderer.render(pdf_bytes=pdf_bytes, pages=[1, 3], dpi=144)
for page_image in result.images:
    # 后续可由调用方保存page_image.png_bytes，或作为image/png传给视觉模块。
    print(page_image.page_number, page_image.width_px, page_image.height_px)
```

这只是调用说明，尚未接视觉模块。dataclass不依赖SDK；图片结果由渲染器创建，外层负责保存和来源关联。
同一个PDF内用pdf_sha256与page_number定位，文件指纹不表示历史版本管理。

## 参数、尺寸和资源

- PDF页面物理尺寸采用point，72 point=1英寸；scale=dpi/72。像素尺寸由渲染库取整，宽屏页面可能得到1921而非1920像素，不应硬编码预期宽度。
- dpi默认144，允许整数36–300。max_page_pixels在构造时默认20000000，单位为每页像素总数，超限明确报错，不自动降DPI。两者是显式Python参数，不新增环境变量。
- PDFium非线程安全，模块用进程内共享锁保护所有实例操作。不要在其他代码绕开此模块直接并发调用PDFium。当前没有多进程池。
- render为同步CPU操作，后续异步入口可用asyncio.to_thread；取消等待不保证立即中止底层渲染。
- 每页使用ExitStack按顺序关闭Pillow图片、PDFium位图和页面，文档上下文最终关闭PDF。不在模块中读取配置或磁盘、启动进程、发送网络请求。
- PDF与全部选中PNG均保存在内存，长文档建议分批选择页码。单页像素上限不等于整个任务的内存上限。当前不支持密码参数，也不实现OCR、缓存或背景任务。

## 版本、许可和平台核对

2026-11-05从官方PyPI发布数据查询，并更新pyproject.toml与uv.lock，使用uv sync --locked --inexact同步。
--inexact保留本机已有但不在项目声明中的包，避免无关清理；不改变锁定版本。

| 包 | 查询时最新稳定版/本次锁定安装 | 查询到的最高版本号预发布（本次未使用） | 许可/运行要求 |
| --- | --- | --- | --- |
| pypdfium2 | 5.14.0 | 5.14.0b1 | 项目声明BSD-3-Clause、Apache-2.0及依赖许可；Python>=3.6 |
| Pillow | 13.0.0 | 5.4.0.dev0（历史开发版本，不是当前推荐版） | MIT-CMU；Python>=3.11 |

官方发布源：[pypdfium2](https://pypi.org/pypi/pypdfium2/json)、[Pillow](https://pypi.org/pypi/Pillow/json)。
文档与许可：[pypdfium2项目](https://github.com/pypdfium2-team/pypdfium2)、[Pillow项目](https://github.com/python-pillow/Pillow)。
两者有Windows和常见Linux平台安装包；本次实际安装与渲染仅在Windows验证，Linux/Docker未执行。
分发时需保留PDFium和所含第三方依赖的许可声明。版本约束未要求修改MCP/Harness，二者没有新增接线。

## 本次实际结果

当前测试范围为1项正常渲染验证；原3项记录中的两项错误测试已由用户删除。样本data/gotenberg-test/20261105-144811-e3f454be/绿色几何创意演示PPT模板.pdf有15页。
第1、3页在144 DPI下均生成1921×1080像素PNG，分别1996153和1711010字节。
输出目录data/pdf-page-test/20261105-151159-862fed72/，已打开两张图片检查，中文标题和背景可见。
未核对原PPT逐对象视觉一致性，也未调用模型或检查隐藏幻灯片导出策略。
