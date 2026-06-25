const http = require('http');
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const { WebSocketServer } = require('ws');

// ============================================================
//  配置
// ============================================================
const PORT = process.env.PORT || 3000;
const ADMIN_PASSWORD = process.env.ADMIN_PASSWORD || '';
const STATE_FILE = path.join(__dirname, 'state.json');

// 持久化当前叫号数字
function loadNumber() {
  try {
    const raw = fs.readFileSync(STATE_FILE, 'utf-8');
    const data = JSON.parse(raw);
    return typeof data.number === 'number' ? data.number : 0;
  } catch {
    return 0;
  }
}
function saveNumber(n) {
  fs.writeFileSync(STATE_FILE, JSON.stringify({ number: n }), 'utf-8');
}

let currentNumber = loadNumber();

// admin token 管理——保证只有一台设备能控制
let adminToken = null; // { token: string, ts: number }

// ============================================================
//  MIME 映射
// ============================================================
const MIME = {
  '.html': 'text/html; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.js': 'application/javascript; charset=utf-8',
  '.png': 'image/png',
  '.ico': 'image/x-icon',
};

function serveStatic(filePath, res) {
  const ext = path.extname(filePath).toLowerCase();
  const contentType = MIME[ext] || 'application/octet-stream';
  try {
    const content = fs.readFileSync(filePath);
    res.writeHead(200, { 'Content-Type': contentType });
    res.end(content);
  } catch {
    res.writeHead(404);
    res.end('Not Found');
  }
}

// ============================================================
//  HTTP 服务
// ============================================================
function handleRequest(req, res) {
  const url = new URL(req.url, `http://localhost:${PORT}`);
  const route = url.pathname;

  // --- 静态文件 ---
  if (route === '/' || route === '/index.html') {
    return serveStatic(path.join(__dirname, 'public', 'index.html'), res);
  }
  if (route === '/admin') {
    return serveStatic(path.join(__dirname, 'public', 'admin.html'), res);
  }
  if (route === '/style.css') {
    return serveStatic(path.join(__dirname, 'public', 'style.css'), res);
  }
  if (route === '/favicon.ico') {
    res.writeHead(204);
    return res.end();
  }

  // --- API: 获取当前号码（HTTP 轮询兜底） ---
  if (route === '/api/number' && req.method === 'GET') {
    res.writeHead(200, { 'Content-Type': 'application/json' });
    return res.end(JSON.stringify({ number: currentNumber }));
  }

  // --- API: admin 登录 ---
  if (route === '/api/admin/login' && req.method === 'POST') {
    let body = '';
    req.on('data', c => (body += c));
    req.on('end', () => {
      try {
        const { password } = JSON.parse(body);
        if (password === ADMIN_PASSWORD) {
          const token = crypto.randomUUID();
          adminToken = { token, ts: Date.now() };
          res.writeHead(200, { 'Content-Type': 'application/json' });
          return res.end(JSON.stringify({ ok: true, token }));
        }
        res.writeHead(403, { 'Content-Type': 'application/json' });
        return res.end(JSON.stringify({ ok: false, error: '密码错误' }));
      } catch {
        res.writeHead(400);
        return res.end('Bad Request');
      }
    });
    return;
  }

  // 404
  res.writeHead(404);
  res.end('Not Found');
}

const server = http.createServer(handleRequest);

// ============================================================
//  WebSocket 服务
// ============================================================
const wss = new WebSocketServer({ server, maxPayload: 256 });

// 广播当前号码给所有公众客户端
function broadcastNumber() {
  const msg = JSON.stringify({ type: 'number', number: currentNumber });
  wss.clients.forEach(client => {
    if (client.readyState === 1 && !client.__isAdmin) {
      client.send(msg);
    }
  });
}

// 给 admin 发送当前状态
function sendToAdmin(ws) {
  ws.send(JSON.stringify({ type: 'number', number: currentNumber }));
}

wss.on('connection', (ws, req) => {
  ws.__isAdmin = false;

  ws.on('message', (raw) => {
    let data;
    try {
      data = JSON.parse(raw.toString());
    } catch {
      return;
    }

    // --- admin 认证 ---
    if (data.type === 'auth') {
      if (adminToken && data.token === adminToken.token) {
        // 踢掉旧的 admin 连接（如果有）
        wss.clients.forEach(client => {
          if (client !== ws && client.__isAdmin && client.readyState === 1) {
            client.send(JSON.stringify({ type: 'kicked', reason: '另一台设备已接管控制' }));
            client.close();
          }
        });
        ws.__isAdmin = true;
        adminToken = { token: data.token, ts: Date.now() };
        ws.send(JSON.stringify({ type: 'auth_ok' }));
        sendToAdmin(ws);
        // 同时广播给观看端
        broadcastNumber();
      } else {
        ws.send(JSON.stringify({ type: 'auth_err', error: '认证失败' }));
      }
      return;
    }

    // --- 只有 admin 可以操作 ---
    if (!ws.__isAdmin) return;

    if (data.type === 'set') {
      const n = Number(data.number);
      if (Number.isInteger(n) && n >= 0) {
        currentNumber = n;
        saveNumber(currentNumber);
        sendToAdmin(ws);
        broadcastNumber();
      }
    } else if (data.type === 'inc') {
      currentNumber++;
      saveNumber(currentNumber);
      sendToAdmin(ws);
      broadcastNumber();
    } else if (data.type === 'dec') {
      if (currentNumber > 0) {
        currentNumber--;
        saveNumber(currentNumber);
        sendToAdmin(ws);
        broadcastNumber();
      }
    } else if (data.type === 'reset') {
      currentNumber = 0;
      saveNumber(currentNumber);
      sendToAdmin(ws);
      broadcastNumber();
    }
  });

  // 新连接立刻推送当前号码
  ws.send(JSON.stringify({ type: 'number', number: currentNumber }));

  ws.on('close', () => {
    // admin 断开不清理 token，允许重连
  });
});

// ============================================================
//  心跳——保持长连接存活，清理死连接
// ============================================================
const interval = setInterval(() => {
  wss.clients.forEach(ws => {
    if (ws.__alive === false) return ws.terminate();
    ws.__alive = false;
    ws.ping();
  });
}, 30000);

wss.on('connection', (ws) => {
  ws.__alive = true;
  ws.on('pong', () => { ws.__alive = true; });
});

// 每 30 秒广播一次心跳保活
setInterval(() => {
  const ping = JSON.stringify({ type: 'ping' });
  wss.clients.forEach(client => {
    if (client.readyState === 1) client.send(ping);
  });
}, 30000);

// ============================================================
//  启动
// ============================================================
server.listen(PORT, () => {
  console.log(`✅ 叫号系统已启动 → http://localhost:${PORT}`);
  console.log(`   管理页面 → http://localhost:${PORT}/admin`);
  console.log(`   当前号码: ${currentNumber}`);
  console.log(`   管理员密码: ${ADMIN_PASSWORD}`);
  console.log('');
  console.log('   提示: 使用 PM2 cluster 模式可支撑万级并发');
  console.log('   pm2 start server.js -i max --name queue-system');
});
