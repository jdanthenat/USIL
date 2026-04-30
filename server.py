#!/usr/bin/env python3
"""
server.py — USIL Web Dashboard Server

Serves the dashboard HTML and exposes SQLite data as JSON API.
No external dependencies beyond Python stdlib + your existing usil/ package.

Endpoints:
    GET /              → dashboard.html
    GET /api/stats     → ledger stats JSON
    GET /api/commitments → recent commitments JSON
    GET /api/mints     → mint ledger JSON
    GET /api/attacks   → attack log JSON
    GET /api/live      → single combined payload for dashboard polling

Usage:
    python server.py           (starts on http://localhost:8765)
    python server.py --port 9000
"""

import sys
import os
import json
import time
import argparse
import threading
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse

# Add usil package to path
sys.path.insert(0, os.path.dirname(__file__))

# Lazy import — only fails if simulation hasn't been run yet
def get_ledger():
    try:
        from usil import ledger
        return ledger
    except ImportError:
        return None


def build_live_payload() -> dict:
    """Combine all ledger data into one JSON payload for dashboard polling."""
    ledger = get_ledger()
    if ledger is None:
        return {"error": "usil module not found", "ts": time.time()}

    # Init DB if not yet initialized
    try:
        ledger.init_db()
    except Exception:
        pass

    try:
        stats       = ledger.get_stats()
        commitments = ledger.get_all_commitments(limit=20)
        mints       = ledger.get_all_mints(limit=10)
        attacks     = ledger.get_attack_log(limit=10)

        # Compute pipeline stage counts
        by_status = stats.get("by_status", {})

        return {
            "ts":           time.time(),
            "stats":        stats,
            "commitments":  commitments,
            "mints":        mints,
            "attacks":      attacks,
            "pipeline": {
                "ghost":    by_status.get("GHOST", 0),
                "shadow":   by_status.get("SHADOW", 0),
                "verified": by_status.get("VERIFIED", 0),
                "live":     by_status.get("LIVE", 0),
                "invalid":  by_status.get("INVALID", 0),
                "expired":  by_status.get("EXPIRED", 0),
            }
        }
    except Exception as e:
        return {"error": str(e), "ts": time.time()}


# ── Serve dashboard HTML ───────────────────────────────────────────────────────
DASHBOARD_PATH = os.path.join(os.path.dirname(__file__), "dashboard.html")


class USILHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # Suppress default request logging

    def send_json(self, data: dict, status: int = 200):
        body = json.dumps(data, default=str).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def send_html(self, path: str):
        try:
            with open(path, "rb") as f:
                body = f.read()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except FileNotFoundError:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"dashboard.html not found")

    def do_GET(self):
        parsed = urlparse(self.path)
        path   = parsed.path.rstrip("/")

        if path in ("", "/"):
            self.send_html(DASHBOARD_PATH)

        elif path == "/api/live":
            self.send_json(build_live_payload())

        elif path == "/api/stats":
            ledger = get_ledger()
            ledger.init_db()
            self.send_json(ledger.get_stats())

        elif path == "/api/commitments":
            ledger = get_ledger()
            ledger.init_db()
            self.send_json({"commitments": ledger.get_all_commitments()})

        elif path == "/api/mints":
            ledger = get_ledger()
            ledger.init_db()
            self.send_json({"mints": ledger.get_all_mints()})

        elif path == "/api/attacks":
            ledger = get_ledger()
            ledger.init_db()
            self.send_json({"attacks": ledger.get_attack_log()})

        else:
            self.send_response(404)
            self.end_headers()


def run_server(port: int = 8765, open_browser: bool = True):
    server = HTTPServer(("localhost", port), USILHandler)
    url    = f"http://localhost:{port}"
    print(f"\n  USIL Dashboard → {url}")
    print(f"  API endpoint  → {url}/api/live")
    print(f"  Press Ctrl+C to stop\n")

    if open_browser:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n  Server stopped.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="USIL Dashboard Server")
    parser.add_argument("--port",       type=int, default=8765)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()
    run_server(port=args.port, open_browser=not args.no_browser)
