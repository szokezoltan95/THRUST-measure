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

## Windows installation

Clone the repository and double-click `install_thrust.bat`. Read the displayed
license notice and choose **Y** to continue. The installer finds a supported
Python 3.11+ installation, creates `.venv`, installs the GUI dependencies,
and creates a **THRUST-measure** desktop shortcut. Choose **N** to exit before
installation. The full terms are in [EULA.txt](EULA.txt) and [LICENSE](LICENSE).

The shortcut starts the GUI without a console window. Following `git pull`,
launch the shortcut to run updated editable source. Rerun the installer after
changes to `pyproject.toml` or the Python environment. The terminal entry point
`thrust` remains available inside `.venv` for troubleshooting.

For development on another platform:

```console
python -m venv .venv
.venv/bin/python -m pip install -e '.[gui]'
.venv/bin/python -m thrust.app
```

On Windows, replace `.venv/bin/python` with `.venv\Scripts\python.exe`.
The `thrust-measure` GUI entry point is installed with the `gui` extra.

## WebDB connection and profiles

Connect using your WebDB credentials, select an active test version and a
participant ID, then assign joystick axes using the Axis assignment dialog.
In offline mode, the SCoPE/SimPLE settings come from local profiles. Test
versions and their analysis configuration should be kept with each result so
later changes do not alter historical interpretation.

## Import older or offline logs

Put historical files in `Documents/THRUST/import` and run
`import_measurements.bat --dry-run` for a preview. The importer recognizes
SCoPE/SimPLE logs with a five-character participant ID, runs the same
analysis pipeline, creates missing participants when authorized, and reuses a
matching test version or creates a `LEGACY_…` test version. The originals are
kept locally. Run `import_measurements.bat --watch` to scan import and output
folders continuously, or use the **Legacy files** action in the launcher.
The importer requests WebDB credentials unless supplied through
`THRUST_WEBDB_USERNAME` and `THRUST_WEBDB_PASSWORD`; `--webdb` overrides the
server address.

## License

Copyright © 2026 Zoltán Szőke. Source code is licensed under the
[MIT License](LICENSE). The installer displays [EULA.txt](EULA.txt) before
making changes to the computer. Third-party dependencies retain their own
applicable licenses.
