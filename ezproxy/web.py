"""Flask web viewer for browsing captured HTTP traffic.

Provides a JSON API consumed by the single-page frontend,
plus serves the main UI page.
"""

import json
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory

from .db import FlowDB

TEMPLATES_DIR = Path(__file__).parent / "templates"


def create_app(db: FlowDB) -> Flask:
    """Build and configure the Flask application."""
    app = Flask(
        __name__,
        static_folder=None,  # no static files needed
    )

    # ------------------------------------------------------------------
    # Page routes
    # ------------------------------------------------------------------

    @app.route("/")
    def index():
        """Serve the single-page web UI."""
        return send_from_directory(str(TEMPLATES_DIR), "index.html")

    # ------------------------------------------------------------------
    # JSON API routes
    # ------------------------------------------------------------------

    @app.route("/api/flows", methods=["GET"])
    def api_list_flows():
        """List flows with pagination and optional filters.

        Query params:
            limit   (int, default 200)
            offset  (int, default 0)
            search  (str)  — free-text search in URL / host
            method  (str)  — exact HTTP method filter
            status  (int)  — exact status code filter
            host    (str)  — substring match on host
        """
        params = {
            "limit": request.args.get("limit", 200, type=int),
            "offset": request.args.get("offset", 0, type=int),
            "search": request.args.get("search"),
            "method": request.args.get("method"),
            "status_code": request.args.get("status", type=int),
            "host": request.args.get("host"),
        }
        flows = db.get_flows(**params)
        total = db.count_flows(
            search=params["search"],
            method=params["method"],
            status_code=params["status_code"],
            host=params["host"],
        )
        return jsonify({"flows": flows, "total": total})

    @app.route("/api/flows/<int:flow_id>", methods=["GET"])
    def api_get_flow(flow_id: int):
        """Get a single flow with full request/response detail."""
        flow = db.get_flow_by_id(flow_id)
        if flow is None:
            return jsonify({"error": "Flow not found"}), 404
        return jsonify(flow)

    @app.route("/api/flows/<int:flow_id>", methods=["DELETE"])
    def api_delete_flow(flow_id: int):
        """Delete a single flow."""
        ok = db.delete_flow(flow_id)
        if not ok:
            return jsonify({"error": "Flow not found"}), 404
        return jsonify({"deleted": True})

    @app.route("/api/flows", methods=["DELETE"])
    def api_delete_all_flows():
        """Delete all captured flows."""
        count = db.delete_all_flows()
        return jsonify({"deleted": count})

    @app.route("/api/flows/<int:flow_id>/curl", methods=["GET"])
    def api_flow_as_curl(flow_id: int):
        """Return a single request as a cURL command string."""
        flow = db.get_flow_by_id(flow_id)
        if flow is None:
            return jsonify({"error": "Flow not found"}), 404
        return jsonify({"curl": _build_curl(flow)})

    @app.route("/api/stats", methods=["GET"])
    def api_stats():
        """Quick summary: total flows, unique hosts, methods used."""
        total = db.count_flows()
        return jsonify({"total_flows": total})

    return app


# -- cURL builder ------------------------------------------------------------

def _build_curl(flow: dict) -> str:
    """Build a cURL command string from a stored flow."""
    method = flow.get("method", "GET")
    url = flow.get("url", "")

    parts = ["curl", "-X", method]

    headers = flow.get("request_headers")
    if isinstance(headers, dict):
        for key, val in headers.items():
            # Skip the Host header (cURL handles it)
            if key.lower() == "host":
                continue
            parts.extend(["-H", f"{key}: {val}"])

    body = flow.get("request_body")
    if body and method in ("POST", "PUT", "PATCH", "DELETE"):
        # Try to present body cleanly
        if isinstance(body, bytes):
            try:
                body = body.decode("utf-8")
            except UnicodeDecodeError:
                body = "[binary data]"
        if isinstance(body, str) and body:
            parts.extend(["-d", json.dumps(body) if _is_json(headers) else body])

    parts.append(json.dumps(url))
    return " ".join(parts)


def _is_json(headers: dict | None) -> bool:
    if not headers:
        return False
    ct = headers.get("Content-Type", headers.get("content-type", ""))
    return "json" in ct.lower()
