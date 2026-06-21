FROM soulter/astrbot:latest

# 安装代理依赖
RUN pip install websockets aiohttp

# 复制文件
COPY sleep_proxy.py /app/sleep_proxy.py
COPY astrbot_config.json /app/astrbot_config.json
COPY start.sh /app/start.sh
RUN chmod +x /app/start.sh

EXPOSE 6185 6199 8080

# 使用 start.sh 启动（接管默认 CMD）
CMD ["bash", "/app/start.sh"]
