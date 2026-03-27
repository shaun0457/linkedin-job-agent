import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "jobs.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS seen_jobs (
    job_id              TEXT PRIMARY KEY,
    title               TEXT NOT NULL,
    company             TEXT NOT NULL,
    url                 TEXT NOT NULL UNIQUE,
    status              TEXT NOT NULL DEFAULT 'notified',
    preview_data        TEXT,           -- JSON blob of full ImproveResumeData
    rm_job_id           TEXT,           -- RM's internal job_id
    master_resume_id    TEXT,           -- master resume used for tailoring
    confirmed_resume_id TEXT,
    notified_at         TEXT NOT NULL,
    decided_at          TEXT
);

CREATE TABLE IF NOT EXISTS search_config (
    key     TEXT PRIMARY KEY,
    value   TEXT NOT NULL
);
"""

_MIGRATE_ADD_COLUMNS = [
    "ALTER TABLE seen_jobs ADD COLUMN preview_data TEXT",
    "ALTER TABLE seen_jobs ADD COLUMN rm_job_id TEXT",
    "ALTER TABLE seen_jobs ADD COLUMN master_resume_id TEXT",
]


@contextmanager
def _conn():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    try:
        yield con
        con.commit()
    finally:
        con.close()


def init_db() -> None:
    with _conn() as con:
        con.executescript(SCHEMA)
        # migrate existing DBs that have the old schema
        for stmt in _MIGRATE_ADD_COLUMNS:
            try:
                con.execute(stmt)
            except sqlite3.OperationalError:
                pass  # column already exists


# ── seen_jobs ──────────────────────────────────────────────────────────────


def is_seen(job_id: str, url: str) -> bool:
    with _conn() as con:
        row = con.execute(
            "SELECT 1 FROM seen_jobs WHERE job_id = ? OR url = ?", (job_id, url)
        ).fetchone()
        return row is not None


def insert_job(
    job_id: str,
    title: str,
    company: str,
    url: str,
    preview_data: dict,
    rm_job_id: str,
    master_resume_id: str,
    notified_at: str,
) -> None:
    with _conn() as con:
        con.execute(
            """INSERT OR IGNORE INTO seen_jobs
               (job_id, title, company, url, status,
                preview_data, rm_job_id, master_resume_id, notified_at)
               VALUES (?, ?, ?, ?, 'notified', ?, ?, ?, ?)""",
            (
                job_id, title, company, url,
                json.dumps(preview_data),
                rm_job_id,
                master_resume_id,
                notified_at,
            ),
        )


def get_preview_data(job_id: str) -> dict | None:
    """Return full preview_data dict, or None if not found / already cleared."""
    with _conn() as con:
        row = con.execute(
            "SELECT preview_data FROM seen_jobs WHERE job_id = ?", (job_id,)
        ).fetchone()
        if row and row["preview_data"]:
            return json.loads(row["preview_data"])
        return None


def get_job_meta(job_id: str) -> dict | None:
    """Return rm_job_id and master_resume_id for a job."""
    with _conn() as con:
        row = con.execute(
            "SELECT rm_job_id, master_resume_id FROM seen_jobs WHERE job_id = ?",
            (job_id,),
        ).fetchone()
        return dict(row) if row else None


def confirm_job(job_id: str, confirmed_resume_id: str, decided_at: str) -> None:
    with _conn() as con:
        con.execute(
            """UPDATE seen_jobs
               SET status = 'confirmed', confirmed_resume_id = ?, decided_at = ?
               WHERE job_id = ?""",
            (confirmed_resume_id, decided_at, job_id),
        )


def skip_job(job_id: str, decided_at: str) -> None:
    with _conn() as con:
        con.execute(
            """UPDATE seen_jobs
               SET status = 'skipped', preview_data = NULL, decided_at = ?
               WHERE job_id = ?""",
            (decided_at, job_id),
        )


def get_stats(since: str) -> dict[str, int]:
    with _conn() as con:
        rows = con.execute(
            """SELECT status, COUNT(*) as n FROM seen_jobs
               WHERE notified_at >= ? GROUP BY status""",
            (since,),
        ).fetchall()
        return {r["status"]: r["n"] for r in rows}


def get_recent_confirmed(limit: int = 10) -> list[dict]:
    with _conn() as con:
        rows = con.execute(
            """SELECT job_id, title, company, confirmed_resume_id
               FROM seen_jobs WHERE status = 'confirmed'
               ORDER BY decided_at DESC LIMIT ?""",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]


# ── search_config ──────────────────────────────────────────────────────────


def get_config_value(key: str) -> str | None:
    with _conn() as con:
        row = con.execute(
            "SELECT value FROM search_config WHERE key = ?", (key,)
        ).fetchone()
        return row["value"] if row else None


def set_config_value(key: str, value: str) -> None:
    with _conn() as con:
        con.execute(
            "INSERT OR REPLACE INTO search_config (key, value) VALUES (?, ?)",
            (key, value),
        )


def get_search_overrides() -> dict[str, object]:
    """Return all DB overrides as a dict (values are JSON-decoded)."""
    with _conn() as con:
        rows = con.execute("SELECT key, value FROM search_config").fetchall()
        return {r["key"]: json.loads(r["value"]) for r in rows}
