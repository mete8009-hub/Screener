from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
LEGACY_DIR = DATA_DIR / "legacy"
DB_PATH = DATA_DIR / "fund_manager_workstation.db"
APP_TITLE = "Fund Manager Workstation"
SEED_VERSION = "v1"
BUSINESS_DAYS = 756  # ~3 years
