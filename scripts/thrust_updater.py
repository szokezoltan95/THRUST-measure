from __future__ import annotations

import argparse
import ctypes
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
import traceback
import zipfile
from pathlib import Path


def wait_for_process(pid: int) -> None:
    if sys.platform == "win32":
        from ctypes import wintypes

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel32.OpenProcess.restype = wintypes.HANDLE
        kernel32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        kernel32.WaitForSingleObject.restype = wintypes.DWORD
        kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel32.CloseHandle.restype = wintypes.BOOL

        synchronize = 0x00100000
        handle = kernel32.OpenProcess(synchronize, False, pid)
        if not handle:
            error = ctypes.get_last_error()
            # The app may have exited before this helper started waiting.
            if error in {87, 1168}:  # ERROR_INVALID_PARAMETER / ERROR_NOT_FOUND
                return
            raise ctypes.WinError(error)
        try:
            result = kernel32.WaitForSingleObject(handle, 0xFFFFFFFF)
            if result == 0xFFFFFFFF:  # WAIT_FAILED
                raise ctypes.WinError(ctypes.get_last_error())
        finally:
            kernel32.CloseHandle(handle)
        return

    while True:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return
        except PermissionError:
            pass
        time.sleep(0.25)


def report_failure(error: Exception) -> None:
    details = f"THRUST-measure update failed: {error}\n\n{traceback.format_exc()}"
    if sys.platform == "win32":
        log_root = Path(os.environ.get("LOCALAPPDATA", tempfile.gettempdir())) / "THRUST-measure"
    else:
        log_root = Path.home() / "Documents" / "THRUST"
    log_path = log_root / "update.log"
    try:
        log_root.mkdir(parents=True, exist_ok=True)
        log_path.write_text(details, encoding="utf-8")
    except OSError:
        log_path = Path(tempfile.gettempdir()) / "THRUST-measure-update.log"
        try:
            log_path.write_text(details, encoding="utf-8")
        except OSError:
            pass

    message = f"The update could not be installed.\n\n{error}\n\nDetails: {log_path}"
    if sys.platform == "win32":
        try:
            from ctypes import wintypes

            message_box = ctypes.WinDLL("user32", use_last_error=True).MessageBoxW
            message_box.argtypes = [wintypes.HWND, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.UINT]
            message_box.restype = wintypes.INT
            message_box(None, message, "THRUST-measure update", 0x10)
            return
        except Exception:
            pass
    if sys.stderr is not None:
        print(details, file=sys.stderr)


def safe_extract(archive: Path, destination: Path) -> Path:
    destination.mkdir(parents=True, exist_ok=True)
    if archive.suffix == ".zip":
        with zipfile.ZipFile(archive) as package:
            for item in package.infolist():
                target = (destination / item.filename).resolve()
                if destination.resolve() not in target.parents and target != destination.resolve():
                    raise RuntimeError("The update package contains an unsafe path.")
            if sys.platform == "darwin":
                # ditto preserves app-bundle symlinks and metadata from the release ZIP.
                subprocess.run(
                    ["ditto", "-x", "-k", str(archive), str(destination)],
                    check=True,
                )
            else:
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

    def ignore_running_updater(_directory: str, names: list[str]) -> set[str]:
        return updater_names.intersection(names)

    # Preserve symlinks within macOS bundles and Linux PyInstaller builds.
    shutil.copytree(
        source,
        target,
        dirs_exist_ok=True,
        symlinks=True,
        ignore=ignore_running_updater,
    )

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
        report_failure(exc)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

