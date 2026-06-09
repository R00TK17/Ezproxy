# EzProxy

基于 [mitmproxy](https://mitmproxy.org/) 的轻量级 HTTP/HTTPS 流量记录器，仿 Burp Suite 的 Proxy 模块。拦截并记录所有流量，通过 Web 界面浏览。

## 功能特性

- **捕获全部 HTTP/HTTPS 流量** — 完整记录请求/响应的头部和正文
- **Web 可视化界面** — Burp 风格的历史记录表，主机分组树，请求/响应详情面板
- **目标站点聚焦** — 只看指定域名，隐藏第三方干扰（广告、统计、CDN）
- **主机分组折叠** — 按域名自动分组，默认折叠，点击展开
- **搜索筛选** — 按 URL/域名、HTTP 方法、状态码类别过滤
- **cURL 导出** — 一键复制任意请求为 cURL 命令
- **彩色标识** — 方法标签着色（GET 绿、POST 蓝等）、状态码着色
- **退出即清空** — 关闭代理自动清理数据库，每次启动都是干净状态

## 快速开始

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 启动代理
python ezproxy.py

# 3. 浏览器设置代理 → localhost:8080
# 4. 打开 http://localhost:5000 查看流量
```

## HTTPS 配置

拦截 HTTPS 流量需要安装 mitmproxy 的 CA 证书：

### Windows（Chrome / Edge）
```powershell
certutil -addstore Root %USERPROFILE%\.mitmproxy\mitmproxy-ca-cert.cer
```

或者双击 `C:\Users\你的用户名\.mitmproxy\mitmproxy-ca-cert.cer` → 安装证书 → 受信任的根证书颁发机构。

### Firefox
1. 设置 → 隐私与安全 → 证书 → 查看证书
2. 导入 `~/.mitmproxy/mitmproxy-ca-cert.pem`
3. 勾选「信任此 CA 标识网站」

### macOS
```bash
sudo security add-trusted-cert -d -p ssl -k /Library/Keychains/System.keychain ~/.mitmproxy/mitmproxy-ca-cert.pem
```

## 命令行参数

```
python ezproxy.py [参数]

参数:
  -p, --proxy-port   代理端口（默认: 8080）
  -w, --web-port     Web 界面端口（默认: 5000）
  --db               自定义数据库路径（默认: ~/.ezproxy/flows.db）
  -V, --version      显示版本号
```

## Web 界面说明

```
┌─ 工具栏 ────────────────────────────────────────────────────┐
│ 🔍 EzProxy  [过滤URL...] [GET▼] [2xx▼] [目标域名] [🎯] ... │
├─ 流量表 ────────────────────────────────────────────────────┤
│ ▶ 🖥 example.com 🎯                    请求数量: 5          │
│ ▶ 🖥 cdn.example.com                    请求数量: 12        │
│   （默认折叠 — 点击展开）                                    │
├─ 详情面板 ──────────────────────────────────────────────────┤
│ [请求] [响应]                                                │
│ GET /api/users HTTP/1.1                                      │
│ Host: example.com                                            │
│ ...                                                          │
└──────────────────────────────────────────────────────────────┘
```

- 点击**主机分组行** → 展开/折叠该域名下的所有请求
- 点击主机名旁的 **🎯** → 只看该站点的流量（隐藏所有第三方请求）
- 点击**某条请求** → 下方显示完整请求头和正文
- 按 **Esc** → 关闭详情面板

## 项目结构

```
Ezproxy/
├── ezproxy.py               # 启动入口
├── requirements.txt          # mitmproxy、flask、rich
└── ezproxy/
    ├── __init__.py
    ├── db.py                 # SQLite 存储层（WAL 模式，线程安全）
    ├── addon.py              # mitmproxy 插件（流量捕获）
    ├── web.py                # Flask JSON API
    └── templates/
        └── index.html        # 单页 Web 界面
```

## 工作原理

1. `ezproxy.py` 同时启动 **mitmproxy**（代理引擎）和 **Flask**（Web 界面）
2. 浏览器请求经过 `localhost:8080` → mitmproxy 拦截
3. `EzProxyAddon` 捕获每对请求/响应 → 写入 SQLite
4. Web 界面每 3 秒轮询 Flask API → 展示分组流量

## License

MIT
