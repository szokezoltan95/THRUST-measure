"""Lossless gzip handling for raw tab-separated measurement logs."""
from __future__ import annotations

import gzip
import shutil
from pathlib import Path


def compress_raw_log(path: str | Path) -> Path:
    """Compress a raw log losslessly, then replace the plaintext source.

    Existing gzip logs are validated and returned unchanged. When compression
    fails, the source remains intact and the temporary file is removed.
    """
    source = Path(path)
    if source.suffix == ".gz":
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
        with source.open("rb") as input_file, temporary.open("wb") as output_file:
            with gzip.GzipFile(filename="", mode="wb", fileobj=output_file, mtime=0) as compressed:
                shutil.copyfileobj(input_file, compressed, length=1024 * 1024)
        with gzip.open(temporary, "rb") as check:
            while check.read(1024 * 1024):
                pass
        temporary.replace(destination)
        source.unlink()
        return destination
    finally:
        temporary.unlink(missing_ok=True)
