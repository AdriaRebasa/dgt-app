from __future__ import annotations

import csv
import os
import re
from typing import Dict, Iterable, List, Optional, Tuple

from PyQt6.QtSql import QSqlDatabase, QSqlQuery

from services.database import (
    ensure_columns,
    find_standard_columns,
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


def _load_imported_periods(db: QSqlDatabase) -> set[Tuple[int, int]]:
    query = QSqlQuery(db)
    query.exec("SELECT year, month FROM imported_periods")
    periods: set[Tuple[int, int]] = set()
    while query.next():
        year = query.value(0)
        month = query.value(1)
        if year is None or month is None:
            continue
        try:
            periods.add((int(year), int(month)))
        except (TypeError, ValueError):
            continue
    return periods


def _parse_row_period(row: Dict[str, str], year_key: Optional[str], month_key: Optional[str]) -> Optional[Tuple[int, int]]:
    if not year_key or not month_key:
        return None
    try:
        year = int(str(row.get(year_key, "")).strip())
        month = int(str(row.get(month_key, "")).strip())
    except ValueError:
        return None
    if 1 <= month <= 12:
        return year, month
    return None


def import_csv(db: QSqlDatabase, path: str) -> Tuple[int, List[Tuple[int, int]]]:
    handle = None
    last_error: Optional[UnicodeDecodeError] = None
    for encoding in ("utf-8-sig", "latin-1"):
        try:
            handle = open(path, "r", encoding=encoding, newline="")
            reader = csv.DictReader(handle, delimiter=";")
            if not reader.fieldnames:
                handle.close()
                return 0, []
            original_headers = [h.strip() for h in reader.fieldnames]
            sanitized_headers = [sanitize_column(h) for h in original_headers]

            mapping = {orig: sanitized for orig, sanitized in zip(original_headers, sanitized_headers)}
            ensure_columns(db, sanitized_headers)

            rows = list(reader)
            standard_mapping = find_standard_columns(sanitized_headers)
            rows_sanitized = [{mapping.get(k, k): v for k, v in row.items()} for row in rows]
            periods = _extract_periods_from_rows(rows_sanitized, standard_mapping)
            if not periods:
                periods = _extract_periods_from_filename(path)

            year_col = standard_mapping.get("year")
            month_col = standard_mapping.get("month")
            imported_periods = _load_imported_periods(db)

            if year_col and month_col:
                reverse_mapping = {san: orig for orig, san in mapping.items()}
                year_key = reverse_mapping.get(year_col, year_col)
                month_key = reverse_mapping.get(month_col, month_col)
                new_rows: List[Dict[str, str]] = []
                new_periods: set[Tuple[int, int]] = set()
                for row in rows:
                    period = _parse_row_period(row, year_key, month_key)
                    if period and period in imported_periods:
                        continue
                    new_rows.append(row)
                    if period:
                        new_periods.add(period)
                if not new_rows:
                    handle.close()
                    return 0, periods
                inserted = _insert_rows(db, new_rows, mapping)
                if new_periods:
                    register_imported_periods(db, sorted(new_periods))
                handle.close()
                return inserted, periods

            if periods and any((y, m) in imported_periods for y, m in periods):
                handle.close()
                return 0, periods

            inserted = _insert_rows(db, rows, mapping)
            if periods:
                register_imported_periods(db, periods)
            handle.close()
            return inserted, periods
        except UnicodeDecodeError as exc:
            last_error = exc
            if handle:
                handle.close()
            continue

    if last_error:
        raise last_error
    return 0, []


def _insert_rows(db: QSqlDatabase, rows: List[Dict[str, str]], mapping: Dict[str, str]) -> int:
    if not rows:
        return 0
    keys = list(rows[0].keys())
    columns = [mapping[key] for key in keys]
    placeholders = ", ".join(["?"] * len(columns))
    col_sql = ", ".join([f'"{col}"' for col in columns])
    sql = f'INSERT INTO exams ({col_sql}) VALUES ({placeholders})'
    query = QSqlQuery(db)
    query.prepare(sql)
    count = 0
    total = len(rows)
    print(f"Importing {total} rows...")
    use_tx = db.transaction()
    for idx, row in enumerate(rows, start=1):
        for i, key in enumerate(keys):
            query.bindValue(i, row.get(key))
        if query.exec():
            count += 1
        if idx % 1000 == 0 or idx == total:
            print(f"Processed {idx}/{total} rows...")
    if use_tx:
        if not db.commit():
            db.rollback()
    return count
