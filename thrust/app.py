import sys
from pathlib import Path

from thrust.paths import ensure_app_directories


def main() -> int:
    """
    Main entry point for the THRUST application.
    For now, this only prepares required directories and prints
    a simple startup message. PyQt UI will be connected next.
    """
    ensure_app_directories()

    print("THRUST started successfully.")
    print(f"Project root: {Path(__file__).resolve().parent.parent}")

    return 0