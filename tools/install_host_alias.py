"""Add or update a local THRUST web server alias in the OS hosts file.

Run in an elevated Windows CMD or with sudo on Linux. The optional --hosts-file
argument is intended for tests and offline previews; it never changes DNS.
"""

from __future__ import annotations

import argparse
import ipaddress
import os
import platform
import re
import shutil
import sys
from pathlib import Path


def system_hosts_path(system: str | None = None) -> Path:
    system = system or platform.system()
    if system == "Windows":
        return Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "drivers" / "etc" / "hosts"
    if system == "Linux":
        return Path("/etc/hosts")
    raise ValueError(f"Nepodporovaný systém: {system}. Podporované sú Windows a Linux.")


def validated_ip(value: str) -> str:
    return str(ipaddress.ip_address(value.strip()))


def validated_alias(value: str) -> str:
    alias = value.strip().lower()
    if len(alias) > 253 or not alias or not all(
        re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label)
        for label in alias.split(".")
    ):
        raise ValueError("Alias musí byť názov hostiteľa bez protokolu, portu a cesty (napr. thrust-webdb.test).")
    return alias


def updated_hosts(content: bytes, ip: str, alias: str) -> bytes:
    """Preserve other hosts entries, comments, encoding bytes, and line endings."""
    name = alias.encode("ascii")
    newline = b"\r\n" if b"\r\n" in content else b"\n"
    lines = content.splitlines(keepends=True)
    found = []
    for line in lines:
        body = line.split(b"#", 1)[0].split()
        if len(body) >= 2 and name in (host.lower() for host in body[1:]):
            found.append(body)
    if len(found) == 1 and len(found[0]) == 2 and found[0][0] == ip.encode("ascii"):
        return content

    result = []
    for line in lines:
        base, hashmark, comment = line.rstrip(b"\r\n").partition(b"#")
        parts = base.split()
        if len(parts) < 2 or name not in (host.lower() for host in parts[1:]):
            result.append(line)
            continue
        others = [host for host in parts[1:] if host.lower() != name]
        ending = line[len(line.rstrip(b"\r\n")):]
        if others:
            result.append(parts[0] + b"\t" + b" ".join(others) +
                          (b"  #" + comment if hashmark else b"") + ending)
        elif hashmark and comment.strip() != b"THRUST":
            result.append(b"#" + comment + ending)
    output = b"".join(result)
    if output and not output.endswith((b"\n", b"\r")):
        output += newline
    return output + ip.encode("ascii") + b"\t" + name + b"  # THRUST" + newline


def install_alias(path: Path, ip: str, alias: str) -> bool:
    original = path.read_bytes()
    updated = updated_hosts(original, ip, alias)
    if updated == original:
        return False
    backup = path.with_name(path.name + ".thrust-backup")
    number = 1
    while backup.exists():
        backup = path.with_name(f"{path.name}.thrust-backup-{number}")
        number += 1
    shutil.copy2(path, backup)
    try:
        with path.open("r+b") as handle:
            handle.seek(0)
            handle.write(updated)
            handle.truncate()
            handle.flush()
            os.fsync(handle.fileno())
    except OSError:
        shutil.copy2(backup, path)
        raise
    return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Nastaví lokálny alias pre THRUST-webdb.")
    parser.add_argument("--ip", help="IP adresa servera; bez voľby sa opýta interaktívne")
    parser.add_argument("--alias", help="Lokálny názov, napr. thrust-webdb.test")
    parser.add_argument("--hosts-file", type=Path, help="Vlastný súbor pre skúšku; inak systémový hosts")
    args = parser.parse_args(argv)
    try:
        ip = validated_ip(args.ip if args.ip is not None else input("IP adresa servera: "))
        alias = validated_alias(args.alias if args.alias is not None else input("Lokálna adresa/alias (napr. thrust-webdb.test): "))
        path = args.hosts_file or system_hosts_path()
        changed = install_alias(path, ip, alias)
    except (ValueError, OSError, EOFError) as exc:
        print(f"Chyba: {exc}", file=sys.stderr)
        print("Na úpravu systémového hosts spusti CMD ako správca alebo použi sudo na Linuxe.", file=sys.stderr)
        return 1
    print(f"{'Zapísané' if changed else 'Už nastavené'}: {ip} {alias} ({path})")
    if changed:
        print(f"Pôvodný hosts je zálohovaný v priečinku {path.parent} (hosts.thrust-backup*).")
    print(f"Adresa webu: http://{alias}:8080 (ak server používa port 8080)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
