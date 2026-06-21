#!/usr/bin/env python3
"""
AstrBot Web UI 反向代理
- 监听 $PORT（Railway 分配的端口）
- GET / → 健康检查 OK
- 其他请求 → 转发到 AstrBot Web UI (127.0.0.1:6185)
"""

import asyncio
from aiohttp import web
import aiohttp
import os
import logging

PORT = int(os.getenv("PORT", "8080"))
ASTRBOT_HOST = "127.0.0.1"
ASTRBOT_WEB_PORT = 6185

logger = logging.getLogger("web_proxy")
logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s %(message)s", datefmt="%H:%M:%S")


async def proxy_handler(request):
    """反向代理到 AstrBot Web UI"""
    # 健康检查
    if request.method == "GET" and request.path == "/":
        return web.Response(text="OK")
    
    # 构建目标 URL
    target_url = f"http://{ASTRBOT_HOST}:{ASTRBOT_WEB_PORT}{request.path}"
    if request.query_string:
        target_url += "?" + request.query_string
    
    try:
        async with aiohttp.ClientSession() as session:
            body = await request.read()
            
            async with session.request(
                method=request.method,
                url=target_url,
                headers=dict(request.headers),
                data=body,
                timeout=aiohttp.ClientTimeout(total=30),
                allow_redirects=False
            ) as resp:
                resp_body = await resp.read()
                
                response = web.Response(
                    body=resp_body,
                    status=resp.status
                )
                
                # 复制响应头（过滤掉 aiohttp 自动处理的）
                skip_headers = {'content-encoding', 'content-length', 'transfer-encoding'}
                for key, value in resp.headers.items():
                    if key.lower() not in skip_headers:
                        response.headers[key] = value
                
                return response
    except Exception as e:
        logger.error(f"代理错误: {e}")
        return web.Response(
            text=f'<html><body><h1>AstrBot 暂时不可用</h1><p>{e}</p></body></html>',
            status=502,
            content_type='text/html'
        )


async def main():
    app = web.Application()
    app.router.add_route('*', '/{path:.*}', proxy_handler)
    
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', PORT)
    await site.start()
    
    logger.info(f"🌐 Web UI 代理运行中：:{PORT} → AstrBot :{ASTRBOT_WEB_PORT}")
    
    # 保持运行
    await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())
