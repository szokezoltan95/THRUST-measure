# THRUST-measure

THRUST-measure is a desktop application for structured research into how people control unmanned aircraft. It is part of the **THRUST** research system (Testing Hub for Research in UAV Simulation and Training), developed at the Faculty of Aeronautics, Technical University of Košice.

## Why THRUST exists

Research on UAV control needs repeatable tasks and measurements. THRUST gives a study team a way to configure the same test for participants, record their control inputs and responses, and compare results across a study. A consistent test setup makes comparisons more meaningful than asking participants to fly under different conditions.

THRUST-measure is a research instrument. Its results describe performance in the selected tasks and conditions; they are not, by themselves, a certificate of real-world piloting ability or a universal score of pilot competence.

## What participants do

Participants use a compatible USB joystick or radio controller in joystick mode to complete one of two types of task:

- **SCoPE** presents structured control tasks and records how the participant responds to requested control inputs.
- **SimPLE** presents a two-dimensional UAV simulation and records control during simulated flight tasks.

The application records the control data and produces measurement results for the research study. It does not control a real aircraft.

## THRUST WebDB is central to the research workflow

THRUST-measure is designed to work with **THRUST-WebDB**. WebDB provides the study's participant accounts and IDs, test versions, measurement upload, result storage, and cohort comparisons. The study team uses it to make sure participants perform the intended test version and to collect comparable results in one place.

For meaningful research use, connect to the WebDB instance provided by your study team and sign in with the account they give you. Without WebDB, local mode can run tasks using local profiles, but it does not provide shared participant and test management, central result storage, or cohort comparisons. THRUST-measure is therefore not intended as a standalone general-purpose simulator.

If you are joining a study, ask its organizer for access to the correct WebDB and instructions for the test and controller. Do not use another study's participant ID or test configuration.

## How the system works

THRUST is made up of two cooperating parts:

1. **THRUST-measure** runs on the participant's computer. It connects to a joystick or radio controller, presents the selected SCoPE or SimPLE task, records time-stamped control inputs and task events, and calculates the per-measurement analysis.
2. **THRUST-WebDB** coordinates the study. The desktop app signs in to the WebDB service over HTTPS to obtain participant and test information and to upload completed results. The app communicates with the service through its web API; it does not connect directly to the database.

The WebDB service has a web interface, an API, and a PostgreSQL database. It manages accounts and permissions, participants, test versions, and saved measurements. It also provides study-level and cohort comparisons.

### What is recorded

After a session, THRUST-measure saves a compressed raw measurement log and a separate analysis file in the user's `Documents/THRUST/output` folder. Depending on the task, these contain controller inputs, requested actions, timing, task events, and calculated measures such as response and tracking performance.

When connected to WebDB, the app uploads the measurement and its analysis to the selected study. The server checks and stores the submitted result; it does not repeat the per-measurement calculations. Group statistics and comparisons are handled separately in WebDB.

### Keeping test results comparable

A WebDB test version identifies the test configuration participants should perform. The result is associated with that version and its analysis settings, so researchers can distinguish measurements made under different conditions. Comparisons are most useful when participants use the same test version, controller setup, and procedure.

Measurements are associated with participant IDs and stored under the study's WebDB access rules. Follow the study team's instructions and consent information when collecting or handling participant data.

## Installation

Download the package for your computer from [Releases](https://github.com/szokezoltan95/THRUST-measure/releases).

| Platform | Installer | How to start |
| --- | --- | --- |
| Windows x64 | `*-windows-x64-setup.exe` | Run the setup wizard. It adds a Start menu entry and can add a desktop shortcut. |
| Ubuntu/Debian amd64 | `*-linux-amd64.deb` | Open the package with your package manager, then launch THRUST-measure from the applications menu. |
| macOS Intel | `*-macos-x64.pkg` | Run the installer, open the app in Applications, and optionally add it to the Dock. |
| macOS Apple Silicon | `*-macos-arm64.pkg` | Run the installer, open the app in Applications, and optionally add it to the Dock. |

The installers include the Python runtime and application libraries. You do not need to install Python, Git, or a virtual environment to use them.

The Windows and macOS installers are not currently signed. Windows may show a SmartScreen warning, and macOS may ask you to approve the app in System Settings before opening it. Only install a copy obtained from the project's official release page.

### Windows source installation

If you prefer to use the source package, download the **Source code (zip)** from a release, extract it to a permanent folder, and run `install_thrust.bat`. This method requires Python 3.11 or newer and an internet connection to install the required libraries. It creates a virtual environment in the extracted folder and a desktop shortcut that points to it. Keep that folder in place after installation.

## License

THRUST-measure source code is available under the [MIT License](LICENSE). Third-party libraries and assets retain their own licenses.
