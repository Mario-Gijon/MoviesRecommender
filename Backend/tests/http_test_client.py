from __future__ import annotations

import http.client
import json
import os
import socket
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping


BACKEND_DIR = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class HttpTestResponse:
    status: int
    headers: dict[str, str]
    body: object
    elapsed_seconds: float


class LiveApiServer:
    def __init__(self, *, environment: Mapping[str, str] | None = None) -> None:
        self._port: int | None = None
        self._process: subprocess.Popen[str] | None = None
        self._environment = dict(environment or {})

    def start(self) -> None:
        self._port = _available_port()
        self._process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "app.main:app",
                "--host",
                "127.0.0.1",
                "--port",
                str(self._port),
                "--log-level",
                "warning",
            ],
            cwd=BACKEND_DIR,
            env={**os.environ, **self._environment},
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            if self._process.poll() is not None:
                output = self._process.stdout.read() if self._process.stdout else ""
                raise RuntimeError(f"Test API failed to start:\n{output}")
            try:
                response = self.request("GET", "/health", timeout=0.5)
            except (ConnectionError, OSError):
                time.sleep(0.05)
                continue
            if response.status == 200:
                return
            time.sleep(0.05)
        self.stop()
        raise RuntimeError("Timed out waiting for the test API to start.")

    def stop(self) -> None:
        if self._process is None:
            return
        if self._process.poll() is None:
            self._process.terminate()
            try:
                self._process.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                self._process.kill()
                self._process.communicate(timeout=5)
        self._process = None

    def request(
        self,
        method: str,
        path: str,
        *,
        json_body: object | None = None,
        timeout: float = 30,
    ) -> HttpTestResponse:
        if self._port is None:
            raise RuntimeError("Test API is not running.")

        encoded_body = None
        headers = {"Accept": "application/json"}
        if json_body is not None:
            encoded_body = json.dumps(json_body).encode("utf-8")
            headers["Content-Type"] = "application/json"

        connection = http.client.HTTPConnection(
            "127.0.0.1",
            self._port,
            timeout=timeout,
        )
        started_at = time.perf_counter()
        try:
            connection.request(
                method,
                path,
                body=encoded_body,
                headers=headers,
            )
            response = connection.getresponse()
            raw_body = response.read()
            elapsed_seconds = time.perf_counter() - started_at
            response_headers = {
                key.lower(): value for key, value in response.getheaders()
            }
        finally:
            connection.close()

        body: object
        if raw_body:
            body = json.loads(raw_body)
        else:
            body = None
        return HttpTestResponse(
            status=response.status,
            headers=response_headers,
            body=body,
            elapsed_seconds=elapsed_seconds,
        )


def _available_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_socket:
        server_socket.bind(("127.0.0.1", 0))
        return int(server_socket.getsockname()[1])
