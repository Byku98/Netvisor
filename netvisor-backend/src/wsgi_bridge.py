"""Minimal ASGI → WSGI bridge for Passenger/lswsgi deployments.

a2wsgi's ASGIMiddleware deadlocks with LiteSpeed's lswsgi handler, so we
ship our own tiny bridge. Plain HTTP request/response only (no websockets,
no streaming requests) — exactly what the NetVisor API uses.

Usage (passenger_wsgi.py):
    from src.wsgi_bridge import asgi_to_wsgi
    from src.api.main import app
    application = asgi_to_wsgi(app)

How it works:
  - Runs a private asyncio event loop in a dedicated thread.
  - Each WSGI request builds an ASGI scope, submits the app coroutine to the
    loop, and pumps receive() events (http.request body) synchronously.
  - Collects response start (status/headers) + body chunks, then feeds them
    to start_response/write in WSGI order.
"""

import asyncio
import sys
import threading
from urllib.parse import unquote

from src.logging import get_logger

log = get_logger("wsgi_bridge")

_BODY_CHUNK = {"type": "http.request", "body": b"", "more_body": False}
_DISCONNECT = {"type": "http.disconnect"}


class _Bridge:
    """Runs ASGI apps on a private event loop thread.

    Loop/thread are created LAZILY on first request — Passenger/lswsgi may
    import the app in a master process and fork workers; threads do not
    survive fork(), so each worker must start its own loop on first use.
    """

    def __init__(self, app):
        self.app = app
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()

    def _ensure_loop(self):
        with self._lock:
            thread_alive = self._thread is not None and self._thread.is_alive()
            if self._loop is None or self._loop.is_closed() or not thread_alive:
                log.info("bridge: starting event loop thread (pid %s)", threading.get_ident())
                self._loop = asyncio.new_event_loop()
                self._thread = threading.Thread(target=self._loop.run_forever, daemon=True)
                self._thread.start()

    def run(self, scope, body: bytes):
        """Run one ASGI request on the loop thread; return (status, headers, body)."""
        self._ensure_loop()
        fut = asyncio.run_coroutine_threadsafe(
            self._run_app(scope, body), self._loop
        )
        return fut.result(timeout=120)

    async def _run_app(self, scope, body: bytes):
        log.info(
            "bridge: scope headers=%s method=%s path=%s root=%s bodylen=%s",
            scope.get("headers"), scope.get("method"), scope.get("path"),
            scope.get("root_path"), len(body),
        )
        state = {"status": None, "headers": [], "body": bytearray()}
        sent_first = asyncio.Event()
        done = asyncio.Event()

        async def receive():
            # Single-shot request bodies: hand over the buffered body once,
            # then disconnect.
            if scope.get("_body_sent"):
                await done.wait()
                return _DISCONNECT
            scope["_body_sent"] = True
            return {"type": "http.request", "body": body, "more_body": False}

        async def send(message):
            if message["type"] == "http.response.start":
                state["status"] = message["status"]
                state["headers"] = list(message.get("headers", []))
                sent_first.set()
            elif message["type"] == "http.response.body":
                state["body"] += message.get("body", b"")
                if not message.get("more_body", False):
                    done.set()
            elif message["type"] == "http.disconnect":
                done.set()

        try:
            await self.app(scope, receive, send)
        finally:
            done.set()
            sent_first.set()

        await done.wait()
        return state["status"], state["headers"], bytes(state["body"])


def asgi_to_wsgi(app):
    """Convert an ASGI app into a WSGI callable."""
    bridge = _Bridge(app)

    def application(environ, start_response):
        # Build ASGI scope from the WSGI environ
        script_name = environ.get("SCRIPT_NAME", "")
        path = environ.get("PATH_INFO", "") or "/"
        server = environ.get("SERVER_NAME", "localhost")
        port = environ.get("SERVER_PORT", "80")
        scope = {
            "type": "http",
            "asgi": {"version": "3.0", "spec_version": "2.1"},
            "http_version": environ.get("SERVER_PROTOCOL", "HTTP/1.1").split("/")[-1],
            "method": environ.get("REQUEST_METHOD", "GET").upper(),
            "scheme": environ.get("wsgi.url_scheme", "http"),
            "path": unquote(path),
            "raw_path": path.encode("utf-8"),
            "query_string": environ.get("QUERY_STRING", "").encode("utf-8"),
            "root_path": script_name,
            "server": (server, int(port)),
            "client": (
                environ.get("REMOTE_ADDR", "127.0.0.1"),
                int(environ.get("REMOTE_PORT", 0) or 0),
            ),
            "headers": [
                (k.lower().encode("latin-1"), v.encode("latin-1"))
                for k, v in environ.items()
                if k.startswith("HTTP_")
            ]
            + (
                [(b"content-type", environ["CONTENT_TYPE"].encode("latin-1"))]
                if environ.get("CONTENT_TYPE")
                else []
            )
            + (
                [(b"content-length", environ["CONTENT_LENGTH"].encode("latin-1"))]
                if environ.get("CONTENT_LENGTH")
                else []
            ),
        }

        # Read the request body (uploads!) — chunked read: some WSGI servers
        # (lswsgi) return partial reads from a single read() call.
        body = b""
        try:
            length = int(environ.get("CONTENT_LENGTH") or 0)
        except ValueError:
            length = 0
        if length:
            stream = environ["wsgi.input"]
            while len(body) < length:
                chunk = stream.read(min(65536, length - len(body)))
                if not chunk:
                    log.warning(
                        "bridge: body short-read (%d/%d bytes) for %s %s",
                        len(body), length, environ.get("REQUEST_METHOD"), path,
                    )
                    break
                body += chunk
        log.info(
            "bridge: %s %s | ct=%s | clen=%s | body=%d bytes",
            environ.get("REQUEST_METHOD"), path,
            environ.get("CONTENT_TYPE", "-"), environ.get("CONTENT_LENGTH", "-"), len(body),
        )

        try:
            status, headers, resp_body = bridge.run(scope, body)
            if status is None:
                # App finished without sending http.response.start
                log.error("bridge: app produced no response start (status=None)")
                status, headers, resp_body = 500, [(b"content-type", b"text/plain")], b"Internal Server Error (bridge: no response start)"
        except Exception:
            # stderr is a broken pipe under lswsgi — log to the file handler instead
            log.exception("bridge: request failed (%s %s)", environ.get("REQUEST_METHOD"), path)
            status, headers, resp_body = 500, [(b"content-type", b"text/plain")], b"Internal Server Error (bridge)"

        reason = {
            200: "OK", 201: "Created", 204: "No Content", 301: "Moved Permanently",
            302: "Found", 304: "Not Modified", 400: "Bad Request", 401: "Unauthorized",
            403: "Forbidden", 404: "Not Found", 409: "Conflict", 410: "Gone",
            413: "Payload Too Large", 422: "Unprocessable Entity", 429: "Too Many Requests",
            500: "Internal Server Error", 502: "Bad Gateway", 503: "Service Unavailable",
            504: "Gateway Timeout",
        }.get(status, "OK")

        out_headers = [(k.decode("latin-1"), v.decode("latin-1")) for k, v in headers]
        # Ensure content-length so lswsgi doesn't buffer forever
        names = {k.lower() for k, _ in out_headers}
        if "content-length" not in names:
            out_headers.append(("Content-Length", str(len(resp_body))))

        start_response(f"{status} {reason}", out_headers)
        return [resp_body]

    return application
