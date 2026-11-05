"""网页HTTP连接的TLS策略与重定向配置，不依赖环境变量读取。"""

import httpx


def create_webpage_http_client(*, verify_tls: bool = True) -> httpx.AsyncClient:
    """创建由调用方async with关闭的连接池。

    verify_tls=True使用正常HTTPS证书校验；False为兼容模式，跳过所有目标
    网站的证书身份校验，不保证连接对端身份。不维护特定网站名单。
    只影响使用此连接的请求；不能解决登录、验证码、JS渲染或服务器拒绝访问。
    """
    return httpx.AsyncClient(verify=verify_tls, max_redirects=5)
