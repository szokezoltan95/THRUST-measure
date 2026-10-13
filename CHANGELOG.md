# Changelog

## 1.2.4

### In-app updates
- About now shows the installed version and clearly states the update path, for example **1.2.3 → 1.2.4**.
- Update release notes from GitHub are shown before installation, with a separate button to apply the update.
- Published this as a stable update so existing 1.2.3 installations can discover and install the updater improvements. The previous updater could only check stable releases and could not parse prerelease version tags.

## 1.2.3b

### In-app update test build
- Added the installed application version and a clear source-to-target version status to the About window.
- Renamed the update action to **Check for updates** and added a separate install button so the release notes can be reviewed first.
- Displayed the GitHub release changelog in the About window when an update is found.
- Included prereleases in update checks to verify the end-to-end updater flow.

## 1.2.3

### Windows in-app update fix
- Fixed the updater waiting for the THRUST-measure process: Windows now waits on a native process handle instead of using a POSIX-style PID signal check that failed with WinError 87.
- Built the Windows update helper without a console window, avoiding the brief CMD flash during updates.
- If an update fails, the helper now shows an error dialog and saves diagnostic details to `%LOCALAPPDATA%\THRUST-measure\update.log`.
- Added regression tests for Windows process waiting and the case where the app has already exited.

## 1.2.2

### Joystick configuration
- Axis assignments are now remembered per joystick using its SDL/USB GUID, with the published device name as a fallback when a GUID is unavailable.
- When a previously configured joystick is connected, its saved LX, LY, RX, RY, BREAK, and RESET mapping is restored automatically.
- Reordered joystick axis displays and assignment controls to LX, LY, RX, RY.

### Interface
- Moved the Updates control from the main window into About. Automatic daily update checks remain enabled, and an available version is shown on that button.

### Release
- Added regression tests for joystick profile identity and mapping persistence.

## 1.2.1

### In-app updates
- Added an **Updates** button and automatic checks for stable GitHub releases at app startup, at most once per day.
- The app downloads the update archive for the current platform and verifies its SHA-256 digest before applying it.
- A bundled update helper replaces the application files after the app closes, then starts the updated version.
- macOS and Linux may request administrator authorization when the app is installed in a protected system folder.

### Release packages
- Added self-update archives for Windows x64, Linux amd64, and macOS x64 and arm64, while keeping the existing installers for new installations.
- Included package version metadata in the frozen builds so the app can compare its installed version with GitHub Releases.
- Added tests for version comparison and platform-specific update package selection.

### Upgrade note
- Users upgrading from 1.2.0 need to install 1.2.1 once with the usual package. Later releases can be applied from the app.



