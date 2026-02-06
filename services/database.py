from __future__ import annotations

import os
import re
from typing import Dict, Iterable, List, Optional, Tuple

from PyQt6.QtSql import QSqlDatabase, QSqlQuery


DB_PATH = os.path.join("data", "driving_exams.db")


def open_database() -> QSqlDatabase:
    db = QSqlDatabase.addDatabase("QSQLITE")
    db.setDatabaseName(DB_PATH)
    if not db.open():
        raise RuntimeError(f"Failed to open database at {DB_PATH}")
    _ensure_base_tables(db)
    return db


def _ensure_base_tables(db: QSqlDatabase) -> None:
    query = QSqlQuery(db)
    query.exec(
        """
        CREATE TABLE IF NOT EXISTS imported_periods (
            year INTEGER NOT NULL,
            month INTEGER NOT NULL,
            PRIMARY KEY (year, month)
        )
        """
    )
    query.exec(
        """
        CREATE TABLE IF NOT EXISTS exams (
            id INTEGER PRIMARY KEY AUTOINCREMENT
        )
        """
    )


def sanitize_column(name: str) -> str:
    cleaned = name.strip().lower()
    cleaned = cleaned.replace("á", "a").replace("é", "e").replace("í", "i").replace("ó", "o").replace("ú", "u")
    cleaned = re.sub(r"[^\w]+", "_", cleaned)
    cleaned = re.sub(r"_+", "_", cleaned).strip("_")
    if not cleaned:
        cleaned = "col"
    if cleaned[0].isdigit():
        cleaned = f"c_{cleaned}"
    return cleaned


def ensure_columns(db: QSqlDatabase, columns: Iterable[str]) -> List[str]:
    existing = get_table_columns(db, "exams")
    to_add = []
    for col in columns:
        if col not in existing and col != "id":
            to_add.append(col)
    if not to_add:
        return existing
    query = QSqlQuery(db)
    for col in to_add:
        query.exec(f'ALTER TABLE exams ADD COLUMN "{col}" TEXT')
    return get_table_columns(db, "exams")


def get_table_columns(db: QSqlDatabase, table: str) -> List[str]:
    query = QSqlQuery(db)
    query.exec(f'PRAGMA table_info("{table}")')
    cols: List[str] = []
    while query.next():
        cols.append(query.value(1))
    return cols


def find_standard_columns(columns: Iterable[str]) -> Dict[str, Optional[str]]:
    col_list = list(columns)
    candidates = {c.lower(): c for c in col_list}

    def pick(patterns: Iterable[str]) -> Optional[str]:
        for pat in patterns:
            for key, original in candidates.items():
                if pat in key:
                    return original
        return None

    return {
        "month": pick(["mes", "month"]),
        "year": pick(["anyo", "anio", "año", "year"]),
        "province": pick(["desc_provincia", "prov", "provincia"]),
        "exam_center": pick(["centro_examen", "exam_center", "centro"]),
        "exam_type": pick(["tipo_examen", "exam_type", "prueba", "tipo"]),
        "driving_school": pick(["nombre_autoescuela", "autoescuela", "driving_school", "escuela"]),
        "permit": pick(["nombre_permiso", "permiso"]),
        "num_aptos": pick(["num_aptos"]),
        "num_no_aptos": pick(["num_no_aptos"]),
    }


def imported_period_exists(db: QSqlDatabase, year: int, month: int) -> bool:
    query = QSqlQuery(db)
    query.prepare("SELECT 1 FROM imported_periods WHERE year = ? AND month = ?")
    query.addBindValue(year)
    query.addBindValue(month)
    query.exec()
    return query.next()


def register_imported_periods(db: QSqlDatabase, periods: Iterable[Tuple[int, int]]) -> None:
    query = QSqlQuery(db)
    query.prepare("INSERT OR IGNORE INTO imported_periods (year, month) VALUES (?, ?)")
    for year, month in periods:
        query.addBindValue(year)
        query.addBindValue(month)
        query.exec()
