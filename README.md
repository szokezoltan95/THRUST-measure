# THRUST

**THRUST (Testing Hub for Research in UAV Simulation and Training)** is a modular platform for UAV control training, human performance experiments, and flight control evaluation.

The system integrates multiple experimental tools into a single environment with a unified configuration interface.

Currently supported modules:

- **SCoPE** – control performance experiment platform
- **SimPLE** – lightweight UAV dynamics simulator


---

## Project Goals

THRUST is designed to support research and training in:

- UAV manual control
- pilot skill development
- human‑machine interaction
- flight control behaviour analysis
- experimental evaluation of control interfaces

The platform focuses on:

- lightweight simulations
- reproducible experiments
- configurable experimental setups
- structured data collection


---

## Architecture Overview

Project structure:

THRUST
│
├─ thrust      # main framework and launcher
├─ scope       # SCoPE experiment module
├─ simple      # SimPLE UAV simulator
├─ profiles    # experiment configuration profiles
├─ docs        # documentation
└─ tests       # automated tests


---

## Modules

### SCoPE
SCoPE is an experimental platform used to evaluate pilot control performance.

It measures:

- tracking accuracy
- response time
- stability
- control error metrics
- learning progress over time


### SimPLE
SimPLE is a lightweight UAV dynamics simulator used for training and behavioural experiments.

Features:

- configurable UAV physics
- 2D motion simulation
- configurable maneuver workspace
- customizable visual environment
- joystick control


---

## Experiment Outputs

Experimental results are stored outside the repository.

Default location:

Documents/THRUST


Example structure:

Documents/THRUST
│
├─ scope
│   └─ 2026-03-13
│
└─ simple
    └─ 2026-03-13


Raw experiment data are stored as CSV or JSON files for later analysis.


---

## Configuration Profiles

Experiment configurations are stored in:

profiles/

Profiles allow reproducible experiments and easy switching between setups.


---

## Install and run on Windows

Clone the repository, then double-click `install_thrust.bat` in its root folder. The installer reports each step, selects the newest supported Python 3.11+ installation it can find (including installations registered with the `py` launcher), creates `.venv`, and installs the GUI dependencies declared in `pyproject.toml`.

It creates a **THRUST-measure** shortcut on the Windows Desktop. The shortcut uses the `thrust-measure` GUI entry point, so it opens the application without showing a Command Prompt window. The installation is editable: after pulling source changes, run the desktop shortcut again; rerun `install_thrust.bat` after dependency changes.

The traditional console entry point remains available as `thrust` inside the virtual environment for development and troubleshooting.



---

## Development Status

Early development stage.

Current focus:

- core architecture
- configuration system
- PyQt launcher
- integration of SCoPE and SimPLE


---

## License

Research / academic use.
License to be defined.


## Import old or offline measurements

The standalone importer searches recursively in `Documents/THRUST/import`. Put historical logs there and double-click `import_measurements.bat`. It recognizes SCoPE and SimPLE filenames containing a five-character participant ID, runs the same SCoPE/SimPLE analysis functions as THRUST-measure, creates missing participants, reuses a matching test code/version when possible, and otherwise creates a `LEGACY_…` test version. It uploads the compressed raw log and analysis to WebDB; the original local log is kept unchanged.

Try a preview first:

```bat
import_measurements.bat --dry-run
```

To keep the tool running and automatically upload completed offline measurements, start:

```bat
import_measurements.bat --watch
```

Watch mode checks the import folder and `Documents/THRUST/output` every five seconds. It waits until a file has stopped changing, then analyzes and uploads it. Stop it with `Ctrl+C`. The importer asks for the WebDB username and password; alternatively set `THRUST_WEBDB_USERNAME` and `THRUST_WEBDB_PASSWORD` in the environment. Use an Admin or SuperAdmin account so it can create missing participants, or a Researcher account when every participant already exists. The WebDB URL can be changed with `--webdb`.

Each raw log is paired with a versioned `.analysis.json` file beside it. Uploaded files are detected by their raw-content hash, so a later scan skips an identical log already in WebDB.
