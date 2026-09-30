"""Small standard-library client for THRUST-webdb."""

from __future__ import annotations

import base64
import json
import os
import re
import threading
from http.cookiejar import CookieJar
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import HTTPCookieProcessor, Request, build_opener

from thrust.paths import APP_DATA_DIR
from thrust.raw_compression import compress_raw_log


DEFAULT_WEBDB_URL = "https://thrust.lf.tuke.sk"


class WebDbError(RuntimeError):
    """Raised when the web database cannot fulfil a client request."""


class WebDbClient:
    def __init__(self, base_url: str, *, timeout: float = 30.0) -> None:
        self.base_url = base_url.rstrip("/") + "/"
        self.timeout = timeout
        self.csrf_token: str | None = None
        self.role: str | None = None
        self.account: dict[str, Any] | None = None
        self._opener = build_opener(HTTPCookieProcessor(CookieJar()))
        self._request_lock = threading.RLock()

    @classmethod
    def from_environment(cls) -> "WebDbClient":
        return cls(os.environ.get("THRUST_WEBDB_URL", DEFAULT_WEBDB_URL))

    def login(self, username: str, password: str) -> dict[str, Any]:
        payload = self._request_json(
            "/api/auth/login",
            method="POST",
            body={"username": username, "password": password},
        )
        self.csrf_token = payload.get("csrf_token")
        self.role = payload.get("role")
        self.account = payload
        if not self.csrf_token:
            raise WebDbError("Web database did not return a CSRF token.")
        return payload

    def report_presence(
        self,
        status: str,
        *,
        participant_id: str | None = None,
        test_definition_id: str | None = None,
    ) -> dict[str, Any]:
        """Report this desktop client's live state to WebDB."""
        return self._request_json(
            "/api/live/measure-presence",
            method="POST",
            body={
                "status": status,
                "participant_id": participant_id,
                "test_definition_id": test_definition_id,
            },
        )

    def list_participants(self) -> list[dict[str, Any]]:
        return self._request_list("/api/admin/participants")

    def list_tests(self) -> list[dict[str, Any]]:
        path = "/api/student/tests" if self.role == "student" else "/api/admin/tests"
        return self._request_list(path)

    def get_test_configuration(self, test_id: str) -> dict[str, Any]:
        prefix = "/api/student/tests" if self.role == "student" else "/api/admin/tests"
        manifest = self._request_json(f"{prefix}/{test_id}/configuration")
        if manifest.get("schema_version") != "test-configuration-v1":
            raise WebDbError("Unsupported test configuration schema.")
        if not isinstance(manifest.get("test"), dict):
            raise WebDbError("The test manifest is missing its test definition.")
        return manifest

    def download_background(self, asset_id: str) -> Path:
        """Cache an immutable WebDB background in the local THRUST data directory."""
        if not re.fullmatch(r"[0-9a-f]{32}", asset_id):
            raise WebDbError("Invalid SimPLE background ID.")
        cache = APP_DATA_DIR / "backgrounds"
        cache.mkdir(parents=True, exist_ok=True)
        for suffix in (".png", ".jpg"):
            existing = cache / f"{asset_id}{suffix}"
            if existing.is_file():
                return existing
        request = Request(
            urljoin(self.base_url, f"api/backgrounds/{asset_id}"),
            headers={"Accept": "image/png, image/jpeg"},
        )
        try:
            with self._request_lock:
                with self._opener.open(request, timeout=self.timeout) as response:
                    content_type = response.headers.get_content_type()
                    content = response.read(5_000_001)
        except (HTTPError, URLError, TimeoutError) as exc:
            raise WebDbError(f"Could not download SimPLE background: {exc}") from exc
        if len(content) > 5_000_000:
            raise WebDbError("SimPLE background exceeds the 5 MB limit.")
        if content_type == "image/png" and content.startswith(b"\x89PNG\r\n\x1a\n"):
            suffix = ".png"
        elif content_type == "image/jpeg" and content.startswith(b"\xff\xd8\xff"):
            suffix = ".jpg"
        else:
            raise WebDbError("WebDB returned an unsupported background image.")
        destination = cache / f"{asset_id}{suffix}"
        temporary = cache / f"{asset_id}.tmp"
        try:
            temporary.write_bytes(content)
            temporary.replace(destination)
        finally:
            temporary.unlink(missing_ok=True)
        return destination

    def upload_measurement(
        self,
        *,
        participant_id: str,
        test_definition_id: str,
        started_at: str,
        raw_log_path: str | Path,
        analysis_data: dict[str, Any] | None = None,
        status: str = "recorded",
    ) -> dict[str, Any]:
        path = compress_raw_log(Path(raw_log_path))
        raw_bytes = path.read_bytes()
        return self._request_json(
            "/api/student/measurements" if self.role == "student" else "/api/admin/measurements",
            method="POST",
            body={
                "participant_id": participant_id,
                "test_definition_id": test_definition_id,
                "started_at": started_at,
                "status": status,
                "source_file_name": path.name,
                "raw_content_type": "application/gzip",
                "raw_log_base64": base64.b64encode(raw_bytes).decode("ascii"),
                "analysis_data": analysis_data,
            },
        )

    def _request_list(self, path: str) -> list[dict[str, Any]]:
        data = self._request(path)
        if not isinstance(data, list) or not all(isinstance(item, dict) for item in data):
            raise WebDbError("Web database returned an invalid list.")
        return data

    def _request_json(
        self,
        path: str,
        *,
        method: str = "GET",
        body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        data = self._request(path, method=method, body=body)
        if not isinstance(data, dict):
            raise WebDbError("Web database returned an invalid JSON object.")
        return data

    def _request(
        self,
        path: str,
        *,
        method: str = "GET",
        body: dict[str, Any] | None = None,
    ) -> Any:
        headers = {"Accept": "application/json"}
        if self.csrf_token:
            headers["X-CSRF-Token"] = self.csrf_token
        encoded_body: bytes | None = None
        if body is not None:
            encoded_body = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json"
        request = Request(
            urljoin(self.base_url, path.lstrip("/")),
            data=encoded_body,
            headers=headers,
            method=method,
        )
        try:
            with self._request_lock:
                with self._opener.open(request, timeout=self.timeout) as response:
                    return json.loads(response.read().decode("utf-8"))
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
            detail = ""
            if isinstance(exc, HTTPError):
                try:
                    payload = json.loads(exc.read().decode("utf-8"))
                    detail = str(payload.get("detail", ""))
                except (json.JSONDecodeError, UnicodeDecodeError):
                    pass
            suffix = f": {detail}" if detail else ""
            raise WebDbError(f"Web database request failed{suffix}") from exc
