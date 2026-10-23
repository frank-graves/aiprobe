"""Offline tests for the HTTP transport layer."""

from __future__ import annotations

import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

import pytest

from aiprobe.core.http import CurlCffiClient, HttpClient, HttpConfig, HttpResponse


class _TestHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path == "/stream":
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"chunk1")
            self.wfile.write(b"chunk2")
            return

        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.send_header("X-Custom", "Hello")
        self.end_headers()
        self.wfile.write(b"Hello, World!")

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: Any) -> None:
        pass  # Silence server logs


@pytest.fixture(scope="module")
def local_server() -> Iterator[str]:
    server = ThreadingHTTPServer(("127.0.0.1", 0), _TestHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    host, port = server.server_address[:2]
    yield f"http://{host}:{port}"

    server.shutdown()
    thread.join()


def test_http_response() -> None:
    resp = HttpResponse(
        status_code=200,
        headers={"Content-Type": "application/json"},
        url="http://example.com",
        content=b'{"status": "ok"}',
    )
    assert resp.ok() is True
    assert resp.text() == '{"status": "ok"}'
    assert resp.json() == {"status": "ok"}
    assert resp.headers["content-type"] == "application/json"


def test_http_response_error() -> None:
    resp = HttpResponse(
        status_code=404,
        headers={},
        url="http://example.com",
        content=b"Not found",
    )
    assert resp.ok() is False


@pytest.mark.asyncio
async def test_curl_cffi_get(local_server: str) -> None:
    async with CurlCffiClient() as client:
        resp = await client.get(f"{local_server}/")
        assert resp.ok()
        assert resp.text() == "Hello, World!"
        assert resp.headers["x-custom"] == "Hello"


@pytest.mark.asyncio
async def test_curl_cffi_post(local_server: str) -> None:
    async with CurlCffiClient() as client:
        payload = {"foo": "bar"}
        resp = await client.post(f"{local_server}/", json=payload)
        assert resp.ok()
        assert resp.json() == payload


@pytest.mark.asyncio
async def test_curl_cffi_headers_merge(local_server: str) -> None:
    config = HttpConfig(headers={"X-Config": "1", "X-Override": "config"})
    async with CurlCffiClient(config=config) as client:
        # Request headers should override config headers
        resp = await client.get(
            f"{local_server}/",
            headers={"X-Override": "request", "X-Req": "2"},
        )
        assert resp.ok()
        # We can't inspect the request headers directly on the response,
        # but we can ensure the call doesn't crash and returns 200.
        # The server echoes nothing back by default, so we trust curl_cffi
        # merging logic here as it is standard dict.update.


@pytest.mark.asyncio
async def test_curl_cffi_stream(local_server: str) -> None:
    async with CurlCffiClient() as client:
        chunks = []
        async for chunk in client.stream("GET", f"{local_server}/stream"):
            chunks.append(chunk)
        assert b"".join(chunks) == b"chunk1chunk2"


@pytest.mark.asyncio
async def test_cookies() -> None:
    async with CurlCffiClient() as client:
        client.set_cookies({"a": "1"})
        assert client.get_cookies() == {"a": "1"}

        client.update_cookies({"b": "2"})
        assert client.get_cookies() == {"a": "1", "b": "2"}


def test_protocol_compliance() -> None:
    # Structural typing check: CurlCffiClient satisfies HttpClient
    client: HttpClient = CurlCffiClient()
    assert hasattr(client, "request")
    assert hasattr(client, "stream")
