@echo off
chcp 65001 >nul
title 叫号系统 — 一键安装

echo.
echo  ============================================
echo   在线叫号系统 — 一键安装
echo  ============================================
echo.

:: 检查 Node.js
where node >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] 未检测到 Node.js，请先安装：
    echo   https://nodejs.org/zh-cn/download/
    echo   推荐 LTS 版本（20.x 或 22.x）
    echo.
    pause
    exit /b 1
)

echo [OK] Node.js:
node --version

:: 安装依赖
echo.
echo [INFO] 安装依赖中...
cd /d "D:\queue-system"
call npm install --production

:: 安装 PM2（全局）
echo.
echo [INFO] 安装 PM2 进程管理器...
call npm install -g pm2

:: 创建日志目录
if not exist "logs" mkdir logs

echo.
echo  ============================================
echo   安装完成!
echo  ============================================
echo.
echo   启动方式:
echo     1. 开发/测试:  npm start
echo        → 访问 http://localhost:3000
echo.
echo     2. 生产环境:  npm run pm2:start
echo        → 访问 http://localhost:3000
echo        → PM2 集群模式，利用多核 CPU
echo.
echo   管理页面: http://localhost:3000/admin
echo   密码: 请通过环境变量 ADMIN_PASSWORD 设置
echo.
echo   修改密码: set ADMIN_PASSWORD=你的密码
echo.
echo   停止服务: npm run pm2:stop
echo   重启服务: npm run pm2:restart
echo.
pause
