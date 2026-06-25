#!/bin/bash
# =============================================================
#  四城叫号系统 — 一键公网部署脚本
#  适用: Ubuntu 20.04 / 22.04 / 24.04
#  用法: chmod +x deploy.sh && sudo bash deploy.sh
# =============================================================
set -e

APP_DIR="/opt/queue-system"
SERVICE_NAME="queue-system"
PYTHON=$(which python3)

echo "============================================"
echo "  四城叫号系统 · 公网部署"
echo "============================================"
echo ""

# 1. 基础检测
if [ "$(id -u)" != "0" ]; then
    echo "[ERROR] 请用 sudo 运行"
    exit 1
fi

echo "[1/5] 安装系统依赖..."
apt-get update -qq
apt-get install -y -qq python3-pip

echo "[2/5] 安装 Python 依赖..."
pip3 install aiohttp

echo "[3/5] 部署项目文件..."
mkdir -p "$APP_DIR"
# 如果当前目录有项目文件则复制，否则从默认路径
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
if [ -f "$SCRIPT_DIR/server.py" ]; then
    cp -r "$SCRIPT_DIR"/* "$APP_DIR/"
else
    echo "       请将项目文件放在 $SCRIPT_DIR 下"
    exit 1
fi

# 4. 配置 systemd 服务
echo "[4/5] 配置服务守护..."
cp "$APP_DIR/queue-system.service" /etc/systemd/system/
systemctl daemon-reload
systemctl enable "$SERVICE_NAME"
systemctl restart "$SERVICE_NAME"

# 5. 放行防火墙
echo "[5/5] 配置防火墙..."

# 云服务器安全组（阿里云/腾讯云）需要在网页控制台手动放行 3000 端口
# 此处仅处理系统级防火墙 (ufw)

if command -v ufw &>/dev/null; then
    ufw allow 3000/tcp 2>/dev/null || true
    echo "       ufw 已放行 3000 端口"
fi

# 检测 firewalld
if command -v firewall-cmd &>/dev/null; then
    firewall-cmd --add-port=3000/tcp --permanent 2>/dev/null || true
    firewall-cmd --reload 2>/dev/null || true
    echo "       firewalld 已放行 3000 端口"
fi

# 检测 iptables
if command -v iptables &>/dev/null; then
    iptables -I INPUT -p tcp --dport 3000 -j ACCEPT 2>/dev/null || true
    echo "       iptables 已放行 3000 端口"
fi

echo ""
echo "============================================"
echo "  部署完成!"
echo "============================================"
echo ""

# 获取公网 IP
PUBLIC_IP=$(curl -s ifconfig.me 2>/dev/null || curl -s ip.sb 2>/dev/null || echo "你的服务器IP")

echo "  服务状态:"
systemctl status "$SERVICE_NAME" --no-pager -l | head -8

echo ""
echo "  访问地址:"
echo "    郑州公众: http://${PUBLIC_IP}:3000/?queue=1"
echo "    上海公众: http://${PUBLIC_IP}:3000/?queue=2"
echo "    成都公众: http://${PUBLIC_IP}:3000/?queue=3"
echo "    广州公众: http://${PUBLIC_IP}:3000/?queue=4"
echo "    监控总览: http://${PUBLIC_IP}:3000/monitor"
echo ""
echo "  管理地址:"
echo "    郑州管理: http://${PUBLIC_IP}:3000/admin?queue=1"
echo "    上海管理: http://${PUBLIC_IP}:3000/admin?queue=2"
echo "    成都管理: http://${PUBLIC_IP}:3000/admin?queue=3"
echo "    广州管理: http://${PUBLIC_IP}:3000/admin?queue=4"
echo ""
echo "  默认管理密码: admin888"
echo ""
echo "  ⚠️  重要: 请前往云服务器控制台「安全组」中放行 3000 端口!"
echo "      (阿里云 / 腾讯云网页控制台操作)"
echo ""
