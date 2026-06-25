# 四城叫号系统 · 公网部署指南

## 第一步：买一台云服务器

两家主流选择（任选一家即可）：

### 阿里云
1. 打开 [aliyun.com](https://www.aliyun.com)，搜"轻量应用服务器"
2. 选择配置：**2核2G 内存**（¥34/月起），系统选 **Ubuntu 22.04**
3. 购买后，在控制台找到「远程连接」→ 点进去就是命令行

### 腾讯云
1. 打开 [cloud.tencent.com](https://cloud.tencent.com)，搜"轻量应用服务器"
2. 选择配置：**2核2G 内存**（¥28/月起），镜像选 **Ubuntu 22.04**
3. 购买后，在控制台找到「登录」→ 点进去就是命令行

> 各地数据中心任选（比如选上海），对四城用户访问速度都差不多。

---

## 第二步：放行端口

### 2.1 云服务器安全组（网页操作）
登录云服务器控制台 → 找到「安全组」或「防火墙」→ 添加规则：

| 端口 | 协议 | 来源 | 说明 |
|------|------|------|------|
| 3000 | TCP | 0.0.0.0/0 | 叫号系统主端口 |
| 80 | TCP | 0.0.0.0/0 | （可选，用 nginx 时） |
| 443 | TCP | 0.0.0.0/0 | （可选，HTTPS 时） |

⚠️ **这一步最容易忘，忘了外面就打不开！**

### 2.2 服务器内部防火墙（已由 deploy.sh 自动处理，无需手动操作）

---

## 第三步：上传项目文件

在服务器命令行中：

```bash
# 方法一：用 git（推荐）
cd /opt
git clone https://github.com/你的仓库/queue-system.git   # 或
# 先把项目推到自己 GitHub，再 clone

# 方法二：用 scp（在你自己电脑上执行）
scp -r D:\queue-system\* root@你的服务器IP:/opt/queue-system/
```

---

## 第四步：一键部署

在服务器上执行：

```bash
cd /opt/queue-system
chmod +x deploy.sh
sudo bash deploy.sh
```

脚本自动完成：
- 安装 Python 依赖 (`aiohttp`)
- 配置 systemd 服务守护（崩溃自动重启，开机自启）
- 放行系统防火墙

部署完成后脚本会打印出所有访问地址。

---

## 第五步：验证

浏览器打开 `http://你的服务器IP:3000/?queue=1`，看到郑州叫号页面即成功。

---

## 常用命令

```bash
# 查看服务状态
systemctl status queue-system

# 重启服务（改密码后）
systemctl restart queue-system

# 查看日志
journalctl -u queue-system -f

# 停止服务
systemctl stop queue-system
```

---

## 修改密码

编辑服务配置：

```bash
nano /etc/systemd/system/queue-system.service
```

修改 `ADMIN_PASSWORD` 那行（或 `ADMIN_PW_1` ~ `ADMIN_PW_4` 分别设四城密码），然后：

```bash
systemctl daemon-reload
systemctl restart queue-system
```

---

## （可选）改用 80 端口 + Nginx

默认用 3000 端口访问。如果你希望用标准 80 端口（URL 里不用写端口号）：

```bash
apt-get install nginx -y
cp /opt/queue-system/nginx.conf /etc/nginx/sites-available/queue-system
ln -s /etc/nginx/sites-available/queue-system /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl reload nginx
```

之后访问 `http://你的服务器IP/?queue=1` 即可（不用写 3000）。

---

## 发给四城同事的 URL 清单

部署完成后，复制下面这些发给对应的人：

```
【郑州】
  公众大屏: http://X.X.X.X:3000/?queue=1
  管理后台: http://X.X.X.X:3000/admin?queue=1
  密码: 请设置你自己的密码

【上海】
  公众大屏: http://X.X.X.X:3000/?queue=2
  管理后台: http://X.X.X.X:3000/admin?queue=2
  密码: 请设置你自己的密码

【成都】
  公众大屏: http://X.X.X.X:3000/?queue=3
  管理后台: http://X.X.X.X:3000/admin?queue=3
  密码: 请设置你自己的密码

【广州】
  公众大屏: http://X.X.X.X:3000/?queue=4
  管理后台: http://X.X.X.X:3000/admin?queue=4
  密码: 请设置你自己的密码

【总部监控】
  监控总览: http://X.X.X.X:3000/monitor
```

把 `X.X.X.X` 替换成你服务器的公网 IP。

---

## 费用估算

| 项目 | 月费用 |
|------|--------|
| 轻量应用服务器 2核2G | ¥28 - 60 |
| 域名（可选） | ¥几十/年 |
| **合计** | **约 ¥30-70/月** |

系统运行期间几乎不消耗带宽，除非有大屏设备 24 小时轮询刷新。
