import json
import sqlite3
from pathlib import Path
from datetime import datetime, timezone


DB_PATH = Path(__file__).parent.parent.parent.parent / "paperscout.db"


def get_connection(db_path: Path = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db(db_path: Path = DB_PATH) -> None:
    conn = get_connection(db_path)
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS papers (
            id              TEXT PRIMARY KEY,
            title           TEXT NOT NULL,
            authors         TEXT,
            abstract        TEXT,
            source          TEXT NOT NULL,
            url             TEXT,
            pdf_url         TEXT,
            status          TEXT NOT NULL DEFAULT 'discovered',
            relevance_score REAL,
            key_findings    TEXT,
            discovered_at   TEXT NOT NULL,
            updated_at      TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS search_history (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            query           TEXT NOT NULL,
            source          TEXT NOT NULL,
            result_count    INTEGER NOT NULL DEFAULT 0,
            searched_at     TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS reports (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            paper_count     INTEGER NOT NULL,
            sent_to         TEXT NOT NULL,
            sent_at         TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_papers_status ON papers(status);
        CREATE INDEX IF NOT EXISTS idx_papers_score ON papers(relevance_score);
    """)
    conn.close()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# --- Paper operations ---

def add_paper(
    paper_id: str,
    title: str,
    authors: list[str],
    abstract: str,
    source: str,
    url: str,
    pdf_url: str | None = None,
    db_path: Path = DB_PATH,
) -> bool:
    conn = get_connection(db_path)
    now = _now()
    try:
        conn.execute(
            """INSERT OR IGNORE INTO papers
               (id, title, authors, abstract, source, url, pdf_url, status, discovered_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, 'discovered', ?, ?)""",
            (paper_id, title, json.dumps(authors), abstract, source, url, pdf_url, now, now),
        )
        conn.commit()
        return conn.total_changes > 0
    finally:
        conn.close()


def update_paper_status(paper_id: str, status: str, db_path: Path = DB_PATH) -> None:
    conn = get_connection(db_path)
    try:
        conn.execute(
            "UPDATE papers SET status = ?, updated_at = ? WHERE id = ?",
            (status, _now(), paper_id),
        )
        conn.commit()
    finally:
        conn.close()


def update_paper_score(paper_id: str, score: float, db_path: Path = DB_PATH) -> None:
    conn = get_connection(db_path)
    try:
        conn.execute(
            "UPDATE papers SET relevance_score = ?, status = 'scored', updated_at = ? WHERE id = ?",
            (score, _now(), paper_id),
        )
        conn.commit()
    finally:
        conn.close()


def update_paper_findings(paper_id: str, findings: list[str], db_path: Path = DB_PATH) -> None:
    conn = get_connection(db_path)
    try:
        conn.execute(
            "UPDATE papers SET key_findings = ?, status = 'extracted', updated_at = ? WHERE id = ?",
            (json.dumps(findings), _now(), paper_id),
        )
        conn.commit()
    finally:
        conn.close()


def get_papers_by_status(status: str, db_path: Path = DB_PATH) -> list[dict]:
    conn = get_connection(db_path)
    try:
        rows = conn.execute("SELECT * FROM papers WHERE status = ?", (status,)).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def get_all_papers(db_path: Path = DB_PATH) -> list[dict]:
    conn = get_connection(db_path)
    try:
        rows = conn.execute("SELECT * FROM papers ORDER BY discovered_at DESC").fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def paper_already_processed(paper_id: str, db_path: Path = DB_PATH) -> bool:
    """Check if a paper has already been processed beyond 'discovered' status."""
    conn = get_connection(db_path)
    try:
        row = conn.execute(
            "SELECT status FROM papers WHERE id = ? AND status != 'discovered'",
            (paper_id,),
        ).fetchone()
        return row is not None
    finally:
        conn.close()


# --- Search history ---

def add_search(query: str, source: str, result_count: int, db_path: Path = DB_PATH) -> None:
    conn = get_connection(db_path)
    try:
        conn.execute(
            "INSERT INTO search_history (query, source, result_count, searched_at) VALUES (?, ?, ?, ?)",
            (query, source, result_count, _now()),
        )
        conn.commit()
    finally:
        conn.close()


# --- Reports ---

def add_report(paper_count: int, sent_to: str, db_path: Path = DB_PATH) -> None:
    conn = get_connection(db_path)
    try:
        conn.execute(
            "INSERT INTO reports (paper_count, sent_to, sent_at) VALUES (?, ?, ?)",
            (paper_count, sent_to, _now()),
        )
        conn.commit()
    finally:
        conn.close()


def mark_papers_reported(paper_ids: list[str], db_path: Path = DB_PATH) -> None:
    conn = get_connection(db_path)
    try:
        placeholders = ",".join("?" for _ in paper_ids)
        now = _now()
        conn.execute(
            f"UPDATE papers SET status = 'reported', updated_at = ? WHERE id IN ({placeholders})",
            [now, *paper_ids],
        )
        conn.commit()
    finally:
        conn.close()
