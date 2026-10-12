from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
import zipfile
from pathlib import Path


def wait_for_process(pid: int) -> None:
    while True:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return
        except PermissionError:
            pass
        time.sleep(0.25)


def safe_extract(archive: Path, destination: Path) -> Path:
    destination.mkdir(parents=True, exist_ok=True)
    if archive.suffix == ".zip":
        with zipfile.ZipFile(archive) as package:
            for item in package.infolist():
                target = (destination / item.filename).resolve()
                if destination.resolve() not in target.parents and target != destination.resolve():
                    raise RuntimeError("The update package contains an unsafe path.")
            package.extractall(destination)
    else:
        with tarfile.open(archive, "r:gz") as package:
            for item in package.getmembers():
                target = (destination / item.name).resolve()
                if destination.resolve() not in target.parents and target != destination.resolve():
                    raise RuntimeError("The update package contains an unsafe path.")
            package.extractall(destination)
    bundles = list(destination.glob("*.app"))
    return bundles[0] if bundles else destination


def overlay(source: Path, target: Path) -> None:
    updater_names = {"THRUST-updater", "THRUST-updater.exe"}
    for current, directories, files in os.walk(source):
        relative = Path(current).relative_to(source)
        target_dir = target / relative
        target_dir.mkdir(parents=True, exist_ok=True)
        directories[:] = [name for name in directories if name not in updater_names]
        for name in files:
            if name in updater_names:
                continue
            shutil.copy2(Path(current) / name, target_dir / name)


def restart(target: Path) -> None:
    if sys.platform == "darwin":
        subprocess.Popen(["open", "-a", str(target)], start_new_session=True)
    else:
        executable = target / "THRUST-measure"
        if sys.platform == "win32":
            executable = target / "THRUST-measure.exe"
        subprocess.Popen([str(executable)], cwd=str(target), start_new_session=True)


def elevate_if_needed(archive: Path, target: Path, pid: int) -> bool:
    if os.access(target, os.W_OK):
        return False
    args = [str(Path(sys.executable).resolve()), str(archive), str(target), str(pid)]
    if sys.platform.startswith("linux"):
        subprocess.run(["pkexec", *args], check=True)
        return True
    if sys.platform == "darwin":
        import shlex

        command = " ".join(shlex.quote(arg) for arg in args)
        applescript = f'do shell script "{command.replace(chr(34), chr(92) + chr(34))}" with administrator privileges'
        subprocess.run(["osascript", "-e", applescript], check=True)
        return True
    raise PermissionError(f"No permission to update {target}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("archive", type=Path)
    parser.add_argument("target", type=Path)
    parser.add_argument("pid", type=int)
    args = parser.parse_args()
    archive = args.archive.resolve()
    target = args.target.resolve()
    try:
        if elevate_if_needed(archive, target, args.pid):
            return 0
        wait_for_process(args.pid)
        with tempfile.TemporaryDirectory(prefix="thrust-update-stage-") as temporary:
            source = safe_extract(archive, Path(temporary))
            if not source.is_dir():
                raise RuntimeError("The update package is incomplete.")
            overlay(source, target)
        restart(target)
        archive.unlink(missing_ok=True)
        return 0
    except Exception as exc:
        print(f"THRUST-measure update failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
