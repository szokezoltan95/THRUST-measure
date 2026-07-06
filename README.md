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

## Running the Project

From the project root:

python main.py

This will start the THRUST launcher.


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
