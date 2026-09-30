"""Import historical and offline THRUST logs into THRUST-webdb.

Run from the repository root with:
    python scripts/import_measurements.py
    python scripts/import_measurements.py --watch
"""
from __future__ import annotations

import argparse
import base64
import csv
import getpass
import gzip
import hashlib
import io
import json
import os
import re
import sys
import time
import zlib
from datetime import datetime, timezone
from io import StringIO
from pathlib import Path
from typing import Any

from thrust.analysis.artifact import analysis_sidecar_path, build_analysis_artifact, save_analysis_artifact
from thrust.analysis.scope_log import ScopeLogError, analyze_scope_log
from thrust.analysis.simple_log import SimpleLogError, analyze_simple_log
from thrust.webdb_client import DEFAULT_WEBDB_URL, WebDbClient, WebDbError


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_WORKSPACE = Path.home() / "Documents" / "THRUST" / "import"
LOG_SUFFIXES = (".tsv", ".txt", ".log", ".tsv.gz", ".txt.gz", ".log.gz")
PARTICIPANT_ID = re.compile(r"^[A-Z0-9]{5}$")
DATE_SUFFIX = re.compile(r"(?:^|_)20\d{6}_\d{6}$")
VERSIONED_PROFILE = re.compile(r"^(?P<code>.+)_v(?P<version>[A-Za-z0-9][A-Za-z0-9._-]*)$", re.I)
LEGACY_SCOPE_COLUMNS = {
    "AILE": "LX", "ELEV": "LY", "THRO": "RY", "RUDD": "RX",
    "AREQ": "LXRQ", "EREQ": "LYRQ", "TREQ": "RYRQ", "RREQ": "RXRQ",
    "TIME[S]": "TIME",
}
SCOPE_COLUMN_ORDER = (
    "TIME", "LX", "LY", "RY", "RX", "LEVR", "BUTT", "SIDL", "SIDR",
    "LXRQ", "LYRQ", "RYRQ", "RXRQ", "IRRS", "ACTION_ID", "IN_RANGE",
)


class ImportProblem(RuntimeError):
    pass


def say(message: str, level: str = "INFO") -> None:
    print(f"[{level}] {message}", flush=True)


def file_stem(path: Path) -> str:
    name = path.name
    if name.lower().endswith(".gz"):
        name = name[:-3]
    return Path(name).stem


def describe_log(path: Path) -> dict[str, str] | None:
    """Extract mode, five-character participant ID and profile from the filename."""
    stem = file_stem(path)
    normalized = re.match(r"^THRUST_([A-Z0-9]{5})_(.+)_(20\d{6}_\d{6})$", stem, re.I)
    if normalized:
        participant = normalized.group(1).upper()
        profile = normalized.group(2)
        sidecar = analysis_sidecar_path(path)
        if sidecar.is_file():
            try:
                artifact = json.loads(sidecar.read_text(encoding="utf-8"))
                analysis_type = artifact.get("analysis_type", "")
                mode = "SIMPLE" if analysis_type == "SIMPLE_2D_FLIGHT" else "SCOPE"
                test = artifact.get("test", {})
                if test.get("test_code") and test.get("version"):
                    profile = f"{test['test_code']}_v{test['version']}"
                return {"mode": mode, "participant": participant, "difficulty": "", "profile": profile, "legacy": "false"}
            except (OSError, ValueError, AttributeError):
                pass
        upper = profile.upper()
        if upper.startswith(("SIMPLE_", "LEGACY_SIMPLE_")):
            mode = "SIMPLE"
        elif upper.startswith(("SCOPE_", "LEGACY_SCOPE_")):
            mode = "SCOPE"
        else:
            return None
        return {"mode": mode, "participant": participant, "difficulty": "", "profile": profile, "legacy": "false"}

    match = re.match(r"^scope_log_(.+)$", stem, re.I)
    if match:
        parts = match.group(1).split("_")
        if len(parts) < 2:
            return None
        participant = parts[0].upper()
        if not PARTICIPANT_ID.fullmatch(participant):
            return None
        rest = parts[1:]
        difficulty = ""
        if rest and rest[0].upper() in {"EASY", "MEDIUM", "HARD", "EXPERT"}:
            difficulty = rest.pop(0).upper()
        profile = "_".join(rest)
        profile = DATE_SUFFIX.sub("", profile)
        profile = re.sub(r"_(?:SCOPE|SIMPLE)$", "", profile, flags=re.I)
        return {"mode": "SCOPE", "participant": participant, "difficulty": difficulty, "profile": profile, "legacy": "true"}

    match = re.match(r"^simple_(.+)$", stem, re.I)
    if match:
        parts = match.group(1).split("_")
        if len(parts) < 1:
            return None
        participant = parts[0].upper()
        if not PARTICIPANT_ID.fullmatch(participant):
            return None
        profile = DATE_SUFFIX.sub("", "_".join(parts[1:]))
        profile = re.sub(r"_(?:SCOPE|SIMPLE)$", "", profile, flags=re.I)
        return {"mode": "SIMPLE", "participant": participant, "difficulty": "", "profile": profile, "legacy": "true"}
    return None


def started_at_for(path: Path) -> str:
    match = re.search(r"(20\d{6}_\d{6})", path.name)
    if match:
        try:
            local_time = datetime.strptime(match.group(1), "%Y%m%d_%H%M%S").astimezone()
            return local_time.isoformat()
        except ValueError:
            pass
    return datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat()


def slug(value: str, fallback: str) -> str:
    cleaned = re.sub(r"[^A-Z0-9]+", "_", value.upper()).strip("_")
    return cleaned or fallback


def resolve_test_descriptor(info: dict[str, str], tests: list[dict[str, Any]]) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    mode = info["mode"]
    profile = info["profile"].strip("_")
    if info.get("legacy") != "true":
        parsed = VERSIONED_PROFILE.fullmatch(profile)
        if parsed:
            code = parsed.group("code").upper()
            version = parsed.group("version").replace("_", ".")
            current = next(
                (item for item in tests if item.get("test_code", "").upper() == code
                 and str(item.get("version", "")).lower() == version.lower()),
                None,
            )
            if current and current.get("is_active", True):
                return current, {}
            if current:
                profile = f"{code}_v{version}"
        elif profile:
            same_code = [item for item in tests if item.get("test_code", "").upper() == profile.upper()]
            if len(same_code) == 1 and same_code[0].get("is_active", True):
                return same_code[0], {}

    # Legacy filenames often repeat their mode in both the difficulty and
    # profile fields (for example HARD_HARD1). The profile is the useful ID.
    label_parts = [profile or info.get("difficulty", "")]
    label = "_".join(part for part in label_parts if part)
    if not label:
        label = info.get("difficulty") or "UNSPECIFIED"
    label = re.sub(r"^(?:SCOPE|SIMPLE)_?", "", label, flags=re.I)
    label = re.sub(r"_?(?:SCOPE|SIMPLE)$", "", label, flags=re.I)
    test_code = f"LEGACY_{mode}_{slug(label, 'UNSPECIFIED')}"[:50].rstrip("_")
    descriptor = {
        "test_code": test_code,
        "name": f"Legacy {mode} · {label.replace('_', ' ')}"[:120],
        "version": "LEGACY",
        "analysis_profile": "SCOPE_STEP_RESPONSE_V1" if mode == "SCOPE" else "SIMPLE_FLIGHT_V1",
        "configuration": {},
    }
    return None, descriptor


def read_compressed(path: Path) -> bytes:
    data = path.read_bytes()
    if path.name.lower().endswith(".gz"):
        # The analyzer has already read and validated the complete input stream.
        return data
    buffer = io.BytesIO()
    with gzip.GzipFile(filename="", mode="wb", fileobj=buffer, compresslevel=6, mtime=0) as stream:
        stream.write(data)
    return buffer.getvalue()


def normalize_raw_log(path: Path, mode: str) -> tuple[bytes, bool]:
    """Return gzip bytes with legacy SCoPE axes renamed and columns consistently ordered."""
    compressed = read_compressed(path)
    try:
        raw = gzip.decompress(compressed) if path.name.lower().endswith(".gz") else path.read_bytes()
        source = raw.decode("utf-8-sig")
    except (OSError, EOFError, UnicodeDecodeError, gzip.BadGzipFile, zlib.error) as exc:
        raise ImportProblem(f"Could not decode raw log {path.name}: {exc}") from exc
    rows = csv.reader(StringIO(source, newline=""), delimiter="\t")
    try:
        original_header = next(rows)
    except StopIteration as exc:
        raise ImportProblem(f"Raw log {path.name} is empty.") from exc
    header = [LEGACY_SCOPE_COLUMNS.get(item.strip().upper(), item.strip()) if mode == "SCOPE" else item.strip()
              for item in original_header]
    if len(header) != len(set(name.upper() for name in header)):
        raise ImportProblem(f"Renaming legacy axes in {path.name} creates duplicate columns.")
    if mode == "SCOPE":
        ordered = [name for name in SCOPE_COLUMN_ORDER if name in header]
        ordered.extend(name for name in header if name not in ordered)
    else:
        ordered = header
    changed = header != original_header or ordered != header or not path.name.lower().endswith(".gz")
    if not changed:
        return compressed, False

    positions = {name: index for index, name in enumerate(header)}
    output = StringIO(newline="")
    writer = csv.writer(output, delimiter="\t", lineterminator="\n")
    writer.writerow(ordered)
    for row in rows:
        padded = row + [""] * max(0, len(header) - len(row))
        writer.writerow([padded[positions[name]] if positions[name] < len(padded) else "" for name in ordered])
    buffer = io.BytesIO()
    with gzip.GzipFile(filename="", mode="wb", fileobj=buffer, compresslevel=6, mtime=0) as stream:
        stream.write(output.getvalue().encode("utf-8"))
    return buffer.getvalue(), True


def normalized_output_name(info: dict[str, str], test: dict[str, Any], started_at: str) -> str:
    test_code = str(test.get("test_code", "LEGACY"))
    version = str(test.get("version", "LEGACY"))
    if version.upper() == "LEGACY":
        prefix = f"LEGACY_{info['mode']}_"
        if test_code.upper().startswith(prefix):
            test_code = f"{info['mode']}_{test_code[len(prefix):]}"
    try:
        stamp = datetime.fromisoformat(started_at.replace("Z", "+00:00")).astimezone().strftime("%Y%m%d_%H%M%S")
    except ValueError:
        stamp = datetime.now().astimezone().strftime("%Y%m%d_%H%M%S")
    return f"THRUST_{info['participant']}_{slug(test_code, 'TEST')}_v{slug(version, 'LEGACY')}_{stamp}.tsv.gz"


class MeasurementImporter:
    def __init__(self, client: WebDbClient | None, *, dry_run: bool, output_dir: Path,
                 convert_only: bool = False) -> None:
        self.client = client
        self.dry_run = dry_run
        self.output_dir = output_dir.expanduser().resolve()
        self.convert_only = convert_only
        self.participants = client.list_participants() if client else []
        self.tests = client.list_tests() if client else []
        self.measurements = client._request_list("/api/admin/measurements") if client else []
        self.participant_by_code = {p["participant_code"].upper(): p for p in self.participants}
        self.test_by_key = {
            (t.get("test_code", "").upper(), str(t.get("version", "")).lower()): t
            for t in self.tests
        }
        self.uploaded_hashes = {m.get("raw_sha256") for m in self.measurements if m.get("raw_sha256")}
        self.done_paths: set[Path] = set()

    def ensure_participant(self, participant_code: str) -> dict[str, Any] | None:
        existing = self.participant_by_code.get(participant_code)
        if existing:
            if not existing.get("is_active", True):
                raise ImportProblem(f"Participant {participant_code} exists but is inactive; activate it in WebDB first.")
            return existing
        say(f"Participant {participant_code} is missing; creating it.")
        if self.dry_run:
            return None
        if self.client is None:
            raise ImportProblem("WebDB is not connected.")
        try:
            participant = self.client._request_json(
                "/api/admin/participants", method="POST", body={"participant_code": participant_code}
            )
        except WebDbError:
            self.participants = self.client.list_participants()
            participant = next((p for p in self.participants if p["participant_code"].upper() == participant_code), None)
            if participant is None:
                raise
        self.participant_by_code[participant_code] = participant
        return participant

    def ensure_test(self, info: dict[str, str]) -> dict[str, Any] | None:
        current, descriptor = resolve_test_descriptor(info, self.tests)
        if current:
            return current
        key = (descriptor["test_code"], descriptor["version"].lower())
        existing = self.test_by_key.get(key)
        if existing:
            if not existing.get("is_active", True):
                raise ImportProblem(f"Legacy test {key[0]} is inactive; activate it in WebDB first.")
            return existing
        say(f"Creating legacy test {descriptor['test_code']} v{descriptor['version']}.")
        if self.dry_run:
            return None
        if self.client is None:
            raise ImportProblem("WebDB is not connected.")
        try:
            test = self.client._request_json("/api/admin/tests", method="POST", body=descriptor)
        except WebDbError:
            self.tests = self.client.list_tests()
            test = next(
                (t for t in self.tests if t.get("test_code", "").upper() == descriptor["test_code"]
                 and str(t.get("version", "")).lower() == descriptor["version"].lower()),
                None,
            )
            if test is None:
                raise
        self.test_by_key[key] = test
        return test

    def process(self, path: Path) -> str:
        path = path.resolve()
        info = describe_log(path)
        if info is None:
            return "ignored"
        if path in self.done_paths:
            return "already handled"
        participant_code = info["participant"]
        if not PARTICIPANT_ID.fullmatch(participant_code):
            raise ImportProblem(f"Participant ID {participant_code!r} must contain five letters or digits.")

        sidecar = analysis_sidecar_path(path)
        candidate: dict[str, Any] | None = None
        if sidecar.is_file():
            try:
                candidate = json.loads(sidecar.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                raise ImportProblem(f"Could not read analysis sidecar {sidecar}: {exc}") from exc
        source_bytes = read_compressed(path)
        source_digest = hashlib.sha256(source_bytes).hexdigest()
        normalized_bytes, was_normalized = normalize_raw_log(path, info["mode"])
        normalized_digest = hashlib.sha256(normalized_bytes).hexdigest()

        if info.get("legacy") == "true":
            _, descriptor = resolve_test_descriptor(info, [])
            test_descriptor = descriptor
        else:
            current, descriptor = resolve_test_descriptor(info, self.tests)
            if current:
                test_descriptor = current
            elif self.convert_only and isinstance(candidate, dict) and isinstance(candidate.get("test"), dict):
                test_descriptor = candidate["test"]
            else:
                test_descriptor = descriptor

        candidate_is_current = (
            isinstance(candidate, dict)
            and candidate.get("schema_version") == "thrust-analysis-v1"
            and info.get("legacy") != "true"
            and candidate.get("raw_log", {}).get("sha256") == source_digest
            and candidate.get("raw_log", {}).get("size_bytes") == len(source_bytes)
            and candidate.get("analysis_type") == ("SCOPE_STEP_RESPONSE" if info["mode"] == "SCOPE" else "SIMPLE_2D_FLIGHT")
            and candidate.get("test", {}).get("test_code") == test_descriptor.get("test_code")
            and str(candidate.get("test", {}).get("version")) == str(test_descriptor.get("version"))
        )
        analysis_started_at = (
            str(candidate.get("started_at")) if candidate_is_current
            else started_at_for(path)
        )
        filename = normalized_output_name(info, test_descriptor, analysis_started_at)
        output_path = self.output_dir / filename
        self.output_dir.mkdir(parents=True, exist_ok=True)
        if output_path.exists() and hashlib.sha256(output_path.read_bytes()).hexdigest() != normalized_digest:
            stem, suffix = output_path.name.removesuffix(".tsv.gz"), ".tsv.gz"
            duplicate = 2
            while (self.output_dir / f"{stem}_{duplicate}{suffix}").exists():
                existing = self.output_dir / f"{stem}_{duplicate}{suffix}"
                if hashlib.sha256(existing.read_bytes()).hexdigest() == normalized_digest:
                    output_path = existing
                    break
                duplicate += 1
            else:
                output_path = self.output_dir / f"{stem}_{duplicate}{suffix}"
            filename = output_path.name
        temporary = output_path.with_suffix(output_path.suffix + ".tmp")
        temporary.write_bytes(normalized_bytes)
        temporary.replace(output_path)

        if candidate_is_current and not was_normalized:
            calculated = candidate
        elif info["mode"] == "SCOPE":
            calculated = analyze_scope_log(output_path)
        else:
            calculated = analyze_simple_log(output_path, started_at=analysis_started_at)

        analysis = build_analysis_artifact(
            output_path,
            calculated,
            started_at=analysis_started_at,
            test=test_descriptor,
            parameters=(candidate.get("parameters", {}) if candidate_is_current else {"legacy_import": True}),
            runtime=(candidate.get("runtime", {}) if candidate_is_current else {}),
            session_summary=(candidate.get("session_summary", {}) if candidate_is_current else {"legacy_import": info.get("legacy") == "true"}),
            raw_bytes=normalized_bytes,
            raw_file_name=filename,
        )
        saved_sidecar = save_analysis_artifact(output_path, analysis)
        say(
            f"{info['mode']} · participant {participant_code} · "
            f"{test_descriptor['test_code']} v{test_descriptor['version']} · "
            f"{analysis.get('sample_count', '?')} samples · saved {output_path}"
        )

        if self.convert_only:
            self.done_paths.add(path)
            return "converted"
        if self.dry_run:
            say(f"Dry run: prepared {output_path.name} and {saved_sidecar.name}; no WebDB writes.", "PLAN")
            self.done_paths.add(path)
            return "planned"
        if normalized_digest in self.uploaded_hashes:
            say(f"Normalized raw log is already in WebDB; saved local copy only: {output_path.name}", "SKIP")
            self.done_paths.add(path)
            return "duplicate"

        participant = self.ensure_participant(participant_code)
        test = self.ensure_test(info)
        if participant is None or test is None or self.client is None:
            raise ImportProblem("Could not resolve participant or test after creation.")
        payload = {
            "participant_id": participant["id"],
            "test_definition_id": test["id"],
            "started_at": analysis["started_at"],
            "status": "recorded",
            "source_file_name": filename,
            "raw_content_type": "application/gzip",
            "raw_log_base64": base64.b64encode(normalized_bytes).decode("ascii"),
            "analysis_data": analysis,
        }
        self.client._request_json("/api/admin/measurements", method="POST", body=payload)
        self.uploaded_hashes.add(normalized_digest)
        self.done_paths.add(path)
        say(f"Uploaded successfully: {output_path.name}; normalized sidecar: {saved_sidecar.name}", "OK")
        return "uploaded"


def candidate_logs(roots: list[Path], exclude_roots: list[Path] | None = None) -> list[Path]:
    found: set[Path] = set()
    excluded = [root.resolve() for root in (exclude_roots or [])]
    for root in roots:
        if not root.exists():
            continue
        for item in root.rglob("*"):
            if item.is_file() and any(item.name.lower().endswith(suffix) for suffix in LOG_SUFFIXES):
                resolved = item.resolve()
                if any(resolved == base or base in resolved.parents for base in excluded):
                    continue
                if describe_log(item):
                    found.add(item.resolve())
    return sorted(found, key=lambda path: (path.stat().st_mtime, str(path).lower()))


def scan(importer: MeasurementImporter, roots: list[Path]) -> tuple[int, int]:
    imported = 0
    failures = 0
    files = candidate_logs(roots, [importer.output_dir])
    say(f"Scanning {len(roots)} folder(s); found {len(files)} THRUST log(s).")
    say(f"PROGRESS\t0\t{len(files)}\tScanning files")
    for index, path in enumerate(files, start=1):
        try:
            result = importer.process(path)
            imported += result in {"uploaded", "planned", "converted"}
        except (ScopeLogError, SimpleLogError, WebDbError, ImportProblem, OSError, ValueError) as exc:
            failures += 1
            say(f"Could not import {path}: {exc}", "ERROR")
        say(f"PROGRESS\t{index}\t{len(files)}\t{path.name}")
    say(f"Pass complete: {imported} processed, {failures} failed.")
    return imported, failures


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Batch import THRUST measurement logs into WebDB.")
    parser.add_argument("--workspace", type=Path, default=DEFAULT_WORKSPACE,
                        help=f"recursive import folder (default: {DEFAULT_WORKSPACE})")
    parser.add_argument("--output", type=Path, default=Path.home() / "Documents" / "THRUST" / "normalized",
                        help="folder for normalized compressed logs and analysis sidecars")
    parser.add_argument("--webdb", default=os.environ.get("THRUST_WEBDB_URL", DEFAULT_WEBDB_URL),
                        help="WebDB base URL")
    parser.add_argument("--username", default=os.environ.get("THRUST_WEBDB_USERNAME"), help="WebDB username")
    parser.add_argument("--watch", action="store_true", help="keep checking for new completed offline logs")
    parser.add_argument("--interval", type=int, default=5, help="watch interval in seconds (default: 5)")
    parser.add_argument("--dry-run", action="store_true", help="analyze logs and show planned changes without uploading")
    parser.add_argument("--convert-only", action="store_true",
                        help="normalize and save files locally without connecting to WebDB")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    workspace = args.workspace.expanduser().resolve()
    workspace.mkdir(parents=True, exist_ok=True)
    output_dir = args.output.expanduser().resolve()
    output_root = Path.home() / "Documents" / "THRUST" / "output"
    roots = [workspace]
    if args.watch and output_root.resolve() != workspace:
        roots.append(output_root)

    say(f"WebDB: {args.webdb}")
    say(f"Import workspace: {workspace}")
    say(f"Normalized output folder: {output_dir}")
    say(f"Recursive folders: {', '.join(map(str, roots))}")
    try:
        client = None
        if not args.convert_only:
            username = args.username or input("WebDB username: ").strip()
            password = os.environ.get("THRUST_WEBDB_PASSWORD") or getpass.getpass("WebDB password: ")
            if not username or not password:
                say("Username and password are required.", "ERROR")
                return 2
            client = WebDbClient(args.webdb, timeout=45)
            account = client.login(username, password)
            if account.get("role") not in {"admin", "superadmin", "researcher"}:
                raise ImportProblem("Use a WebDB admin, superadmin or researcher account for legacy imports.")
            say(f"Authenticated as {username} ({account.get('role')}).")
        mode = "convert only" if args.convert_only else "dry run" if args.dry_run else "convert and upload"
        say(f"Mode: {mode}.")
        importer = MeasurementImporter(client, dry_run=args.dry_run, output_dir=output_dir,
                                       convert_only=args.convert_only)
        if not args.watch:
            _, failures = scan(importer, roots)
            return 1 if failures else 0

        say(f"Watch mode active; checking every {max(1, args.interval)} seconds. Press Ctrl+C to stop.")
        stable: dict[Path, tuple[int, int, int]] = {}
        while True:
            for path in candidate_logs(roots, [output_dir]):
                stat = path.stat()
                previous = stable.get(path)
                signature = (stat.st_size, stat.st_mtime_ns)
                count = previous[2] + 1 if previous and previous[:2] == signature else 1
                stable[path] = (signature[0], signature[1], count)
                if count >= 2 and path not in importer.done_paths:
                    try:
                        importer.process(path)
                    except (ScopeLogError, SimpleLogError, WebDbError, ImportProblem, OSError, ValueError) as exc:
                        say(f"Could not import {path}: {exc}", "ERROR")
            time.sleep(max(1, args.interval))
    except KeyboardInterrupt:
        say("Stopped by user.")
        return 0
    except (WebDbError, ImportProblem, OSError) as exc:
        say(str(exc), "ERROR")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
