from __future__ import annotations

import csv
import os
import re
from typing import Dict, Iterable, List, Optional, Tuple

from PyQt6.QtSql import QSqlDatabase, QSqlQuery

from services.database import (
    ensure_columns,
    find_standard_columns,
    imported_period_exists,
    register_imported_periods,
    sanitize_column,
)


def _extract_periods_from_filename(path: str) -> List[Tuple[int, int]]:
    name = os.path.basename(path)
    matches = re.findall(r"(20\d{2}).?([01]?\d)", name)
    periods: List[Tuple[int, int]] = []
    for year_str, month_str in matches:
        year = int(year_str)
        month = int(month_str)
        if 1 <= month <= 12:
            periods.append((year, month))
    return periods


def _extract_periods_from_rows(rows: Iterable[Dict[str, str]], mapping: Dict[str, Optional[str]]) -> List[Tuple[int, int]]:
    year_col = mapping.get("year")
    month_col = mapping.get("month")
    if not year_col or not month_col:
        return []
    periods = set()
    for row in rows:
        try:
            year = int(str(row.get(year_col, "")).strip())
            month = int(str(row.get(month_col, "")).strip())
        except ValueError:
            continue
        if 1 <= month <= 12:
            periods.add((year, month))
    return sorted(periods)


def import_csv(db: QSqlDatabase, path: str) -> Tuple[int, List[Tuple[int, int]]]:
    with open(path, "r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle, delimiter=";")
        if not reader.fieldnames:
            return 0, []
        original_headers = [h.strip() for h in reader.fieldnames]
        sanitized_headers = [sanitize_column(h) for h in original_headers]

        mapping = {orig: sanitized for orig, sanitized in zip(original_headers, sanitized_headers)}
        ensure_columns(db, sanitized_headers)

        rows = list(reader)
        standard_mapping = find_standard_columns(sanitized_headers)
        periods = _extract_periods_from_rows(
            [{mapping.get(k, k): v for k, v in row.items()} for row in rows],
            standard_mapping,
        )
        if not periods:
            periods = _extract_periods_from_filename(path)

        if periods and any(imported_period_exists(db, y, m) for y, m in periods):
            return 0, periods

        inserted = _insert_rows(db, rows, mapping)
        if periods:
            register_imported_periods(db, periods)
        return inserted, periods


def _insert_rows(db: QSqlDatabase, rows: List[Dict[str, str]], mapping: Dict[str, str]) -> int:
    if not rows:
        return 0
    columns = [mapping[key] for key in rows[0].keys()]
    placeholders = ", ".join(["?"] * len(columns))
    col_sql = ", ".join([f'"{col}"' for col in columns])
    sql = f'INSERT INTO exams ({col_sql}) VALUES ({placeholders})'
    query = QSqlQuery(db)
    query.prepare(sql)
    count = 0
    for row in rows:
        query.clear()
        query.prepare(sql)
        for key in row.keys():
            query.addBindValue(row[key])
        if query.exec():
            count += 1
    return count
