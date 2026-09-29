"""Import historical and offline THRUST logs into THRUST-webdb.

Run from the repository root with:
    python scripts/import_measurements.py
    python scripts/import_measurements.py --watch
"""
from __future__ import annotations

import argparse
import base64
import getpass
import gzip
import hashlib
import io
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from thrust.analysis.scope_log import ScopeLogError, analyze_scope_log
from thrust.analysis.simple_log import SimpleLogError, analyze_simple_log
from thrust.webdb_client import DEFAULT_WEBDB_URL, WebDbClient, WebDbError


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_WORKSPACE = Path.home() / "Documents" / "THRUST" / "import"
LOG_SUFFIXES = (".tsv", ".txt", ".log", ".tsv.gz", ".txt.gz", ".log.gz")
PARTICIPANT_ID = re.compile(r"^[A-Z0-9]{5}$")
DATE_SUFFIX = re.compile(r"(?:^|_)20\d{6}_\d{6}$")
VERSIONED_PROFILE = re.compile(r"^(?P<code>.+)_v(?P<version>\d+(?:[._]\d+)*)$", re.I)


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
        return {"mode": "SCOPE", "participant": participant, "difficulty": difficulty, "profile": profile}

    match = re.match(r"^simple_(.+)$", stem, re.I)
    if match:
        parts = match.group(1).split("_")
        if len(parts) < 1:
            return None
        participant = parts[0].upper()
        if not PARTICIPANT_ID.fullmatch(participant):
            return None
        profile = DATE_SUFFIX.sub("", "_".join(parts[1:]))
        return {"mode": "SIMPLE", "participant": participant, "difficulty": "", "profile": profile}
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

    label_parts = [info.get("difficulty", ""), profile]
    label = "_".join(part for part in label_parts if part)
    if not label:
        label = info.get("difficulty") or "UNSPECIFIED"
    test_code = f"LEGACY_{mode}_{slug(label, 'UNSPECIFIED')}"[:50].rstrip("_")
    descriptor = {
        "test_code": test_code,
        "name": f"Legacy {mode} · {label.replace('_', ' ')}"[:120],
        "version": "legacy-1",
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


class MeasurementImporter:
    def __init__(self, client: WebDbClient, *, dry_run: bool, report_dir: Path) -> None:
        self.client = client
        self.dry_run = dry_run
        self.report_dir = report_dir
        self.participants = client.list_participants()
        self.tests = client.list_tests()
        self.measurements = client._request_list("/api/admin/measurements")
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

        if info["mode"] == "SCOPE":
            analysis = analyze_scope_log(path)
            analysis["started_at"] = started_at_for(path)
            analysis["analysis_type"] = "SCOPE_STEP_RESPONSE"
        else:
            analysis = analyze_simple_log(path, started_at=started_at_for(path))

        compressed = read_compressed(path)
        digest = hashlib.sha256(compressed).hexdigest()
        if digest in self.uploaded_hashes:
            say(f"Already present in WebDB, skipping: {path.name}", "SKIP")
            self.done_paths.add(path)
            return "duplicate"

        participant = self.ensure_participant(participant_code)
        test = self.ensure_test(info)
        report_name = f"{digest}.analysis.json"
        self.report_dir.mkdir(parents=True, exist_ok=True)
        (self.report_dir / report_name).write_text(
            json.dumps(analysis, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8"
        )
        say(
            f"{info['mode']} · participant {participant_code} · "
            f"{test['test_code'] + ' v' + str(test['version']) if test else 'legacy test (planned)'} · "
            f"{analysis.get('sample_count', analysis.get('metrics', {}).get('simple_sample_count', '?'))} samples · {path}"
        )
        if self.dry_run:
            self.done_paths.add(path)
            return "planned"
        if participant is None or test is None:
            raise ImportProblem("Could not resolve participant or test after creation.")

        filename = path.name if path.name.lower().endswith(".gz") else path.name + ".gz"
        payload = {
            "participant_id": participant["id"],
            "test_definition_id": test["id"],
            "started_at": analysis.get("started_at") or started_at_for(path),
            "status": "recorded",
            "source_file_name": filename,
            "raw_content_type": "application/gzip",
            "raw_log_base64": base64.b64encode(compressed).decode("ascii"),
            "analysis_data": analysis,
        }
        self.client._request_json("/api/admin/measurements", method="POST", body=payload)
        self.uploaded_hashes.add(digest)
        self.done_paths.add(path)
        say(f"Uploaded successfully; source file was left unchanged: {path.name}", "OK")
        return "uploaded"


def candidate_logs(roots: list[Path]) -> list[Path]:
    found: set[Path] = set()
    for root in roots:
        if not root.exists():
            continue
        for item in root.rglob("*"):
            if item.is_file() and any(item.name.lower().endswith(suffix) for suffix in LOG_SUFFIXES):
                if describe_log(item):
                    found.add(item.resolve())
    return sorted(found, key=lambda path: (path.stat().st_mtime, str(path).lower()))


def scan(importer: MeasurementImporter, roots: list[Path]) -> tuple[int, int]:
    imported = 0
    failures = 0
    files = candidate_logs(roots)
    say(f"Scanning {len(roots)} folder(s); found {len(files)} THRUST log(s).")
    for path in files:
        try:
            result = importer.process(path)
            imported += result in {"uploaded", "planned"}
        except (ScopeLogError, SimpleLogError, WebDbError, ImportProblem, OSError, ValueError) as exc:
            failures += 1
            say(f"Could not import {path}: {exc}", "ERROR")
    say(f"Pass complete: {imported} uploaded/planned, {failures} failed.")
    return imported, failures


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Batch import THRUST measurement logs into WebDB.")
    parser.add_argument("--workspace", type=Path, default=DEFAULT_WORKSPACE,
                        help=f"recursive import folder (default: {DEFAULT_WORKSPACE})")
    parser.add_argument("--webdb", default=os.environ.get("THRUST_WEBDB_URL", DEFAULT_WEBDB_URL),
                        help="WebDB base URL")
    parser.add_argument("--username", default=os.environ.get("THRUST_WEBDB_USERNAME"), help="WebDB username")
    parser.add_argument("--watch", action="store_true", help="keep checking for new completed offline logs")
    parser.add_argument("--interval", type=int, default=5, help="watch interval in seconds (default: 5)")
    parser.add_argument("--dry-run", action="store_true", help="analyze logs and show planned changes without uploading")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    workspace = args.workspace.expanduser().resolve()
    workspace.mkdir(parents=True, exist_ok=True)
    output_root = Path.home() / "Documents" / "THRUST" / "output"
    roots = [workspace]
    if args.watch and output_root.resolve() != workspace:
        roots.append(output_root)
    report_dir = workspace / ".thrust-import" / "analysis"

    username = args.username or input("WebDB username: ").strip()
    password = os.environ.get("THRUST_WEBDB_PASSWORD") or getpass.getpass("WebDB password: ")
    if not username or not password:
        say("Username and password are required.", "ERROR")
        return 2

    say(f"WebDB: {args.webdb}")
    say(f"Import workspace: {workspace}")
    say(f"Recursive folders: {', '.join(map(str, roots))}")
    say("Mode: dry run (no database writes)." if args.dry_run else "Mode: upload.")
    try:
        client = WebDbClient(args.webdb, timeout=45)
        account = client.login(username, password)
        if account.get("role") not in {"admin", "superadmin", "researcher"}:
            raise ImportProblem("Use a WebDB admin or researcher account; student accounts cannot batch import measurements.")
        importer = MeasurementImporter(client, dry_run=args.dry_run, report_dir=report_dir)
        say(f"Authenticated as {username} ({account.get('role')}).")
        if not args.watch:
            _, failures = scan(importer, roots)
            return 1 if failures else 0

        say(f"Watch mode active; checking every {max(1, args.interval)} seconds. Press Ctrl+C to stop.")
        stable: dict[Path, tuple[int, int, int]] = {}
        while True:
            for path in candidate_logs(roots):
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
