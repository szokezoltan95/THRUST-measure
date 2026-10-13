import ctypes
import os
import sys
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from scripts import thrust_updater

from thrust.updater import expected_asset_suffix, find_update_asset, is_newer_version


@pytest.mark.parametrize(
    ("candidate", "installed", "expected"),
    [
        ("1.2.0", "1.1.9", True),
        ("1.10.0", "1.9.9", True),
        ("1.2.0", "1.2", False),
        ("1.1.9", "1.2.0", False),
    ],
)
def test_is_newer_version(candidate, installed, expected):
    assert is_newer_version(candidate, installed) is expected


@pytest.mark.parametrize(
    ("system", "machine", "suffix"),
    [
        ("win32", "AMD64", "-windows-x64.zip"),
        ("linux", "x86_64", "-linux-amd64.tar.gz"),
        ("darwin", "arm64", "-macos-arm64.zip"),
        ("darwin", "x86_64", "-macos-x64.zip"),
    ],
)
def test_expected_asset_suffix(system, machine, suffix):
    assert expected_asset_suffix(system, machine) == suffix


def test_find_update_asset_uses_platform_specific_release_asset():
    release = {
        "assets": [
            {"name": "THRUST-measure-1.3.0-windows-x64.zip"},
            {"name": "THRUST-measure-1.3.0-linux-amd64.tar.gz"},
        ]
    }
    assert find_update_asset(release, "-linux-amd64.tar.gz")["name"].endswith(
        "-linux-amd64.tar.gz"
    )


def test_find_update_asset_fails_if_platform_package_is_missing():
    with pytest.raises(RuntimeError, match="does not include"):
        find_update_asset({"assets": []}, "-macos-arm64.zip")



def test_windows_wait_for_process_uses_native_wait(monkeypatch):
    kernel32 = SimpleNamespace(
        OpenProcess=Mock(return_value=1234),
        WaitForSingleObject=Mock(return_value=0),
        CloseHandle=Mock(return_value=True),
    )
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(ctypes, "WinDLL", lambda *_args, **_kwargs: kernel, raising=False)
    monkeypatch.setattr(os, "kill", lambda *_args: pytest.fail("os.kill must not be used on Windows"))

    thrust_updater.wait_for_process(5678)

    kernel32.OpenProcess.assert_called_once_with(0x00100000, False, 5678)
    kernel32.WaitForSingleObject.assert_called_once_with(1234, 0xFFFFFFFF)
    kernel32.CloseHandle.assert_called_once_with(1234)


def test_windows_wait_for_process_returns_if_app_already_exited(monkeypatch):
    kernel32 = SimpleNamespace(
        OpenProcess=Mock(return_value=None),
        WaitForSingleObject=Mock(),
        CloseHandle=Mock(),
    )
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(ctypes, "WinDLL", lambda *_args, **_kwargs: kernel32, raising=False)
    monkeypatch.setattr(ctypes, "get_last_error", lambda: 87, raising=False)

    thrust_updater.wait_for_process(5678)

    kernel32.WaitForSingleObject.assert_not_called()
    kernel32.CloseHandle.assert_not_called()
