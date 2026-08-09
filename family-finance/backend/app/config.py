import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.environ.get("FAMILY_FINANCE_DATA_DIR", BASE_DIR / "data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)

DATABASE_URL = os.environ.get(
    "DATABASE_URL", f"sqlite:///{DATA_DIR / 'family_finance.db'}"
)

CORS_ORIGINS = os.environ.get("CORS_ORIGINS", "http://localhost:3000").split(",")
