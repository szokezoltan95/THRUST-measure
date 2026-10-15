# THRUST-measure

**A research tool for structured measurement of UAV control performance.**

THRUST-measure presents repeatable **SCoPE** control tasks and **SimPLE** 2D flight tasks, records controller input and task events, and analyses each measurement. It is part of the THRUST research system developed at the Faculty of Aeronautics, Technical University of Košice.

> [!WARNING]
> **The Windows application is currently unsigned.** Windows SmartScreen may show **“Windows protected your PC”** or identify an unknown publisher when you run the installer. This warning is expected for an unsigned application; it does not independently confirm that a file is safe.
>
> Download the installer only from the [official GitHub Releases page](https://github.com/szokezoltan95/THRUST-measure/releases). Check that the repository and release are correct before proceeding. If you trust that official download, select **More info → Run anyway** to continue. On managed computers, your administrator may block this action.
>
> macOS may also require you to approve an app from an unidentified developer in **System Settings → Privacy & Security**. Only approve a copy downloaded from the official release page.

[![Latest release](https://img.shields.io/github/v/release/szokezoltan95/THRUST-measure?label=latest%20release)](https://github.com/szokezoltan95/THRUST-measure/releases/latest)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

## Download

Get the latest version from **[GitHub Releases](https://github.com/szokezoltan95/THRUST-measure/releases/latest)**. Choose the package for your operating system:

| Platform | Recommended download | Installation |
| --- | --- | --- |
| Windows 10/11, x64 | `THRUST-measure-*-windows-x64-setup.exe` | Run the setup wizard. It can add a Start menu entry and desktop shortcut. See the SmartScreen warning above. |
| Ubuntu/Debian, amd64 | `THRUST-measure-*-linux-amd64.deb` | Open the package with your software installer, or install it with your package manager. |
| macOS, Apple Silicon | `THRUST-measure-*-macos-arm64.pkg` | Open the package, complete installation, then launch the app from Applications. |
| macOS, Intel | `THRUST-measure-*-macos-x64.pkg` | Open the package, complete installation, then launch the app from Applications. |

ZIP and TAR.GZ packages are also available on the release page for users who prefer an archive. Installers include the application runtime and libraries: **you do not need to install Python** to use them.

### Update the app

Open **About** in THRUST-measure and select **Check for updates**. The app can show the available version and its release notes before you choose to install it. The updater downloads the package and applies the update; you do not need to manually find and install each new version.

## What it does

- **SCoPE** presents structured stick-to-target control tasks.
- **SimPLE** presents a two-dimensional UAV simulation.
- Supports compatible USB joysticks and radio controllers operating in USB joystick mode.
- Remembers axis assignments in joystick-specific profiles.
- Checks joystick readiness before a measurement, including required axis travel.
- Records time-stamped inputs and task events and can create local response graphs.
- Uploads measurements and analysis to THRUST-WebDB when connected.

THRUST-measure does not control a real aircraft. Its results describe performance in the selected tasks and conditions; on their own, they are not a certificate of real-world piloting ability or a universal measure of pilot competence.

## Using THRUST-WebDB

THRUST-measure is designed to work with **THRUST-WebDB**, which provides study accounts, participant IDs, test versions, shared result storage, and cohort comparisons. If you are taking part in a study, ask its organizer for the correct WebDB address, account, controller setup, and test instructions. Do not use another study's participant ID or test configuration.

The app communicates with WebDB through its HTTPS API. It does not connect directly to the database.

If the connection drops during upload, the app keeps pending measurements in a persistent local queue so they can be retried after connectivity returns. Measurement files and analysis are also saved locally under `Documents/THRUST/output`. Follow your study's consent and data-handling instructions when using or transferring these files.

## Controller support: TX16SMK3 LED rings

For LED ring control, the RadioMaster TX16SMK3 needs the project's [custom EdgeTX firmware](https://github.com/szokezoltan95/edgetx/tree/tx16smk3-pc-led-control). Connect the radio in USB joystick mode, open **Configure joystick…**, and enable **TX16SMK3 lights**. Use **Configure lights…** to set colors and animations. LED control is off by default; disabling it or closing THRUST-measure returns control to the radio.

## Installing from source

For a Windows source installation, download **Source code (zip)** from a release, extract it to a permanent folder, and run `install_thrust.bat`. This method requires Python 3.11 or newer and an internet connection to install dependencies. It creates a virtual environment and a desktop shortcut; keep the extracted folder in place.

For a development environment with Python 3.11 or newer:

```bash
python -m pip install -e ".[gui]"
thrust-measure
```

Run the test suite with:

```bash
python -m pytest -q
```

## Project information

THRUST-measure is developed at the **Faculty of Aeronautics, Technical University of Košice** as part of the THRUST research system.

- [Latest release and downloads](https://github.com/szokezoltan95/THRUST-measure/releases/latest)
- [Changelog](CHANGELOG.md)
- [License](LICENSE)

The THRUST-measure source code is available under the [MIT License](LICENSE). Third-party libraries and assets retain their own licenses.
