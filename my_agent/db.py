"""Base de datos SQLite para inscripciones a materias del ITBA."""

import sqlite3
from datetime import datetime
from pathlib import Path

_DB_PATH = Path(__file__).parent / "inscripciones.db"


def _get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(str(_DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def _init_db(conn: sqlite3.Connection) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS inscripciones (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id      TEXT NOT NULL,
            subject_code    TEXT NOT NULL,
            subject_name    TEXT NOT NULL,
            inscripto_en    TEXT NOT NULL,
            UNIQUE(student_id, subject_code)
        )
    """)
    conn.commit()


def is_enrolled(student_id: str, subject_code: str) -> bool:
    with _get_connection() as conn:
        _init_db(conn)
        row = conn.execute(
            "SELECT 1 FROM inscripciones WHERE student_id = ? AND subject_code = ?",
            (student_id, subject_code.upper()),
        ).fetchone()
    return row is not None


def enroll(student_id: str, subject_code: str, subject_name: str) -> dict:
    now = datetime.now()
    with _get_connection() as conn:
        _init_db(conn)
        conn.execute(
            "INSERT INTO inscripciones (student_id, subject_code, subject_name, inscripto_en) VALUES (?, ?, ?, ?)",
            (student_id, subject_code.upper(), subject_name, now.isoformat()),
        )
        conn.commit()
    return {
        "student_id": student_id,
        "subject_code": subject_code.upper(),
        "subject_name": subject_name,
        "inscripto_en": now.strftime("%d/%m/%Y %H:%M"),
    }


def get_subject_enrollments(subject_code: str) -> list[dict]:
    with _get_connection() as conn:
        _init_db(conn)
        rows = conn.execute(
            "SELECT student_id, subject_name, inscripto_en "
            "FROM inscripciones WHERE subject_code = ? ORDER BY inscripto_en",
            (subject_code.upper(),),
        ).fetchall()
    return [dict(row) for row in rows]


def get_enrollments(student_id: str) -> list[dict]:
    with _get_connection() as conn:
        _init_db(conn)
        rows = conn.execute(
            "SELECT subject_code, subject_name, inscripto_en "
            "FROM inscripciones WHERE student_id = ? ORDER BY inscripto_en",
            (student_id,),
        ).fetchall()
    return [dict(row) for row in rows]
