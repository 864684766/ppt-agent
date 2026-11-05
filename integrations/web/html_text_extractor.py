"""用标准库提取静态HTML可读文本，不引入浏览器或执行网页脚本。"""

from html.parser import HTMLParser


class HtmlTextExtractor(HTMLParser):
    """优先main/article区域，缺失时退回页面文本；是启发式提取而非文章识别模型。

    每次解析创建新实例；去除脚本、样式和常见导航区域。无法保证清除所有广告，
    也不能通过有少量文本就判断页面是否需要登录、验证码或JavaScript。
    """

    _SKIP = {"script", "style", "noscript", "nav", "footer", "aside", "svg", "iframe", "form"}
    _BLOCK = {"p", "div", "section", "article", "main", "li", "br", "hr", "h1", "h2", "h3", "h4", "tr"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        # 分别积累候选正文和全页文本，结束后按语义区域选择。
        self._all: list[str] = []
        self._main: list[str] = []
        self._article: list[str] = []
        self._title: list[str] = []
        self._main_depth = 0
        self._article_depth = 0
        self._in_title = False
        self._skip_tags: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in self._SKIP:
            self._skip_tags.append(tag)
        if self._skip_tags:
            return
        if tag == "title":
            self._in_title = True
        if tag == "main":
            self._main_depth += 1
        if tag == "article":
            self._article_depth += 1
        if tag in self._BLOCK:
            self._append("\n")

    def handle_endtag(self, tag: str) -> None:
        if self._skip_tags:
            if tag == self._skip_tags[-1]:
                self._skip_tags.pop()
            return
        if tag in self._BLOCK:
            self._append("\n")
        if tag == "main":
            self._main_depth = max(0, self._main_depth - 1)
        if tag == "article":
            self._article_depth = max(0, self._article_depth - 1)
        if tag == "title":
            self._in_title = False

    def handle_data(self, data: str) -> None:
        if self._skip_tags:
            return
        if self._in_title:
            self._title.append(data)
        else:
            self._append(data)

    def _append(self, text: str) -> None:
        """同步收集各区域，避免把HTML标签原样返回给调用方。"""
        self._all.append(text)
        if self._main_depth:
            self._main.append(text)
        if self._article_depth:
            self._article.append(text)

    def result(self) -> tuple[str, str]:
        """返回(title, text)；按行合并多余空白，保留段落边界。"""
        for fragments in (self._main, self._article, self._all):
            lines = (" ".join(line.split()) for line in "".join(fragments).splitlines())
            text = "\n".join(line for line in lines if line)
            if text:
                return " ".join("".join(self._title).split()), text
        return " ".join("".join(self._title).split()), ""
