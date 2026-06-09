#!/usr/bin/env python3
"""EzProxy — Lightweight Burp Suite-like HTTP proxy recorder.

Launches a mitmproxy instance that captures every HTTP request/response
and a companion web UI for browsing the recorded traffic.

Usage:
    python ezproxy.py [--proxy-port 8080] [--web-port 5000]

Then configure your browser to use localhost:<proxy-port> as the HTTP/HTTPS proxy
and open http://localhost:<web-port> to view captured traffic.
"""

import argparse
import asyncio
import logging
import sys
import threading

# Force UTF-8 output on Windows to avoid Rich encoding issues
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Suppress noisy startup logs
logging.getLogger("mitmproxy").setLevel(logging.WARNING)
logging.getLogger("werkzeug").setLevel(logging.WARNING)
# Suppress asyncio "connection reset" noise (normal when clients disconnect abruptly)
logging.getLogger("asyncio").setLevel(logging.CRITICAL)

from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from ezproxy.db import FlowDB, DEFAULT_DB_PATH
from ezproxy.addon import EzProxyAddon

console = Console()


def main() -> None:
    args = _parse_args()

    # ------------------------------------------------------------------
    # Database
    # ------------------------------------------------------------------
    db_path = args.db or str(DEFAULT_DB_PATH)
    db = FlowDB(db_path)

    # ------------------------------------------------------------------
    # Print banner
    # ------------------------------------------------------------------
    console.print()
    console.print(
        Panel.fit(
            "[bold bright_blue]EzProxy[/] — HTTP Traffic Recorder",
            subtitle=f"v{__import__('ezproxy').__version__}",
        )
    )

    table = Table(show_header=False, box=None, padding=(0, 4))
    table.add_column("Key", style="dim")
    table.add_column("Value", style="bright_white")
    table.add_row("Proxy (HTTP/HTTPS)", f"[bold green]localhost:{args.proxy_port}[/]")
    table.add_row("Web UI", f"[bold cyan]http://localhost:{args.web_port}[/]")
    table.add_row("Database", db_path)
    console.print(table)
    console.print()

    # ------------------------------------------------------------------
    # Start web viewer in a daemon thread
    # ------------------------------------------------------------------
    from ezproxy.web import create_app

    app = create_app(db)

    web_thread = threading.Thread(
        target=lambda: app.run(
            host="127.0.0.1",
            port=args.web_port,
            debug=False,
            use_reloader=False,
        ),
        daemon=True,
    )
    web_thread.start()

    # ------------------------------------------------------------------
    # Start mitmproxy via asyncio
    # ------------------------------------------------------------------
    console.print("  [dim]Starting proxy engine...[/]")

    console.print(
        "  [green]✓[/] Proxy ready. "
        "[dim](Configure browser → proxy [bold]localhost:{0}[/])[/]".format(
            args.proxy_port
        )
    )
    console.print(
        "  [green]✓[/] Web UI ready. "
        "[dim](Open [bold]http://localhost:{0}[/])[/]".format(args.web_port)
    )
    console.print()
    console.print("[dim]Press Ctrl+C to stop.[/]")
    console.print()

    try:
        asyncio.run(_run_proxy(args, db))
    except KeyboardInterrupt:
        console.print()
    finally:
        # Clean up: delete all recorded flows on exit
        count = db.delete_all_flows()
        if count:
            console.print(f"[dim]Cleaned up {count} recorded flow(s).[/]")
        console.print("[dim]Proxy stopped.[/]")


async def _run_proxy(args, db: FlowDB) -> None:
    """Async entry point for mitmproxy's DumpMaster."""
    import asyncio as _asyncio

    def _exception_handler(loop, context):
        """Suppress noisy ConnectionResetError — normal when clients disconnect."""
        exc = context.get("exception")
        if isinstance(exc, ConnectionResetError):
            return  # silently ignore
        loop.default_exception_handler(context)

    _asyncio.get_running_loop().set_exception_handler(_exception_handler)

    from mitmproxy.options import Options
    from mitmproxy.tools.dump import DumpMaster

    opts = Options()
    opts.listen_host = "0.0.0.0"
    opts.listen_port = args.proxy_port
    opts.ssl_insecure = True  # allow self-signed upstream certs

    master = DumpMaster(opts)
    master.addons.add(EzProxyAddon(db))

    # DumpMaster.run() handles the event loop internally
    await master.run()


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="EzProxy — lightweight HTTP proxy recorder.",
    )
    p.add_argument(
        "--proxy-port", "-p",
        type=int, default=8080,
        help="Port for the HTTP/HTTPS proxy (default: 8080)",
    )
    p.add_argument(
        "--web-port", "-w",
        type=int, default=5000,
        help="Port for the web viewer UI (default: 5000)",
    )
    p.add_argument(
        "--db",
        type=str, default=None,
        help="Path to SQLite database file (default: ~/.ezproxy/flows.db)",
    )
    p.add_argument(
        "--version", "-V",
        action="version",
        version=f"EzProxy {__import__('ezproxy').__version__}",
    )
    return p.parse_args()


if __name__ == "__main__":
    main()
