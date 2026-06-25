# 在线叫号系统 — 四城版

红 · 白 · 粉 · 黑 主题，郑州 · 上海 · 成都 · 广州 四城独立叫号。

## 页面

| 角色 | 地址 | 说明 |
|------|------|------|
| 郑州大屏 | `/?queue=1` | 只看郑州，无切换入口 |
| 上海大屏 | `/?queue=2` | 只看上海，无切换入口 |
| 成都大屏 | `/?queue=3` | 只看成都，无切换入口 |
| 广州大屏 | `/?queue=4` | 只看广州，无切换入口 |
| 监控总览 | `/monitor` | 四城同屏，管理人员专用 |
| 郑州管理 | `/admin?queue=1` | 只控制郑州 |
| 上海管理 | `/admin?queue=2` | 只控制上海 |
| 成都管理 | `/admin?queue=3` | 只控制成都 |
| 广州管理 | `/admin?queue=4` | 只控制广州 |

**密码**: 通过环境变量 `ADMIN_PASSWORD` 设置，无默认值

## 修改密码

```bash
# 四城统一密码
set ADMIN_PASSWORD=你的密码 && python server.py

# 每城单独密码
set ADMIN_PW_1=郑州密码
set ADMIN_PW_2=上海密码
set ADMIN_PW_3=成都密码
set ADMIN_PW_4=广州密码
python server.py
```

## 启动

```bash
pip install aiohttp
python server.py
```

## 技术

Python + aiohttp 异步，单进程 5000+ WebSocket 连接，号码持久化 state.json。
