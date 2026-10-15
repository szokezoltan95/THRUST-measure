"""Durable local outbox for measurement uploads."""
from __future__ import annotations

import json
import threading
import uuid
from pathlib import Path
from typing import Any

from thrust.paths import APP_DATA_DIR


class MeasurementUploadQueue:
    """Persist pending upload metadata so it survives application restarts.

    Authentication state is deliberately never stored. A queued measurement is
    resumed only after the operator signs in to WebDB again.
    """

    def __init__(self, directory: Path | None = None) -> None:
        self.directory = directory or APP_DATA_DIR / "pending_uploads"
        self.directory.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()

    def enqueue(self, payload: dict[str, Any]) -> str:
        item_id = uuid.uuid4().hex
        record = {key: value for key, value in payload.items() if key != "client"}
        record.update({"queue_id": item_id, "queue_status": "queued"})
        self._write(item_id, record)
        return item_id

    def update(self, item_id: str, **changes: Any) -> None:
        with self._lock:
            path = self._path(item_id)
            record = json.loads(path.read_text(encoding="utf-8"))
            record.update(changes)
            self._write(item_id, record)

    def remove(self, item_id: str) -> None:
        with self._lock:
            self._path(item_id).unlink(missing_ok=True)

    def pending(self) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        with self._lock:
            for path in sorted(self.directory.glob("*.json"), key=lambda item: item.stat().st_mtime):
                try:
                    record = json.loads(path.read_text(encoding="utf-8"))
                    if isinstance(record, dict) and record.get("queue_id") == path.stem:
                        records.append(record)
                except (OSError, json.JSONDecodeError):
                    continue
        return records

    def _path(self, item_id: str) -> Path:
        if not item_id or any(char not in "0123456789abcdef" for char in item_id):
            raise ValueError("Invalid upload queue ID.")
        return self.directory / f"{item_id}.json"

    def _write(self, item_id: str, record: dict[str, Any]) -> None:
        encoded = json.dumps(record, ensure_ascii=False, indent=2)
        with self._lock:
            path = self._path(item_id)
            temporary = path.with_suffix(".tmp")
            temporary.write_text(encoded, encoding="utf-8")
            temporary.replace(path)
