# EzProxy

A lightweight HTTP/HTTPS traffic recorder powered by [mitmproxy](https://mitmproxy.org/), inspired by Burp Suite's Proxy module. Intercept, record, and browse web traffic through a clean web UI.

## Features

- **Capture all HTTP/HTTPS traffic** — full request/response with headers + body
- **Web UI** — Burp-style traffic history with grouped host tree, request/response detail viewer
- **Scope filter** — focus on a target host, hide third-party noise (ads, analytics, CDN)
- **Collapsible host groups** — traffic auto-grouped by domain, collapsed by default
- **Search & filter** — filter by URL/host, HTTP method, status code class
- **cURL export** — one-click copy any request as a cURL command
- **Color-coded** — method badges (GET green, POST blue, etc.) and status code colors
- **Clean exit** — auto-cleans database on shutdown, fresh start every time

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Start the proxy
python ezproxy.py

# 3. Configure your browser proxy → localhost:8080
# 4. Open http://localhost:5000 to view traffic
```

## HTTPS Setup

To intercept HTTPS traffic, install mitmproxy's CA certificate:

### Windows (Chrome / Edge)
```powershell
certutil -addstore Root %USERPROFILE%\.mitmproxy\mitmproxy-ca-cert.cer
```

### Firefox
1. Settings → Privacy & Security → Certificates → View Certificates
2. Import `~/.mitmproxy/mitmproxy-ca-cert.pem`
3. Check "Trust this CA to identify websites"

### macOS
```bash
sudo security add-trusted-cert -d -p ssl -k /Library/Keychains/System.keychain ~/.mitmproxy/mitmproxy-ca-cert.pem
```

## CLI Options

```
python ezproxy.py [options]

Options:
  -p, --proxy-port   Proxy port (default: 8080)
  -w, --web-port     Web UI port (default: 5000)
  --db               Custom SQLite database path (default: ~/.ezproxy/flows.db)
  -V, --version      Show version
```

## Web UI Overview

```
┌─ Toolbar ──────────────────────────────────────────────────────────┐
│ 🔍 EzProxy  [filter URL...] [GET▼] [2xx▼] [target host] [🎯] ...  │
├─ Traffic Table ────────────────────────────────────────────────────┤
│ ▶ 🖥 example.com 🎯                   请求数量: 5                  │
│ ▶ 🖥 cdn.example.com                   请求数量: 12                │
│   (collapsed by default — click to expand)                         │
├─ Detail Panel ─────────────────────────────────────────────────────┤
│ [Request] [Response]                                               │
│ GET /api/users HTTP/1.1                                            │
│ Host: example.com                                                  │
│ ...                                                                │
└────────────────────────────────────────────────────────────────────┘
```

- Click a **host group** to expand/collapse its requests
- Click **🎯** next to a host to focus on that site (hides all third-party requests)
- Click a **request row** to view full headers + body
- Press **Esc** to close the detail panel

## Project Structure

```
Ezproxy/
├── ezproxy.py               # CLI entry point
├── requirements.txt          # mitmproxy, flask, rich
└── ezproxy/
    ├── __init__.py
    ├── db.py                 # SQLite storage (WAL mode, thread-safe)
    ├── addon.py              # mitmproxy addon (flow capture)
    ├── web.py                # Flask JSON API
    └── templates/
        └── index.html        # Single-page web UI
```

## How It Works

1. `ezproxy.py` starts **mitmproxy** (proxy engine) and **Flask** (web viewer) in parallel
2. Browser sends requests through `localhost:8080` → mitmproxy intercepts them
3. `EzProxyAddon` captures every request/response pair → writes to SQLite
4. Web UI polls the Flask API every 3 seconds → displays grouped traffic

## License

MIT
