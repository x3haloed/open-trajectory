from __future__ import annotations

import http.client
import json
import re
import ssl
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

import certifi


UPSTREAM_HOST = "chatgpt.com"
UPSTREAM_PORT = 443
ALLOWED_PATH_PREFIX = "/backend-api/"
RECEIPT_KINDS = {
    "effective_model",
    "models_etag",
    "response_id",
    "upstream_request_id",
}
HOP_BY_HOP_HEADERS = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "proxy-connection",
    "te",
    "trailer",
    "transfer-encoding",
    "upgrade",
}


class DeploymentProxyError(RuntimeError):
    pass


class DeploymentReceiptCollector:
    """Retain only allowlisted hosted-deployment identity fields in memory."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._receipts: list[dict[str, str]] = []
        self._errors: list[str] = []
        self._request_kinds: list[str] = []
        self._request_methods: list[str] = []
        self._request_shapes: list[str] = []
        self._response_shapes: list[dict[str, Any]] = []
        self._sse_data_lines = 0

    def record(self, kind: str, value: Any) -> None:
        if (
            kind not in RECEIPT_KINDS
            or not isinstance(value, str)
            or not 1 <= len(value) <= 1024
        ):
            self.record_error("receipt failed its allowlist schema")
            return
        with self._lock:
            self._receipts.append({"kind": kind, "value": value})

    def record_headers(self, headers: http.client.HTTPMessage) -> None:
        for name, kind in (
            ("x-models-etag", "models_etag"),
            ("openai-model", "effective_model"),
            ("x-request-id", "upstream_request_id"),
        ):
            value = headers.get(name)
            if value is not None:
                self.record(kind, value)

    def feed_sse_line(self, line: bytes) -> None:
        if not line.startswith(b"data:"):
            return
        with self._lock:
            self._sse_data_lines += 1
        encoded = line[5:].strip()
        if not encoded or encoded == b"[DONE]":
            return
        try:
            event = json.loads(encoded)
        except (UnicodeDecodeError, json.JSONDecodeError):
            self.record_error("response stream contained malformed JSON data")
            return
        if not isinstance(event, dict):
            return
        response = event.get("response")
        if isinstance(response, dict):
            if isinstance(response.get("model"), str):
                self.record("effective_model", response["model"])
            if isinstance(response.get("id"), str):
                self.record("response_id", response["id"])
        if isinstance(event.get("response_id"), str):
            self.record("response_id", event["response_id"])

    def record_error(self, message: str) -> None:
        with self._lock:
            self._errors.append(message)

    def record_request(self, method: str, path: str) -> str:
        normalized = path.split("?", 1)[0].rstrip("/")
        if normalized.endswith("/responses"):
            kind = "responses"
        elif normalized.endswith("/models"):
            kind = "models"
        elif "/responses/" in normalized:
            kind = "responses-adjacent"
        else:
            kind = "other"
        segments = []
        for segment in normalized.split("/"):
            if not segment:
                continue
            safe = re.fullmatch(r"[a-z][a-z0-9_-]{0,31}", segment)
            segments.append(segment if safe else "<opaque>")
        with self._lock:
            self._request_kinds.append(kind)
            self._request_methods.append(method)
            self._request_shapes.append("/" + "/".join(segments))
        return kind

    def record_response_shape(
        self,
        request_kind: str,
        status: int,
        content_type: str,
        content_encoding: str,
    ) -> None:
        mime = content_type.split(";", 1)[0].strip()
        if not re.fullmatch(r"[a-z0-9.+-]+/[a-z0-9.+-]+", mime):
            mime = "<other>"
        if "text/event-stream" in content_type:
            kind = "event-stream"
        elif "json" in content_type:
            kind = "json"
        else:
            kind = "other"
        with self._lock:
            self._response_shapes.append(
                {
                    "status": status,
                    "request_kind": request_kind,
                    "kind": kind,
                    "mime": mime,
                    "encoded": content_encoding not in {"", "identity"},
                }
            )

    def snapshot(self) -> list[dict[str, str]]:
        with self._lock:
            return [dict(item) for item in self._receipts]

    def errors(self) -> list[str]:
        with self._lock:
            return list(self._errors)

    def request_count(self) -> int:
        with self._lock:
            return len(self._request_kinds)

    def diagnostics(self) -> dict[str, Any]:
        with self._lock:
            return {
                "request_kinds": list(self._request_kinds),
                "request_methods": list(self._request_methods),
                "request_shapes": list(self._request_shapes),
                "response_shapes": [dict(item) for item in self._response_shapes],
                "sse_data_lines": self._sse_data_lines,
            }


class _SseLineBuffer:
    def __init__(self, collector: DeploymentReceiptCollector) -> None:
        self.collector = collector
        self.buffer = bytearray()

    def feed(self, chunk: bytes) -> None:
        self.buffer.extend(chunk)
        while b"\n" in self.buffer:
            line, _, remainder = self.buffer.partition(b"\n")
            self.buffer = bytearray(remainder)
            self.collector.feed_sse_line(bytes(line).rstrip(b"\r"))

    def finish(self) -> None:
        if self.buffer:
            self.collector.feed_sse_line(bytes(self.buffer).rstrip(b"\r"))
            self.buffer.clear()


class _SanitizingProxyHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.0"
    server_version = "OpenTrajectoryDeploymentProxy/1"

    def do_GET(self) -> None:  # noqa: N802
        self._forward()

    def do_POST(self) -> None:  # noqa: N802
        self._forward()

    def log_message(self, format: str, *args: Any) -> None:
        return

    @property
    def proxy(self) -> SanitizedResponsesProxy:
        return self.server.proxy  # type: ignore[attr-defined, no-any-return]

    def _forward(self) -> None:
        if not self.path.startswith(ALLOWED_PATH_PREFIX) or "://" in self.path:
            self.send_error(404)
            return
        request_kind = self.proxy.collector.record_request(self.command, self.path)
        if self.headers.get("Transfer-Encoding"):
            self.send_error(400, "chunked requests are not supported")
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self.send_error(400, "invalid content length")
            return
        body = self.rfile.read(length) if length else None
        request_headers = {
            name: value
            for name, value in self.headers.items()
            if name.lower() not in HOP_BY_HOP_HEADERS
            and name.lower() not in {"host", "content-length", "accept-encoding", "expect"}
        }
        request_headers["Host"] = UPSTREAM_HOST
        request_headers["Accept-Encoding"] = "identity"
        if body is not None:
            request_headers["Content-Length"] = str(len(body))

        connection = http.client.HTTPSConnection(
            UPSTREAM_HOST,
            UPSTREAM_PORT,
            context=self.proxy.tls_context,
            timeout=self.proxy.upstream_timeout,
        )
        try:
            connection.request(self.command, self.path, body=body, headers=request_headers)
            response = connection.getresponse()
            self.proxy.collector.record_headers(response.headers)
            self.send_response(response.status, response.reason)
            for name, value in response.getheaders():
                if name.lower() in HOP_BY_HOP_HEADERS or name.lower() == "content-length":
                    continue
                self.send_header(name, value)
            self.send_header("Connection", "close")
            self.end_headers()

            content_type = response.headers.get("content-type", "").lower()
            content_encoding = response.headers.get("content-encoding", "identity").lower()
            self.proxy.collector.record_response_shape(
                request_kind, response.status, content_type, content_encoding
            )
            parser = _SseLineBuffer(self.proxy.collector)
            parse_stream = request_kind == "responses" and content_encoding in {"", "identity"}
            if request_kind == "responses" and not parse_stream:
                self.proxy.collector.record_error("response stream used an unexpected encoding")
            while True:
                chunk = response.read(65536)
                if not chunk:
                    break
                if parse_stream:
                    parser.feed(chunk)
                self.wfile.write(chunk)
                self.wfile.flush()
            if parse_stream:
                parser.finish()
        except (OSError, http.client.HTTPException, ssl.SSLError):
            self.proxy.collector.record_error("upstream forwarding failed")
            if not self.wfile.closed:
                try:
                    self.send_error(502)
                except OSError:
                    pass
        finally:
            connection.close()
            self.close_connection = True


class _ProxyServer(ThreadingHTTPServer):
    daemon_threads = True


class SanitizedResponsesProxy:
    """Loopback-only reverse proxy that receipts no request or response content."""

    def __init__(self, *, upstream_timeout: float = 240.0) -> None:
        self.upstream_timeout = upstream_timeout
        self.tls_context = ssl.create_default_context(cafile=certifi.where())
        self.collector = DeploymentReceiptCollector()
        self.server = _ProxyServer(("127.0.0.1", 0), _SanitizingProxyHandler)
        self.server.proxy = self  # type: ignore[attr-defined]
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self._started = False

    @property
    def base_url(self) -> str:
        host, port = self.server.server_address
        return f"http://{host}:{port}{ALLOWED_PATH_PREFIX}"

    def start(self) -> SanitizedResponsesProxy:
        if self._started:
            raise DeploymentProxyError("deployment proxy already started")
        self._started = True
        self.thread.start()
        return self

    def close(self) -> None:
        if not self._started:
            self.server.server_close()
            return
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)

    def __enter__(self) -> SanitizedResponsesProxy:
        return self.start()

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        self.close()
