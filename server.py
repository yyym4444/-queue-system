"""
在线叫号系统 — 红·白·粉·黑 | 四城分权版
郑州 · 上海 · 成都 · 广州 — 每城独立管理
"""
import asyncio, json, os, secrets, time
from pathlib import Path
import aiohttp.web as web
from aiohttp import WSMsgType

# ============================================================
#  配置
# ============================================================
PORT = int(os.environ.get("PORT", 3000))
ROOT = Path(__file__).parent
PUBLIC = ROOT / "public"
STATE_FILE = ROOT / "state.json"

# 四城市
QUEUE_IDS = ["1", "2", "3", "4"]
QUEUE_NAMES = {"1": "郑州", "2": "上海", "3": "成都", "4": "广州"}

# 每城独立管理密码（默认统一，可选单独覆盖）
def _pw(q):
    key = f"ADMIN_PW_{q}"
    return os.environ.get(key) or os.environ.get("ADMIN_PASSWORD", "")
QUEUE_PASSWORDS = {q: _pw(q) for q in QUEUE_IDS}

# ============================================================
#  持久化 — 每个队列: number + last_updated
# ============================================================
def load_all():
    try:
        data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        qs = data.get("queues", {})
        result = {}
        for q in QUEUE_IDS:
            cur = qs.get(q, {"number": 0, "last_updated": None})
            # 兼容旧数据：没有 range 字段时默认为 0（不显示区间）
            cur.setdefault("range_start", 0)
            cur.setdefault("range_end", 0)
            result[q] = cur
        return result
    except Exception:
        return {q: {"number": 0, "last_updated": None, "range_start": 0, "range_end": 0} for q in QUEUE_IDS}

def save_all(queues: dict):
    STATE_FILE.write_text(json.dumps({"queues": queues}), encoding="utf-8")

queues_data = load_all()  # {"1": {"number":0, "last_updated":null}, ...}

# ============================================================
#  Admin 状态 — 每队列独立
# ============================================================
admin_state = {q: {"token": None, "ws": None} for q in QUEUE_IDS}

# ============================================================
#  公众观看端 — 按队列分组
# ============================================================
viewers: dict[str, list] = {q: [] for q in QUEUE_IDS}

# ============================================================
#  广播
# ============================================================
async def broadcast_queue(queue_id: str):
    qd = queues_data[queue_id]
    msg = json.dumps({
        "type": "number", "queue": queue_id,
        "number": qd["number"],
        "range_start": qd["range_start"], "range_end": qd["range_end"],
        "last_updated": qd["last_updated"],
    })
    dead = []
    for ws in viewers[queue_id]:
        try:
            if ws.closed:
                dead.append(ws)
            else:
                await ws.send_str(msg)
        except Exception:
            dead.append(ws)
    for ws in dead:
        viewers[queue_id].remove(ws)

async def send_to_admin(queue_id: str):
    ws = admin_state[queue_id]["ws"]
    if ws and not ws.closed:
        try:
            qd = queues_data[queue_id]
            await ws.send_str(json.dumps({
                "type": "number", "queue": queue_id,
                "number": qd["number"],
                "range_start": qd["range_start"],
                "range_end": qd["range_end"],
                "last_updated": qd["last_updated"],
            }))
        except Exception:
            admin_state[queue_id]["ws"] = None

def kick_old_admin(queue_id: str, new_ws):
    old = admin_state[queue_id]["ws"]
    if old and old is not new_ws and not old.closed:
        asyncio.ensure_future(_kick(old))

async def _kick(ws):
    try:
        await ws.send_str(json.dumps({"type": "kicked", "reason": "另一台设备已接管此窗口控制"}))
        await ws.close()
    except Exception:
        pass

# ============================================================
#  HTTP 路由
# ============================================================
_CACHE_CTRL = {"Cache-Control": "public, max-age=300"}

async def index_handler(request: web.Request):
    fp = PUBLIC / "index.html"
    bs = fp.read_bytes()
    return web.Response(body=bs, content_type="text/html", charset="utf-8", headers=_CACHE_CTRL)

async def monitor_handler(request: web.Request):
    fp = PUBLIC / "monitor.html"
    bs = fp.read_bytes()
    return web.Response(body=bs, content_type="text/html", charset="utf-8", headers=_CACHE_CTRL)

async def admin_handler(request: web.Request):
    fp = PUBLIC / "admin.html"
    bs = fp.read_bytes()
    return web.Response(body=bs, content_type="text/html", charset="utf-8", headers=_CACHE_CTRL)

async def css_handler(request: web.Request):
    return web.FileResponse(PUBLIC / "style.css", headers={
        "Content-Type": "text/css; charset=utf-8",
        "Cache-Control": "public, max-age=86400",
    })

async def health_handler(request: web.Request):
    """健康检查 — 供监控系统使用"""
    return web.json_response({
        "status": "ok",
        "queues": {q: QUEUE_NAMES[q] for q in QUEUE_IDS},
        "viewers": {q: len(viewers[q]) for q in QUEUE_IDS},
    })

async def api_get_number(request: web.Request):
    q = request.query.get("queue", "1")
    if q not in QUEUE_IDS:
        q = "1"
    qd = queues_data[q]
    return web.json_response({"queue": q, "name": QUEUE_NAMES[q], "number": qd["number"],
                              "range_start": qd["range_start"], "range_end": qd["range_end"],
                              "last_updated": qd["last_updated"]})

async def api_get_all(request: web.Request):
    """获取全部四队列状态（监控页用）"""
    result = {}
    for q in QUEUE_IDS:
        qd = queues_data[q]
        result[q] = {
            "name": QUEUE_NAMES[q],
            "number": qd["number"],
            "range_start": qd["range_start"],
            "range_end": qd["range_end"],
            "last_updated": qd["last_updated"],
        }
    return web.json_response(result)

async def api_admin_login(request: web.Request):
    """管理员登录 — 按队列独立认证"""
    try:
        body = await request.json()
    except Exception:
        raise web.HTTPBadRequest(text="Bad Request")

    q = body.get("queue", "1")
    if q not in QUEUE_IDS:
        q = "1"

    pw = body.get("password", "")
    if pw != QUEUE_PASSWORDS[q]:
        return web.json_response({"ok": False, "error": "密码错误"}, status=403)

    token = secrets.token_hex(16)
    admin_state[q]["token"] = token
    qd = queues_data[q]
    return web.json_response({
        "ok": True, "token": token,
        "queue": q, "name": QUEUE_NAMES[q],
        "number": qd["number"],
        "range_start": qd["range_start"],
        "range_end": qd["range_end"],
        "last_updated": qd["last_updated"],
    })

async def api_admin_control(request: web.Request):
    """管理员 HTTP 控制操作 — WebSocket 不稳定时的兜底通道"""
    try:
        body = await request.json()
    except Exception:
        raise web.HTTPBadRequest(text="Bad Request")

    q = body.get("queue", "1")
    if q not in QUEUE_IDS:
        return web.json_response({"ok": False, "error": "无效队列"}, status=400)

    token = body.get("token", "")
    st = admin_state[q]
    if not st["token"] or token != st["token"]:
        return web.json_response({"ok": False, "error": "认证失败"}, status=403)

    msg_type = body.get("type", "")
    changed = False
    if msg_type == "inc":
        queues_data[q]["number"] += 1
        changed = True
    elif msg_type == "dec" and queues_data[q]["number"] > 0:
        queues_data[q]["number"] -= 1
        changed = True
    elif msg_type == "set":
        n = body.get("number")
        if isinstance(n, int) and n >= 0:
            queues_data[q]["number"] = n
            changed = True
    elif msg_type == "reset":
        queues_data[q]["number"] = 0
        queues_data[q]["range_start"] = 0
        queues_data[q]["range_end"] = 0
        changed = True
    elif msg_type == "range_set":
        s = body.get("range_start")
        e = body.get("range_end")
        if isinstance(s, int) and isinstance(e, int) and 0 <= s <= e:
            queues_data[q]["range_start"] = s
            queues_data[q]["range_end"] = e
            queues_data[q]["number"] = s  # 当前号码跳到区间起点
            changed = True

    if changed:
        queues_data[q]["last_updated"] = int(time.time())
        save_all(queues_data)
        asyncio.create_task(broadcast_queue(q))
        qd = queues_data[q]
        return web.json_response({
            "ok": True, "queue": q, "number": qd["number"],
            "range_start": qd["range_start"], "range_end": qd["range_end"],
            "last_updated": qd["last_updated"],
        })

    return web.json_response({"ok": False, "error": "无效操作或号码未变"})

# ============================================================
#  WebSocket
# ============================================================
async def ws_handler(request: web.Request):
    ws = web.WebSocketResponse(max_msg_size=2048)
    await ws.prepare(request)

    is_admin = False
    admin_queue = None   # 该 admin 掌管哪个队列
    subscribed: set = set()

    try:
        async for msg in ws:
            if msg.type == WSMsgType.TEXT:
                try:
                    data = json.loads(msg.data)
                except json.JSONDecodeError:
                    continue

                msg_type = data.get("type", "")

                # —— 观众订阅队列 ——
                if msg_type == "subscribe":
                    qid = data.get("queue", "")
                    if qid == "all":
                        for q in QUEUE_IDS:
                            if q not in subscribed:
                                subscribed.add(q)
                                viewers[q].append(ws)
                        result = {}
                        for q in QUEUE_IDS:
                            qd = queues_data[q]
                            result[q] = {
                                "name": QUEUE_NAMES[q],
                                "number": qd["number"],
                                "range_start": qd["range_start"],
                                "range_end": qd["range_end"],
                                "last_updated": qd["last_updated"],
                            }
                        await ws.send_str(json.dumps({"type": "all_numbers", "queues": result}))
                    elif qid in QUEUE_IDS and qid not in subscribed:
                        subscribed.add(qid)
                        viewers[qid].append(ws)
                        qd = queues_data[qid]
                        await ws.send_str(json.dumps({
                            "type": "number", "queue": qid,
                            "number": qd["number"],
                            "range_start": qd["range_start"],
                            "range_end": qd["range_end"],
                            "last_updated": qd["last_updated"],
                        }))

                # —— 管理员认证（按队列） ——
                elif msg_type == "auth":
                    qid = data.get("queue", "1")
                    if qid not in QUEUE_IDS:
                        qid = "1"
                    token = data.get("token", "")
                    st = admin_state[qid]
                    if st["token"] and token == st["token"]:
                        # 踢旧 admin
                        kick_old_admin(qid, ws)
                        st["ws"] = ws
                        is_admin = True
                        admin_queue = qid
                        # 从观众列表移除
                        for q in subscribed:
                            try:
                                viewers[q].remove(ws)
                            except ValueError:
                                pass
                        subscribed.clear()
                        qd = queues_data[qid]
                        await ws.send_str(json.dumps({
                            "type": "auth_ok",
                            "queue": qid, "name": QUEUE_NAMES[qid],
                            "number": qd["number"],
                            "range_start": qd["range_start"],
                            "range_end": qd["range_end"],
                            "last_updated": qd["last_updated"],
                        }))
                    else:
                        await ws.send_str(json.dumps({"type": "auth_err", "error": "认证失败"}))

                # —— 只有 admin 可以操作 ——
                if not is_admin:
                    continue

                qid = admin_queue
                changed = False
                if msg_type == "inc":
                    queues_data[qid]["number"] += 1
                    changed = True
                elif msg_type == "dec" and queues_data[qid]["number"] > 0:
                    queues_data[qid]["number"] -= 1
                    changed = True
                elif msg_type == "set":
                    n = data.get("number")
                    if isinstance(n, int) and n >= 0:
                        queues_data[qid]["number"] = n
                        changed = True
                elif msg_type == "reset":
                    queues_data[qid]["number"] = 0
                    queues_data[qid]["range_start"] = 0
                    queues_data[qid]["range_end"] = 0
                    changed = True
                elif msg_type == "range_set":
                    s = data.get("range_start")
                    e = data.get("range_end")
                    if isinstance(s, int) and isinstance(e, int) and 0 <= s <= e:
                        queues_data[qid]["range_start"] = s
                        queues_data[qid]["range_end"] = e
                        queues_data[qid]["number"] = s
                        changed = True

                if changed:
                    queues_data[qid]["last_updated"] = int(time.time())
                    save_all(queues_data)
                    await send_to_admin(qid)
                    await broadcast_queue(qid)

            elif msg.type == WSMsgType.ERROR:
                pass

    finally:
        if is_admin:
            if admin_state[admin_queue]["ws"] is ws:
                admin_state[admin_queue]["ws"] = None
        for q in subscribed:
            try:
                viewers[q].remove(ws)
            except ValueError:
                pass

    return ws

# ============================================================
#  心跳
# ============================================================
async def heartbeat():
    while True:
        await asyncio.sleep(30)
        ping = json.dumps({"type": "ping"})
        for q in QUEUE_IDS:
            dead = []
            for v in viewers[q]:
                try:
                    if not v.closed:
                        await v.send_str(ping)
                except Exception:
                    dead.append(v)
            for v in dead:
                try:
                    viewers[q].remove(v)
                except ValueError:
                    pass
            aws = admin_state[q]["ws"]
            if aws and not aws.closed:
                try:
                    await aws.send_str(ping)
                except Exception:
                    admin_state[q]["ws"] = None

# ============================================================
#  启动
# ============================================================
def main():
    import sys
    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    app = web.Application()
    app.router.add_get("/", index_handler)
    app.router.add_get("/index.html", index_handler)
    app.router.add_get("/monitor", monitor_handler)
    app.router.add_get("/admin", admin_handler)
    app.router.add_get("/style.css", css_handler)
    app.router.add_get("/health", health_handler)
    app.router.add_get("/api/number", api_get_number)
    app.router.add_get("/api/all", api_get_all)
    app.router.add_post("/api/admin/login", api_admin_login)
    app.router.add_post("/api/admin/control", api_admin_control)
    app.router.add_get("/ws", ws_handler)

    async def start_heartbeat(app):
        asyncio.create_task(heartbeat())
    app.on_startup.append(start_heartbeat)

    print(f"  [OK] 四城叫号系统已启动 -> http://localhost:{PORT}")
    for q in QUEUE_IDS:
        pinfo = QUEUE_PASSWORDS[q]
        print(f"       {QUEUE_NAMES[q]} (queue={q})  号码:{queues_data[q]['number']}  密码:{'*' * len(pinfo)}")
    print(f"       监控总览 -> http://localhost:{PORT}/monitor")

    web.run_app(app, host="0.0.0.0", port=PORT,
                access_log=None,  # 关闭访问日志减少 I/O
                backlog=2048,     # 增大连接队列
                )

if __name__ == "__main__":
    main()
