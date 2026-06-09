"""SQLite storage layer for captured HTTP flows.

Uses WAL journal mode for concurrent read/write access from the
mitmproxy addon (writer) and Flask web viewer (reader).
"""

import base64
import json
import sqlite3
import threading
import time
from pathlib import Path

DEFAULT_DB_PATH = Path.home() / ".ezproxy" / "flows.db"

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS flows (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp     REAL    NOT NULL,
    method        TEXT    NOT NULL,
    url           TEXT    NOT NULL,
    host          TEXT    NOT NULL,
    path          TEXT    NOT NULL,
    status_code   INTEGER,
    request_headers  TEXT,
    response_headers TEXT,
    request_body    BLOB,
    response_body   BLOB,
    content_type    TEXT,
    response_length INTEGER,
    duration_ms     REAL,
    comment         TEXT,
    highlight       TEXT DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_flows_timestamp ON flows(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_flows_host      ON flows(host);
CREATE INDEX IF NOT EXISTS idx_flows_method    ON flows(method);
CREATE INDEX IF NOT EXISTS idx_flows_status    ON flows(status_code);
"""


class FlowDB:
    """Thread-safe SQLite database for HTTP flow storage."""

    def __init__(self, db_path: str | Path | None = None):
        self._db_path = str(db_path or DEFAULT_DB_PATH)
        self._local = threading.local()
        Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    # -- connection management ------------------------------------------------

    @property
    def _conn(self) -> sqlite3.Connection:
        """Per-thread connection (SQLite requires same-thread usage)."""
        if not hasattr(self._local, "conn") or self._local.conn is None:
            self._local.conn = sqlite3.connect(self._db_path)
            self._local.conn.row_factory = sqlite3.Row
            self._local.conn.execute("PRAGMA journal_mode=WAL")
            self._local.conn.execute("PRAGMA foreign_keys=ON")
        return self._local.conn

    def _init_db(self) -> None:
        conn = sqlite3.connect(self._db_path)
        try:
            conn.executescript(_SCHEMA_SQL)
            conn.commit()
        finally:
            conn.close()

    # -- write operations -----------------------------------------------------

    def insert_flow(
        self,
        *,
        timestamp: float | None = None,
        method: str,
        url: str,
        host: str,
        path: str,
        status_code: int | None = None,
        request_headers: dict | None = None,
        response_headers: dict | None = None,
        request_body: bytes | None = None,
        response_body: bytes | None = None,
        content_type: str | None = None,
        response_length: int | None = None,
        duration_ms: float | None = None,
    ) -> int:
        """Insert a captured flow and return its row id."""
        if timestamp is None:
            timestamp = time.time()

        conn = self._conn
        cur = conn.execute(
            """INSERT INTO flows
               (timestamp, method, url, host, path, status_code,
                request_headers, response_headers,
                request_body, response_body,
                content_type, response_length, duration_ms)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                timestamp,
                method,
                url,
                host,
                path,
                status_code,
                json.dumps(request_headers) if request_headers else None,
                json.dumps(response_headers) if response_headers else None,
                request_body,
                response_body,
                content_type,
                response_length,
                duration_ms,
            ),
        )
        conn.commit()
        return cur.lastrowid

    # -- read operations ------------------------------------------------------

    def get_flows(
        self,
        *,
        limit: int = 200,
        offset: int = 0,
        search: str | None = None,
        method: str | None = None,
        status_code: int | None = None,
        host: str | None = None,
    ) -> list[dict]:
        """Return recent flows with optional filters."""
        conditions = []
        params: list = []

        if search:
            conditions.append("(url LIKE ? OR host LIKE ?)")
            params.extend((f"%{search}%", f"%{search}%"))
        if method:
            conditions.append("method = ?")
            params.append(method.upper())
        if status_code is not None:
            conditions.append("status_code = ?")
            params.append(status_code)
        if host:
            conditions.append("host LIKE ?")
            params.append(f"%{host}%")

        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        conn = self._conn
        cur = conn.execute(
            f"""SELECT id, timestamp, method, url, host, path,
                       status_code, content_type, response_length,
                       duration_ms, comment, highlight
                FROM flows
                {where}
                ORDER BY timestamp DESC
                LIMIT ? OFFSET ?""",
            (*params, limit, offset),
        )
        return [self._row_to_dict(r, detail=False) for r in cur.fetchall()]

    def count_flows(
        self,
        *,
        search: str | None = None,
        method: str | None = None,
        status_code: int | None = None,
        host: str | None = None,
    ) -> int:
        """Count flows matching filters."""
        conditions = []
        params: list = []

        if search:
            conditions.append("(url LIKE ? OR host LIKE ?)")
            params.extend((f"%{search}%", f"%{search}%"))
        if method:
            conditions.append("method = ?")
            params.append(method.upper())
        if status_code is not None:
            conditions.append("status_code = ?")
            params.append(status_code)
        if host:
            conditions.append("host LIKE ?")
            params.append(f"%{host}%")

        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        conn = self._conn
        cur = conn.execute(f"SELECT COUNT(*) FROM flows {where}", params)
        return cur.fetchone()[0]

    def get_flow_by_id(self, flow_id: int) -> dict | None:
        """Return a single flow including full headers and bodies."""
        conn = self._conn
        cur = conn.execute(
            "SELECT * FROM flows WHERE id = ?", (flow_id,)
        )
        row = cur.fetchone()
        if row is None:
            return None
        return self._row_to_dict(row, detail=True)

    def delete_flow(self, flow_id: int) -> bool:
        """Delete a single flow by id. Returns True if deleted."""
        conn = self._conn
        cur = conn.execute("DELETE FROM flows WHERE id = ?", (flow_id,))
        conn.commit()
        return cur.rowcount > 0

    def delete_all_flows(self) -> int:
        """Delete all flows and reset the ID counter. Returns count of deleted rows."""
        conn = self._conn
        cur = conn.execute("DELETE FROM flows")
        conn.execute("DELETE FROM sqlite_sequence WHERE name='flows'")
        conn.commit()
        return cur.rowcount

    # -- helpers --------------------------------------------------------------

    @staticmethod
    def _row_to_dict(row: sqlite3.Row, *, detail: bool = False) -> dict:
        d = dict(row)
        if detail:
            # Parse JSON header fields
            for field in ("request_headers", "response_headers"):
                if d.get(field):
                    try:
                        d[field] = json.loads(d[field])
                    except (json.JSONDecodeError, TypeError):
                        d[field] = {}
            # Decode body bytes to string; fall back to base64 for binary
            for field in ("request_body", "response_body"):
                val = d.get(field)
                if isinstance(val, bytes):
                    if val:
                        try:
                            d[field] = val.decode("utf-8")
                        except (UnicodeDecodeError, Exception):
                            # Binary content (images, fonts, etc.) — encode as base64
                            d[field] = "[binary: " + base64.b64encode(val).decode("ascii") + "]"
                    else:
                        d[field] = ""
        else:
            # Strip heavy fields from list view
            for field in ("request_headers", "response_headers",
                          "request_body", "response_body"):
                d.pop(field, None)

        # Final safety net: ensure no raw bytes remain in the dict
        return _sanitize_bytes(d)


def _sanitize_bytes(obj):
    """Recursively convert any bytes values in obj to strings."""
    if isinstance(obj, bytes):
        try:
            return obj.decode("utf-8")
        except Exception:
            return "[binary data]"
    if isinstance(obj, dict):
        return {k: _sanitize_bytes(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_sanitize_bytes(v) for v in obj]
    return obj
