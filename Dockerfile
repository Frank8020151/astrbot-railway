FROM soulter/astrbot:latest

# 安装代理依赖
RUN pip install websockets aiohttp

# 复制所有文件
COPY sleep_proxy.py /app/sleep_proxy.py
COPY web_proxy.py /app/web_proxy.py
COPY astrbot_config.json /app/astrbot_config.json
COPY start.sh /app/start.sh
RUN chmod +x /app/start.sh

# 暴露三个端口（Railway 会自动映射 PORT）
EXPOSE 6185 6199 8080

CMD ["bash", "/app/start.sh"]
