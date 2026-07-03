"""Helpers for parsing ONS-style Excel workbooks with openpyxl.

ONS statistical workbooks share a recognisable shape: a few notes rows, then
a header row that includes a geography *code* column, a geography *name*
column, and a run of four-digit *year* columns. These helpers locate that
header row heuristically so the ingest commands don't hard-code fragile row
numbers.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

CODE_RE = re.compile(r"cod", re.IGNORECASE)
NAME_RE = re.compile(r"(name|area|authority|constituency)", re.IGNORECASE)
INDUSTRY_RE = re.compile(r"(sic|industr)", re.IGNORECASE)
# Year columns are sometimes bare ("2021") and sometimes prefixed
# ("population_2021"); capture the trailing four digits either way.
YEAR_RE = re.compile(r"^(?:.*[^0-9])?((?:19|20)\d{2})$")
# An ONS geography code, e.g. E06000001, S12000036, W06000015, N09000001.
GEOCODE_RE = re.compile(r"^[ENSWK]\d{8}$")


@dataclass
class SheetLayout:
    """Where the interesting columns live in a parsed sheet."""

    header_row: int  # 1-indexed row containing headers
    code_col: int  # 1-indexed column with the geography code
    name_col: int | None  # 1-indexed column with the geography name
    year_cols: dict[int, int]  # {year: 1-indexed column}
    industry_col: int | None = None  # 1-indexed SIC/industry column, if any


def _as_str(value) -> str:
    return "" if value is None else str(value).strip()


def _year_from(value) -> int | None:
    match = YEAR_RE.match(_as_str(value))
    if match:
        return int(match.group(1))
    # Some sheets store years as numbers (2021.0).
    if isinstance(value, (int, float)) and 1900 <= int(value) <= 2100:
        return int(value)
    return None


def detect_layout(ws, max_scan_rows: int = 40) -> SheetLayout | None:
    """Find the header row and key columns in a worksheet.

    Returns ``None`` if no plausible header row is found within the first
    ``max_scan_rows`` rows.
    """
    for row_idx in range(1, min(ws.max_row, max_scan_rows) + 1):
        cells = [ws.cell(row=row_idx, column=c) for c in range(1, ws.max_column + 1)]
        code_col = name_col = industry_col = None
        year_cols: dict[int, int] = {}
        for cell in cells:
            header = _as_str(cell.value)
            if not header:
                continue
            year = _year_from(cell.value)
            if year is not None:
                year_cols[year] = cell.column
                continue
            if code_col is None and CODE_RE.search(header):
                code_col = cell.column
            elif industry_col is None and INDUSTRY_RE.search(header):
                industry_col = cell.column
            elif name_col is None and NAME_RE.search(header):
                name_col = cell.column
        # A real header row has a code column and at least one year column.
        if code_col is not None and year_cols:
            return SheetLayout(row_idx, code_col, name_col, year_cols, industry_col)
    return None


def is_geocode(value) -> bool:
    return bool(GEOCODE_RE.match(_as_str(value)))


def to_number(value) -> float | None:
    """Coerce a cell to a float, treating ONS placeholders as missing."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = _as_str(value).replace(",", "")
    if text in {"", "-", "..", "N/A", "n/a", ":", "c", "x"}:
        return None
    try:
        return float(text)
    except ValueError:
        return None
