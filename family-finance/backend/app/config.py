import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.environ.get("FAMILY_FINANCE_DATA_DIR", BASE_DIR / "data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)

DATABASE_URL = os.environ.get(
    "DATABASE_URL", f"sqlite:///{DATA_DIR / 'family_finance.db'}"
)

# localhost and 127.0.0.1 are different origins to a browser's CORS check even
# though they point at the same machine — allow both by default so opening
# either in the address bar doesn't produce a confusing "Failed to fetch".
_DEFAULT_CORS_ORIGINS = "http://localhost:3000,http://127.0.0.1:3000"
CORS_ORIGINS = os.environ.get("CORS_ORIGINS", _DEFAULT_CORS_ORIGINS).split(",")
