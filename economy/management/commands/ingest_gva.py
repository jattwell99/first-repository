"""Ingest ONS "Regional GVA (balanced) by local authority" workbooks.

    python manage.py ingest_gva --path data/gva/

``--path`` may be a single .xlsx file or a directory (all .xlsx files in it
are processed). Each sheet is scanned for a header row with a geography code
column and year columns (see ``_xlsx.detect_layout``); rows whose first cell
is a valid ONS geography code are read as all-industries current-price GVA
in £ million.

The workbook layout varies between releases, so the important knobs are
exposed as options rather than hard-coded:

* ``--sheet``        limit to sheets whose name contains this text
* ``--price-basis``  which PriceBasis the figures represent (default current)
* ``--level``        GeographyLevel for codes not already seeded (default LAD)
"""
from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from economy.models import GvaValue, Industry, PriceBasis
from geography.models import Geography, GeographyLevel

from ._xlsx import detect_layout, is_geocode, to_number


class Command(BaseCommand):
    help = "Ingest ONS balanced GVA by local authority workbooks (£m)."

    def add_arguments(self, parser):
        parser.add_argument("--path", required=True, help="File or directory.")
        parser.add_argument(
            "--sheet",
            default="",
            help="Only read sheets whose name contains this text.",
        )
        parser.add_argument(
            "--price-basis",
            default="current",
            help="PriceBasis code these figures use (default: current).",
        )
        parser.add_argument(
            "--level",
            default="LAD",
            help="GeographyLevel code for unseen geography codes (default: LAD).",
        )
        parser.add_argument(
            "--industry-total",
            default="Total",
            help=(
                "When a sheet has a SIC/industry column, only ingest rows whose "
                "industry equals this (default: Total). Matched case-insensitively; "
                "'All industries' is also accepted."
            ),
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Parse and report without writing to the database.",
        )

    def handle(self, *args, **options):
        try:
            from openpyxl import load_workbook
        except ImportError as exc:  # pragma: no cover
            raise CommandError(
                "openpyxl is required: pip install -r requirements.txt"
            ) from exc

        files = self._resolve_files(options["path"])
        if not files:
            raise CommandError(f"No .xlsx files found at {options['path']}")

        industry = self._get_industry()
        price_basis = self._get_price_basis(options["price_basis"])
        level = self._get_level(options["level"])

        totals = {"files": 0, "sheets": 0, "rows": 0, "new_geographies": 0}
        for path in files:
            self.stdout.write(f"Reading {path.name} ...")
            wb = load_workbook(path, read_only=True, data_only=True)
            for ws in wb.worksheets:
                if options["sheet"] and options["sheet"].lower() not in ws.title.lower():
                    continue
                stats = self._ingest_sheet(
                    ws,
                    path,
                    industry,
                    price_basis,
                    level,
                    options["industry_total"],
                    options["dry_run"],
                )
                if stats["rows"]:
                    totals["sheets"] += 1
                    totals["rows"] += stats["rows"]
                    totals["new_geographies"] += stats["new_geographies"]
                    self.stdout.write(
                        f"  [{ws.title}] {stats['rows']} values across "
                        f"{len(stats['years'])} years "
                        f"({min(stats['years'])}–{max(stats['years'])})"
                    )
            wb.close()
            totals["files"] += 1

        verb = "Would ingest" if options["dry_run"] else "Ingested"
        self.stdout.write(
            self.style.SUCCESS(
                f"{verb} {totals['rows']} GVA values from {totals['sheets']} "
                f"sheet(s) in {totals['files']} file(s); "
                f"{totals['new_geographies']} new geographies."
            )
        )

    # -- helpers ----------------------------------------------------------

    def _resolve_files(self, raw_path: str) -> list[Path]:
        path = Path(raw_path)
        if path.is_dir():
            return sorted(path.glob("*.xlsx"))
        if path.is_file():
            return [path]
        return []

    def _get_industry(self) -> Industry:
        industry, _ = Industry.objects.get_or_create(
            code="TOTAL", defaults={"name": "All industries"}
        )
        return industry

    def _get_price_basis(self, code: str) -> PriceBasis:
        try:
            return PriceBasis.objects.get(code=code)
        except PriceBasis.DoesNotExist as exc:
            raise CommandError(
                f"Unknown price basis '{code}'. Run seed_v1 --dimensions first."
            ) from exc

    def _get_level(self, code: str) -> GeographyLevel:
        try:
            return GeographyLevel.objects.get(code=code)
        except GeographyLevel.DoesNotExist as exc:
            raise CommandError(
                f"Unknown geography level '{code}'. Run seed_v1 --dimensions first."
            ) from exc

    @transaction.atomic
    def _ingest_sheet(
        self, ws, path, industry, price_basis, level, industry_total, dry_run
    ):
        stats = {"rows": 0, "years": set(), "new_geographies": 0}
        layout = detect_layout(ws)
        if layout is None:
            return stats

        wanted = {industry_total.strip().lower(), "all industries"}
        for row in ws.iter_rows(min_row=layout.header_row + 1):
            code_cell = row[layout.code_col - 1] if layout.code_col - 1 < len(row) else None
            if code_cell is None or not is_geocode(code_cell.value):
                continue
            # When the sheet breaks GVA down by industry, keep only the
            # all-industries total row (otherwise every industry row would
            # overwrite the same TOTAL record).
            if layout.industry_col and layout.industry_col - 1 < len(row):
                cell = row[layout.industry_col - 1]
                if str(cell.value or "").strip().lower() not in wanted:
                    continue
            code = str(code_cell.value).strip()
            name = ""
            if layout.name_col and layout.name_col - 1 < len(row):
                name = str(row[layout.name_col - 1].value or "").strip()

            geo, created = self._get_or_create_geography(code, name, level, dry_run)
            if created:
                stats["new_geographies"] += 1

            for year, col in layout.year_cols.items():
                if col - 1 >= len(row):
                    continue
                value = to_number(row[col - 1].value)
                if value is None:
                    continue
                stats["years"].add(year)
                stats["rows"] += 1
                if dry_run or geo is None:
                    continue
                GvaValue.objects.update_or_create(
                    geography=geo,
                    industry=industry,
                    price_basis=price_basis,
                    year=year,
                    defaults={
                        "value_gbp_million": Decimal(str(round(value, 3))),
                        "source": path.name,
                    },
                )
        return stats

    def _get_or_create_geography(self, code, name, level, dry_run):
        geo = Geography.objects.filter(code=code).first()
        if geo is not None:
            return geo, False
        if dry_run:
            return None, True
        geo = Geography.objects.create(
            code=code, name=name or code, level=level
        )
        return geo, True
