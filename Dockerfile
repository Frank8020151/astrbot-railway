FROM soulter/astrbot:latest

# 安装依赖
RUN pip install websockets aiohttp

# 复制代理脚本和配置文件
COPY sleep_proxy.py /app/sleep_proxy.py
COPY astrbot_config.json /app/astrbot_config.json

EXPOSE 6185 6199 8080

# 🔥 启动脚本：先启动 AstrBot，再启动代理
CMD ["sh", "-c", "python3 -m astrbot & sleep 3 && python3 /app/sleep_proxy.py"]
