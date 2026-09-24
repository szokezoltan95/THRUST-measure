#!/usr/bin/env python3
"""Add a local THRUST WebDB hostname to the system hosts file."""

from __future__ import annotations

import argparse
import ipaddress
import os
import platform
import re
import shlex
import subprocess
import sys
from pathlib import Path


MARKER = "# THRUST WebDB"


def hosts_path() -> Path:
    system = platform.system()
    if system == "Windows":
        root = os.environ.get("SystemRoot", r"C:\\Windows")
        return Path(root) / "System32" / "drivers" / "etc" / "hosts"
    if system in {"Linux", "Darwin"}:
        return Path("/etc/hosts")
    raise RuntimeError(f"Unsupported operating system: {system}")


def validate_alias(value: str) -> str:
    alias = value.strip().rstrip(".").lower()
    if len(alias) > 253 or not alias:
        raise ValueError("Enter a valid hostname alias, for example thrust.webdb.")
    labels = alias.split(".")
    if any(not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label) for label in labels):
        raise ValueError("Alias must contain only hostname characters (letters, digits, hyphens, dots).")
    return alias


def update_hosts_text(text: str, address: str, alias: str) -> tuple[str, bool]:
    """Ensure alias points to address, leaving unrelated hosts entries intact."""
    output: list[str] = []
    changed = False
    found = False

    for line in text.splitlines():
        content, sep, comment = line.partition("#")
        fields = content.split()
        if alias in fields[1:]:
            found = True
            fields = [fields[0], *(name for name in fields[1:] if name != alias)] if fields else []
            replacement = " ".join(fields)
            if replacement:
                output.append(replacement + (f" #{comment}" if sep else ""))
            # Drop an empty mapping line, including a stale THRUST marker.
            changed = True
        else:
            output.append(line)

    output_text = "\n".join(output).rstrip("\n")
    if output_text:
        output_text += "\n"
    output_text += f"{address}\t{alias}\t{MARKER}\n"
    if not found and text.replace("\r\n", "\n").endswith(output_text):
        return text, False
    # Compare normalized content, so repeated runs do not keep adding entries.
    normalized = text.replace("\r\n", "\n").rstrip("\n") + ("\n" if text else "")
    return (output_text, True) if output_text != normalized else (text, False)


def elevate_and_apply(address: str, alias: str) -> int:
    script = str(Path(__file__).resolve())
    if platform.system() == "Windows":
        import ctypes

        params = subprocess.list2cmdline([script, "--apply", address, alias])
        result = ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, params, None, 1)
        if result <= 32:
            print("Administrator permission was not granted; hosts file was not changed.", file=sys.stderr)
            return 1
        return 0
    if os.geteuid() != 0:
        try:
            os.execvp("sudo", ["sudo", sys.executable, script, "--apply", address, alias])
        except OSError as exc:
            print(f"Could not start sudo: {exc}", file=sys.stderr)
            return 1
    return apply_hosts(address, alias)


def apply_hosts(address: str, alias: str) -> int:
    path = hosts_path()
    try:
        original = path.read_text(encoding="utf-8")
        updated, changed = update_hosts_text(original, address, alias)
        if not changed:
            print(f"{alias} already points to {address}; no change needed.")
            return 0
        # Direct write preserves the existing file's permissions and Windows ACLs.
        with path.open("w", encoding="utf-8", newline="\n") as handle:
            handle.write(updated)
        print(f"Added {address} {alias} to {path}")
        print("Restart THRUST if it is already running.")
        return 0
    except (OSError, RuntimeError) as exc:
        print(f"Could not update hosts file {path}: {exc}", file=sys.stderr)
        return 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Configure a local THRUST WebDB hostname.")
    parser.add_argument("--apply", nargs=2, metavar=("IP", "ALIAS"), help=argparse.SUPPRESS)
    args = parser.parse_args()

    try:
        if args.apply:
            address = str(ipaddress.ip_address(args.apply[0]))
            alias = validate_alias(args.apply[1])
            return apply_hosts(address, alias)

        address = str(ipaddress.ip_address(input("WebDB server IP address: ").strip()))
        alias = validate_alias(input("Hostname alias to use on this computer (e.g. thrust.webdb): "))
        return elevate_and_apply(address, alias)
    except (ValueError, EOFError) as exc:
        print(f"Invalid input: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
