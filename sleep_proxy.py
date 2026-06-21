#!/usr/bin/env python3
"""
AstrBot 休眠代理
- 监听 6199 端口，接收 NapCat 的 WS 连接
- 内部连接 AstrBot (127.0.0.1:6185)
- 空闲超时后断开与 AstrBot 的连接，NapCat 不受影响
- 有新消息时重新连上 AstrBot
"""


import asyncio
import websockets
import json
import time
import os
import logging

# ========== 配置 ==========
PROXY_PORT = int(os.getenv("PROXY_PORT", "6199"))
ASTRBOT_HOST = os.getenv("ASTRBOT_HOST", "127.0.0.1")
ASTRBOT_PORT = int(os.getenv("ASTRBOT_PORT", "6185"))
ASTRBOT_WS_PATH = os.getenv("ASTRBOT_WS_PATH", "/ws")

IDLE_TIMEOUT = int(os.getenv("IDLE_TIMEOUT", "300"))         # 空闲超时（秒）
CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", "10"))      # 检查间隔
WARMUP_DELAY = int(os.getenv("WARMUP_DELAY", "3"))           # 重连后等待秒数

logger = logging.getLogger("sleep_proxy")
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s %(message)s",
    datefmt="%H:%M:%S"
)

# ========== 共享状态 ==========
class ProxyState:
    def __init__(self):
        self.last_msg_time = time.time()
        self.is_sleeping = False
        self.pending_messages = asyncio.Queue()  # 休眠期间缓存的消息
        self.napcat_ws = None                    # NapCat 连接
        self.astrbot_ws = None                   # AstrBot 连接
        self.lock = asyncio.Lock()

state = ProxyState()

# ========== 健康检查 ==========
async def health_check():
    """Railway 健康检查"""
    import aiohttp
    from aiohttp import web
    
    async def handle(request):
        return web.Response(
            text=json.dumps({
                "status": "ok",
                "sleeping": state.is_sleeping,
                "napcat_connected": state.napcat_ws is not None,
                "astrbot_connected": state.astrbot_ws is not None,
                "idle_seconds": round(time.time() - state.last_msg_time, 1)
            }),
            content_type="application/json"
        )
    
    app = web.Application()
    app.router.add_get('/', handle)
    
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', int(os.getenv("PORT", "8080")))
    await site.start()
    logger.info(f"✅ 健康检查 :{os.getenv('PORT', '8080')}")

# ========== 连接 AstrBot ==========
async def connect_astrbot():
    """连接到 AstrBot 的 WS 服务端"""
    url = f"ws://{ASTRBOT_HOST}:{ASTRBOT_PORT}{ASTRBOT_WS_PATH}"
    try:
        ws = await asyncio.wait_for(
            websockets.connect(url, max_size=10*1024*1024, ping_interval=20),
            timeout=10
        )
        logger.info(f"✅ 已连接 AstrBot: {url}")
        return ws
    except Exception as e:
        logger.warning(f"⚠️ 连接 AstrBot 失败: {e}")
        return None

# ========== 处理从 AstrBot 收到的消息 ==========
async def astrbot_reader():
    """读取 AstrBot 发来的消息并转发给 NapCat"""
    while True:
        try:
            if state.astrbot_ws is None:
                await asyncio.sleep(1)
                continue
            
            msg = await asyncio.wait_for(state.astrbot_ws.recv(), timeout=30)
            state.last_msg_time = time.time()
            
            # 转发给 NapCat
            if state.napcat_ws and not state.napcat_ws.closed:
                await state.napcat_ws.send(msg)
        except asyncio.TimeoutError:
            continue
        except websockets.ConnectionClosed:
            logger.info("🔌 AstrBot 连接已断开")
            state.astrbot_ws = None
            await asyncio.sleep(1)
        except Exception as e:
            logger.error(f"astrbot_reader 错误: {e}")
            await asyncio.sleep(1)

# ========== 空闲检测循环 ==========
async def idle_check_loop():
    """检测空闲，决定休眠/唤醒"""
    while True:
        await asyncio.sleep(CHECK_INTERVAL)
        
        idle = time.time() - state.last_msg_time
        
        async with state.lock:
            if idle > IDLE_TIMEOUT and not state.is_sleeping:
                # → 进入休眠
                logger.info(f"🟡 空闲 {idle:.0f}s（超时 {IDLE_TIMEOUT}s），断开 AstrBot 进入休眠")
                state.is_sleeping = True
                
                # 断开与 AstrBot 的连接
                if state.astrbot_ws and not state.astrbot_ws.closed:
                    await state.astrbot_ws.close()
                    state.astrbot_ws = None
                    logger.info("💤 AstrBot 连接已断开（休眠中）")
            
            elif idle <= IDLE_TIMEOUT and state.is_sleeping:
                # → 唤醒（如果 AstrBot 已断开，会在收到消息时重连）
                logger.info(f"🟢 空闲 {idle:.0f}s（低于阈值），准备唤醒")
                state.is_sleeping = False

# ========== 处理 NapCat 连接 ==========
async def handle_napcat(ws_napcat):
    """处理一个 NapCat 连接"""
    state.napcat_ws = ws_napcat
    state.last_msg_time = time.time()
    
    logger.info("📡 NapCat 已连接")
    
    # 先尝试连接 AstrBot
    if state.astrbot_ws is None or state.astrbot_ws.closed:
        state.astrbot_ws = await connect_astrbot()
        if state.astrbot_ws:
            state.is_sleeping = False
    
    # 启动 AstrBot 消息读取协程（全局只跑一个）
    reader_task = asyncio.create_task(astrbot_reader())
    
    try:
        # 持续接收 NapCat 的消息
        async for msg in ws_napcat:
            state.last_msg_time = time.time()
            
            # 解析消息判断类型
            try:
                data = json.loads(msg)
                msg_type = data.get("post_type") or data.get("message_type", "unknown")
                logger.debug(f"📨 消息类型: {msg_type}")
            except json.JSONDecodeError:
                pass
            
            async with state.lock:
                # 如果处于休眠状态 → 先唤醒（重连 AstrBot）
                if state.is_sleeping or state.astrbot_ws is None or state.astrbot_ws.closed:
                    logger.info("🔵 收到消息，唤醒中...")
                    state.astrbot_ws = await connect_astrbot()
                    if state.astrbot_ws:
                        state.is_sleeping = False
                        # 等待预热
                        if WARMUP_DELAY > 0:
                            logger.info(f"⏳ 等待预热 {WARMUP_DELAY}s...")
                            await asyncio.sleep(WARMUP_DELAY)
                        logger.info("☀️ AstrBot 已唤醒，继续转发")
                    else:
                        logger.warning("⚠️ AstrBot 暂时不可用，消息缓存")
                        # 缓存消息，稍后重试
                        asyncio.create_task(retry_send(msg))
                        continue
                
                # 转发到 AstrBot
                try:
                    await state.astrbot_ws.send(msg)
                except websockets.ConnectionClosed:
                    logger.warning("⚠️ AstrBot 连接断开，尝试重连...")
                    state.astrbot_ws = await connect_astrbot()
                    if state.astrbot_ws:
                        await state.astrbot_ws.send(msg)
    
    except websockets.ConnectionClosed:
        logger.info("🔌 NapCat 已断开")
    finally:
        reader_task.cancel()
        state.napcat_ws = None

async def retry_send(msg, retries=3):
    """缓存的消息重试发送"""
    for i in range(retries):
        await asyncio.sleep(2)
        if state.astrbot_ws and not state.astrbot_ws.closed:
            try:
                await state.astrbot_ws.send(msg)
                logger.info("✅ 缓存消息已发送")
                return
            except:
                pass
    logger.warning(f"⚠️ 缓存消息发送失败（{retries}次重试）")

# ========== 主函数 ==========
async def main():
    logger.info("=" * 50)
    logger.info("🤖 AstrBot 休眠代理 v2.0")
    logger.info(f"代理端口 :{PROXY_PORT} → AstrBot :{ASTRBOT_PORT}{ASTRBOT_WS_PATH}")
    logger.info(f"空闲超时: {IDLE_TIMEOUT}s | 预热: {WARMUP_DELAY}s")
    logger.info("=" * 50)
    
    # 启动健康检查
    await health_check()
    
    # 启动空闲检测
    asyncio.create_task(idle_check_loop())
    
    # 启动 WebSocket 代理
    async with websockets.serve(
        handle_napcat, "0.0.0.0", PROXY_PORT,
        max_size=10*1024*1024,
        ping_interval=25,
        ping_timeout=10
    ):
        logger.info(f"🟢 代理已在 :{PROXY_PORT} 上监听，等待 NapCat 连接...")
        await asyncio.Future()  # 永远运行

if __name__ == "__main__":
    asyncio.run(main())
