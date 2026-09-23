"""Small standard-library client for THRUST-webdb."""

from __future__ import annotations

import base64
import json
import os
from http.cookiejar import CookieJar
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import HTTPCookieProcessor, Request, build_opener


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

    @classmethod
    def from_environment(cls) -> "WebDbClient":
        return cls(os.environ.get("THRUST_WEBDB_URL", "http://localhost:8080"))

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
        path = Path(raw_log_path)
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
                "raw_content_type": "text/tab-separated-values",
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
