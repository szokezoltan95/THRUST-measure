# Changelog

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
