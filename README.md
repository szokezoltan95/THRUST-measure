# THRUST-measure

THRUST (Testing Hub for Research in UAV Simulation and Training) is a desktop
measurement client for UAV control research. Its PyQt6 launcher configures the
joystick, selects an online WebDB test or an offline profile, and starts the
Pygame-based SCoPE and SimPLE experiments.

## Modules and results

- **SCoPE** measures control response, tracking error, reaction, and stability.
- **SimPLE** simulates a 2D UAV with configurable dynamics and boundaries.
- Each recording produces a compressed raw log and adjacent versioned
  `.analysis.json` file in `Documents/THRUST/output`. The analysis includes
  statistics, events, quality flags, and normalized response curves.
- WebDB validates the raw hash and saved analysis, stores individual results
  without recalculating them, and computes group comparisons separately.

## Install version 1.0

Download the installer for your system from [Releases](https://github.com/szokezoltan95/THRUST-measure/releases).
These packages contain Python and all required application libraries. You do
not need Git, a system Python installation, pip, or a separate virtual
environment.

| Platform | Package | Installation |
| --- | --- | --- |
| Windows x64 | `*-windows-x64-setup.exe` | Run the wizard, accept the license and select a destination. A Start menu entry and optional desktop shortcut are created. |
| Ubuntu/Debian amd64 | `*-linux-amd64.deb` | Open with your package manager, or run `sudo apt install ./THRUST-measure-1.0.0-linux-amd64.deb`. Launch from the application menu. To put an icon on the desktop, copy `/usr/share/applications/thrust-measure.desktop` to `~/Desktop/` and mark it trusted in the desktop environment. |
| macOS Intel or Apple Silicon | `*-macos-x64.pkg` or `*-macos-arm64.pkg` | Run the installer to place the app in Applications; drag it from Applications to the Dock for a shortcut. |

The macOS packages are currently unsigned and not notarized. macOS may
prevent launching them until the user explicitly permits the app in System
Settings. The Windows package is also unsigned and may show a SmartScreen
warning. Distribution signing is planned for a later build.

The old `install_thrust.bat` is still available for a source checkout. It
creates `.venv` in the checkout and installs dependencies there; it is not
needed for these standalone installers. Updates to the installed application
come from a new installer release, not from `git pull`.

## Development from source

```console
python -m venv .venv
.venv/bin/python -m pip install -e '.[gui]'
.venv/bin/thrust-measure
```

On Windows, use `.venv\Scripts\python.exe` for Python commands and
`.venv\Scripts\thrust-measure.exe` for the GUI entry point.

## WebDB connection and profiles

Connect using your WebDB credentials, select an active test version and a
participant ID, then assign joystick axes using the Axis assignment dialog.
In offline mode, the SCoPE/SimPLE settings come from local profiles. Test
versions and their analysis configuration should be kept with each result so
later changes do not alter historical interpretation.

## Import older or offline logs

Put historical files in `Documents/THRUST/import` and run
`import_measurements.bat --dry-run` from a source checkout for a preview.
The importer recognizes SCoPE/SimPLE logs with a five-character participant
ID, runs the same analysis pipeline, creates missing participants when
authorized, and reuses a matching test version or creates a `LEGACY_…` test
version. The originals are kept locally. Run
`import_measurements.bat --watch` to scan import and output folders
continuously, or use the **Legacy files** action in the launcher.
The importer requests WebDB credentials unless supplied through
`THRUST_WEBDB_USERNAME` and `THRUST_WEBDB_PASSWORD`; `--webdb` overrides
the server address.

## Release process

The `release/v1.0.0` branch runs tests and builds the four platform packages
in GitHub Actions. The publish job creates tag `v1.0.0` and the release only
after every package job succeeds. The packages use PyInstaller to bundle the
interpreter and dependencies; the development installation keeps its venv.
The release workflow and platform packaging definitions are under
`.github/workflows/release.yml` and `packaging/`.

## License

Copyright © 2026 Zoltán Szőke. Source code is licensed under the
[MIT License](LICENSE). The installer displays [EULA.txt](EULA.txt) before
making changes to the computer. Third-party dependencies retain their own
applicable licenses.
