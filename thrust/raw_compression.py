"""Lossless gzip handling for raw tab-separated measurement logs."""
from __future__ import annotations

import gzip
from pathlib import Path
from collections.abc import Callable


def compress_raw_log(
    path: str | Path,
    *,
    progress_callback: Callable[[str, int, int], None] | None = None,
) -> Path:
    """Compress a raw log losslessly, then replace the plaintext source.

    Existing gzip logs are validated and returned unchanged. When compression
    fails, the source remains intact and the temporary file is removed.
    """
    source = Path(path)
    if source.suffix == ".gz":
        if progress_callback:
            progress_callback("Verifying compressed log", 0, 0)
        with gzip.open(source, "rb") as stream:
            while stream.read(1024 * 1024):
                pass
        return source
    if not source.is_file():
        raise FileNotFoundError(source)

    destination = source.with_name(source.name + ".gz")
    if destination.exists():
        raise FileExistsError(destination)
    temporary = destination.with_name(f".{destination.name}.tmp")
    try:
        total = max(1, source.stat().st_size)
        completed = 0
        if progress_callback:
            progress_callback("Compressing raw log", 0, total)
        with source.open("rb") as input_file, temporary.open("wb") as output_file:
            with gzip.GzipFile(filename="", mode="wb", fileobj=output_file, mtime=0) as compressed:
                while chunk := input_file.read(1024 * 1024):
                    compressed.write(chunk)
                    completed += len(chunk)
                    if progress_callback:
                        progress_callback("Compressing raw log", completed, total)
        completed = 0
        verification_total = max(1, source.stat().st_size)
        if progress_callback:
            progress_callback("Verifying compressed log", 0, verification_total)
        with gzip.open(temporary, "rb") as check:
            while chunk := check.read(1024 * 1024):
                completed += len(chunk)
                if progress_callback:
                    progress_callback("Verifying compressed log", min(completed, verification_total), verification_total)
        if progress_callback:
            progress_callback("Verifying compressed log", verification_total, verification_total)
        temporary.replace(destination)
        source.unlink()
        return destination
    finally:
        temporary.unlink(missing_ok=True)

