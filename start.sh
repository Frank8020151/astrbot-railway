#!/bin/bash
set -e

echo "🚀 AstrBot + 休眠代理 + Web UI 代理 启动中..."
echo "📡 Railway PORT = ${PORT}"

cd /app

# ========== 1️⃣ 找到正确的 AstrBot 入口 ==========
echo "⏳ 正在查找 AstrBot 入口..."

# 尝试多种路径（适配不同版本的镜像）
BOT_SCRIPT=""
for candidate in \
    "/app/astrbot/bot.py" \
    "/app/bot.py" \
    "/AstrBot/astrbot/bot.py" \
    "/AstrBot/bot.py" \
    $(find / -maxdepth 4 -name "bot.py" -path "*/astrbot*" 2>/dev/null | head -3); do
    
    if [ -f "$candidate" ]; then
        BOT_SCRIPT="$candidate"
        echo "✅ 找到入口: $BOT_SCRIPT"
        break
    fi
done

if [ -z "$BOT_SCRIPT" ]; then
    echo "❌ 未找到 AstrBot 入口！检查目录结构..."
    echo "📁 /app 内容:"
    ls -la /app/
    echo "📁 /AstrBot 内容（如果存在）:"
    ls -la /AstrBot/ 2>/dev/null || echo "（不存在）"
    exit 1
fi

# ========== 2️⃣ 启动 AstrBot ==========
echo "⏳ 启动 AstrBot..."
BOT_DIR=$(dirname "$(dirname "$BOT_SCRIPT")")
cd "$BOT_DIR"
echo "📂 工作目录: $(pwd)"

python3 -u "$BOT_SCRIPT" &
ASTRBOT_PID=$!
echo "✅ AstrBot 已启动 (PID: $ASTRBOT_PID)"

# ========== 3️⃣ 等待 AstrBot 就绪 ==========
echo "⏳ 等待 AstrBot 就绪（5 秒）..."
sleep 5

if kill -0 $ASTRBOT_PID 2>/dev/null; then
    echo "🟢 AstrBot 运行正常"
else
    echo "⚠️ AstrBot 进程已退出，检查日志..."
    wait $ASTRBOT_PID 2>/dev/null || true
fi

# ========== 4️⃣ 启动 Web UI 代理（监听 $PORT）==========
echo "⏳ 启动 Web UI 代理（端口 ${PORT}）..."
cd /app
python3 -u web_proxy.py &
WEB_PROXY_PID=$!
echo "✅ Web UI 代理已启动 (PID: $WEB_PROXY_PID)"

# ========== 5️⃣ 启动休眠代理（监听 6199）==========
echo "⏳ 启动休眠代理（端口 6199）..."
python3 -u sleep_proxy.py &
SLEEP_PROXY_PID=$!
echo "✅ 休眠代理已启动 (PID: $SLEEP_PROXY_PID)"

# ========== 6️⃣ 等待所有进程 ==========
echo ""
echo "=========================================="
echo "🎉 所有服务已启动！"
echo "🌐 Web UI: http://localhost:${PORT}/"
echo "🔌 休眠代理: :6199"
echo "=========================================="
echo ""

# 等待任意子进程退出
wait -n
echo "⚠️ 有进程退出，容器将重启..."
exit 1
