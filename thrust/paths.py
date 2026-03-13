from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent

DOCUMENTS_DIR = Path.home() / "Documents"
APP_DATA_DIR = DOCUMENTS_DIR / "THRUST"

OUTPUT_ROOT_DIR = APP_DATA_DIR / "output"
SCOPE_OUTPUT_DIR = OUTPUT_ROOT_DIR / "scope"
SIMPLE_OUTPUT_DIR = OUTPUT_ROOT_DIR / "simple"

PROFILES_ROOT_DIR = PROJECT_ROOT / "profiles"
DEFAULT_PROFILES_DIR = PROFILES_ROOT_DIR / "defaults"
SCOPE_PROFILES_DIR = PROFILES_ROOT_DIR / "scope"
SIMPLE_PROFILES_DIR = PROFILES_ROOT_DIR / "simple"

DOCS_DIR = PROJECT_ROOT / "docs"
TESTS_DIR = PROJECT_ROOT / "tests"
ASSETS_DIR = PROJECT_ROOT / "thrust" / "assets"


def ensure_directory(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def ensure_app_directories() -> None:
    """
    Create all important runtime directories if they do not exist.
    """
    ensure_directory(APP_DATA_DIR)
    ensure_directory(OUTPUT_ROOT_DIR)
    ensure_directory(SCOPE_OUTPUT_DIR)
    ensure_directory(SIMPLE_OUTPUT_DIR)

    ensure_directory(PROFILES_ROOT_DIR)
    ensure_directory(DEFAULT_PROFILES_DIR)
    ensure_directory(SCOPE_PROFILES_DIR)
    ensure_directory(SIMPLE_PROFILES_DIR)