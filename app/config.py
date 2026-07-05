from pathlib import Path

APP_NAME = "MemoryFlow"
APP_VERSION = "0.1.0"

ROOT_DIR = Path(__file__).resolve().parent.parent
DATABASE_DIR = ROOT_DIR / "database"
POEMS_DIR = ROOT_DIR / "poems"
ASSETS_DIR = ROOT_DIR / "assets"
LOG_DIR = ROOT_DIR / "logs"

DATABASE_DIR.mkdir(exist_ok=True)
POEMS_DIR.mkdir(exist_ok=True)
ASSETS_DIR.mkdir(exist_ok=True)
LOG_DIR.mkdir(exist_ok=True)

DATABASE_FILE = DATABASE_DIR / "memory.db"

DEFAULT_NEW_POEMS = 1
DEFAULT_REVIEW_LIMIT = 50

WINDOW_WIDTH = 1100
WINDOW_HEIGHT = 750

STUDY_SESSION_THRESHOLD_MINUTES = 1
