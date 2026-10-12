from __future__ import annotations

import hashlib
import json
import platform
import re
import sys
import tempfile
import urllib.request
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from PyQt6.QtCore import QThread, pyqtSignal

REPOSITORY = "szokezoltan95/THRUST-measure"
LATEST_RELEASE_URL = f"https://api.github.com/repos/{REPOSITORY}/releases/latest"
USER_AGENT = "THRUST-measure-updater"


def current_version() -> str:
    try:
        return version("thrust-measurement")
    except PackageNotFoundError:
        return "0.0.0"


def _version_parts(value: str) -> tuple[int, ...]:
    match = re.fullmatch(r"v?(\d+(?:\.\d+){1,3})", value.strip())
    if not match:
        raise ValueError(f"Unsupported version: {value}")
    return tuple(int(part) for part in match.group(1).split("."))


def is_newer_version(candidate: str, installed: str) -> bool:
    left, right = _version_parts(candidate), _version_parts(installed)
    size = max(len(left), len(right))
    return left + (0,) * (size - len(left)) > right + (0,) * (size - len(right))


def expected_asset_suffix(system: str | None = None, machine: str | None = None) -> str:
    system = system or sys.platform
    machine = (machine or platform.machine()).lower()
    if system == "win32":
        return "-windows-x64.zip"
    if system == "darwin":
        arch = "arm64" if machine in {"arm64", "aarch64"} else "x64"
        return f"-macos-{arch}.zip"
    if system.startswith("linux"):
        return "-linux-amd64.tar.gz"
    raise RuntimeError(f"Updates are not available for {system}.")


def find_update_asset(release: dict, suffix: str) -> dict:
    assets = release.get("assets", [])
    for asset in assets:
        if str(asset.get("name", "")).endswith(suffix):
            return asset
    raise RuntimeError(f"The release does not include the {suffix} update package.")


def check_latest_release(installed_version: str | None = None) -> dict | None:
    request = urllib.request.Request(
        LATEST_RELEASE_URL,
        headers={"Accept": "application/vnd.github+json", "User-Agent": USER_AGENT},
    )
    with urllib.request.urlopen(request, timeout=12) as response:
        release = json.load(response)
    tag = str(release.get("tag_name", ""))
    latest = tag.removeprefix("v")
    if not is_newer_version(latest, installed_version or current_version()):
        return None
    asset = find_update_asset(release, expected_asset_suffix())
    digest = str(asset.get("digest") or "")
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", digest):
        raise RuntimeError("GitHub did not provide a SHA-256 digest for the update package.")
    return {
        "version": latest,
        "tag": tag,
        "release_url": release.get("html_url", ""),
        "download_url": asset.get("browser_download_url", ""),
        "name": asset.get("name", ""),
        "digest": digest.removeprefix("sha256:"),
    }


def download_update(update: dict) -> str:
    request = urllib.request.Request(
        update["download_url"],
        headers={"User-Agent": USER_AGENT, "Accept": "application/octet-stream"},
    )
    suffix = ".zip" if str(update["name"]).endswith(".zip") else ".tar.gz"
    digest = hashlib.sha256()
    path = ""
    try:
        with urllib.request.urlopen(request, timeout=30) as response, tempfile.NamedTemporaryFile(
            prefix="thrust-update-", suffix=suffix, delete=False
        ) as output:
            path = output.name
            while chunk := response.read(1024 * 1024):
                digest.update(chunk)
                output.write(chunk)
        if digest.hexdigest().lower() != str(update["digest"]).lower():
            raise RuntimeError("The update package failed its SHA-256 integrity check.")
        return path
    except Exception:
        if path:
            Path(path).unlink(missing_ok=True)
        raise


class UpdateWorker(QThread):
    result_ready = pyqtSignal(object)

    def __init__(self, operation: str, update: dict | None = None, parent=None) -> None:
        super().__init__(parent)
        self.operation = operation
        self.update = update

    def run(self) -> None:
        try:
            if self.operation == "check":
                result = {"operation": "check", "ok": True, "update": check_latest_release()}
            elif self.operation == "download" and self.update is not None:
                result = {"operation": "download", "ok": True, "path": download_update(self.update)}
            else:
                raise ValueError("Unknown update operation.")
        except Exception as exc:
            result = {"operation": self.operation, "ok": False, "error": str(exc)}
        self.result_ready.emit(result)
