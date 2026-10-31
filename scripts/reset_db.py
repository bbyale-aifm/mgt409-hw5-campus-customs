"""Reset data/campus_customs_new.db to the original values in data/campus_customs.db.

Run before every full ticket-resolution run:  python scripts/reset_db.py
The original database is opened read-only and is never modified.
"""
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common.config import DB_PATH, ORIGINAL_DB  # noqa: E402


def reset() -> None:
    src = sqlite3.connect(f"file:{ORIGINAL_DB}?mode=ro", uri=True)
    for suffix in ("", "-wal", "-shm", "-journal"):
        Path(str(DB_PATH) + suffix).unlink(missing_ok=True)
    dst = sqlite3.connect(DB_PATH)
    src.backup(dst)
    dst.close()
    src.close()


if __name__ == "__main__":
    reset()
    con = sqlite3.connect(DB_PATH)
    today = con.execute("select date_today from desk").fetchone()[0]
    cash = con.execute("select balance from cash_accounts").fetchone()[0]
    con.close()
    print(f"Reset {DB_PATH.name} from {ORIGINAL_DB.name}: today={today}, checking=${cash:,.2f}")
