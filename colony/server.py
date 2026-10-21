"""Read-only local Observatory server. Worker mutations use the Store, never HTTP."""

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import mimetypes
from pathlib import Path
from urllib.parse import unquote, urlsplit


ASSET_SUFFIXES = {".html", ".css", ".js", ".json", ".svg", ".png", ".ico", ".webp", ".jpg", ".jpeg", ".woff", ".woff2", ".txt"}


def make_server(store, host="127.0.0.1", port=8765, static_dir="observatory/dist", project=None):
    """Return a server; callers own serve_forever()/shutdown()/server_close()."""
    root = Path(static_dir).resolve()

    class Handler(BaseHTTPRequestHandler):
        server_version = "QEDColony/0.1"
        sys_version = ""

        def log_message(self, fmt, *args):
            # Keep regular access logging, without Python's default reverse DNS lookup.
            super().log_message(fmt, *args)

        def _respond(self, status, body, content_type="text/plain; charset=utf-8", cache="no-store"):
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", cache)
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("X-Frame-Options", "DENY")
            self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; object-src 'none'")
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(body)

        def do_HEAD(self):
            self.do_GET()

        def do_GET(self):
            try:
                path = unquote(urlsplit(self.path).path, errors="strict")
            except (UnicodeError, ValueError):
                self._respond(400, b"Invalid request path\n")
                return
            if path == "/api/state":
                try:
                    body = json.dumps(store.snapshot(project=project), ensure_ascii=False, allow_nan=False).encode("utf-8")
                except Exception:
                    # Details remain local; do not disclose filesystem paths or SQL over HTTP.
                    self._respond(503, b"State unavailable\n")
                    return
                self._respond(200, body, "application/json; charset=utf-8")
                return
            if path.startswith("/api/"):
                self._respond(404, b"Unknown API endpoint\n")
                return
            parts = Path(path.lstrip("/")).parts
            if "\x00" in path or "\\" in path or any(part == ".." or part.startswith(".") for part in parts):
                self._respond(403, b"Forbidden\n")
                return
            candidate = root.joinpath(*parts)
            if path.endswith("/") or candidate.is_dir():
                candidate = candidate / "index.html"
            try:
                candidate = candidate.resolve()
                candidate.relative_to(root)
            except (ValueError, OSError, RuntimeError):
                self._respond(403, b"Forbidden\n")
                return
            if candidate.suffix.lower() not in ASSET_SUFFIXES or not candidate.is_file():
                self._respond(404, b"Not found\n")
                return
            try:
                body = candidate.read_bytes()
            except OSError:
                self._respond(404, b"Not found\n")
                return
            content_type = mimetypes.guess_type(str(candidate))[0] or "application/octet-stream"
            if content_type.startswith("text/") or candidate.suffix in {".js", ".json", ".svg"}:
                content_type += "; charset=utf-8"
            self._respond(200, body, content_type, "no-cache")

        def _method_not_allowed(self):
            self._respond(405, b"Read-only server; use the local CLI for mutations\n")

        do_POST = _method_not_allowed
        do_PUT = _method_not_allowed
        do_PATCH = _method_not_allowed
        do_DELETE = _method_not_allowed

    server = ThreadingHTTPServer((host, port), Handler)
    server.daemon_threads = True
    return server
