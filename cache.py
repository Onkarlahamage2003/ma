"""
Local price history cache (SQLite).

Every time the app fetches live prices for a commodity, it saves them here too.
Next time the same commodity is requested, the cache is merged with the fresh
pull, so the effective history keeps growing the longer the app stays running
and gets used — rather than being capped by whatever data.gov.in returns in
one call.

CAVEAT: on free hosting tiers (e.g. Render's free web service), the filesystem
is usually wiped on redeploy/restart, so the cache resets too. For a laptop
that stays on, or a host with a persistent disk, it keeps accumulating for real.
For production-grade persistence, swap this for a small hosted Postgres
(Neon/Supabase both have free tiers) — same functions, different connection.
"""

import sqlite3
from pathlib import Path
import pandas as pd

DB_PATH = Path(__file__).parent / "price_cache.db"


def init_db():
    con = sqlite3.connect(DB_PATH)
    con.execute("""
        CREATE TABLE IF NOT EXISTS prices (
            commodity TEXT NOT NULL,
            market TEXT,
            date TEXT NOT NULL,
            modal_price REAL NOT NULL,
            PRIMARY KEY (commodity, market, date)
        )
    """)
    con.commit()
    con.close()


def save_records(commodity: str, df: pd.DataFrame):
    """df needs columns: arrival_date (datetime), market, modal_price."""
    if df.empty:
        return
    con = sqlite3.connect(DB_PATH)
    rows = [
        (commodity, r.get("market"), r["arrival_date"].strftime("%Y-%m-%d"), float(r["modal_price"]))
        for _, r in df.iterrows()
    ]
    con.executemany(
        "INSERT OR REPLACE INTO prices (commodity, market, date, modal_price) VALUES (?, ?, ?, ?)",
        rows,
    )
    con.commit()
    con.close()


def load_history(commodity: str, days: int = 730) -> pd.DataFrame:
    """Returns daily-averaged modal price for this commodity from the cache."""
    con = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query(
        "SELECT date, modal_price FROM prices WHERE commodity = ? ORDER BY date",
        con, params=(commodity,),
    )
    con.close()
    if df.empty:
        return df
    df["date"] = pd.to_datetime(df["date"])
    cutoff = df["date"].max() - pd.Timedelta(days=days)
    df = df[df["date"] >= cutoff]
    return df.groupby("date")["modal_price"].mean().rename("modal_price").reset_index()
