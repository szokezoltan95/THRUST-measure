import pytest

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
