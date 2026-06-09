"""mitmproxy addon that captures HTTP flows into SQLite.

Hooks into mitmproxy's request/response lifecycle to record every completed
HTTP transaction with full headers, body, timing, and metadata.
"""

import time
import urllib.parse

from mitmproxy import http

from .db import FlowDB

# Flows whose request has started but not yet received a response.
# Keyed by flow.id (thread-safe string assigned by mitmproxy).
_pending: dict[str, float] = {}


class EzProxyAddon:
    """Captures every HTTP request/response pair and stores them in SQLite."""

    def __init__(self, db: FlowDB):
        self.db = db

    # -- mitmproxy hooks -----------------------------------------------------

    def request(self, flow: http.HTTPFlow) -> None:
        """Record the start time when a request is received."""
        if flow.request:
            _pending[flow.id] = time.time()

    def response(self, flow: http.HTTPFlow) -> None:
        """When a complete response arrives, persist the full transaction."""
        start = _pending.pop(flow.id, None)
        duration_ms = (
            (time.time() - start) * 1000 if start else None
        )

        req = flow.request
        resp = flow.response

        if req is None:
            return

        # Parse URL components
        try:
            parsed = urllib.parse.urlparse(req.pretty_url)
        except Exception:
            parsed = urllib.parse.urlparse(req.url)

        host = parsed.hostname or req.host or ""
        path = parsed.path or "/"
        if parsed.query:
            path = f"{path}?{parsed.query}"

        # Convert headers to plain dicts (multi-value → first value for brevity)
        req_headers = {k: v for k, v in req.headers.items(multi=True)} if req.headers else None
        resp_headers = {k: v for k, v in resp.headers.items(multi=True)} if resp else None

        self.db.insert_flow(
            timestamp=time.time(),
            method=req.method,
            url=req.pretty_url,
            host=host,
            path=path,
            status_code=resp.status_code if resp else None,
            request_headers=req_headers,
            response_headers=resp_headers,
            request_body=req.content or None,
            response_body=resp.content if resp else None,
            content_type=resp.headers.get("content-type", "") if resp else "",
            response_length=len(resp.content) if resp and resp.content else 0,
            duration_ms=duration_ms,
        )

    def done(self):
        """Cleanup called when mitmproxy shuts down."""
        _pending.clear()
