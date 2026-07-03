"""Seed baseline reference data for the v1 model.

    python manage.py seed_v1 --dimensions --geography

Flags can be combined; with none given, everything is seeded. ``--demo``
additionally loads a tiny, clearly-illustrative set of GVA and population
figures so the /places/ page renders before real ONS workbooks are ingested.
"""
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from economy.models import (
    GvaValue,
    Industry,
    PopulationValue,
    PopulationVintage,
    PriceBasis,
)
from geography.models import Geography, GeographyLevel

# --- Dimension seed data -------------------------------------------------

GEOGRAPHY_LEVELS = [
    ("CTRY", "Country", 0),
    ("RGN", "Region / ITL1", 1),
    ("LAD", "Local Authority District", 2),
    ("WPC", "Westminster Parliamentary Constituency", 2),
]

# SIC07 sections plus the all-industries total.
INDUSTRIES = [
    ("TOTAL", "All industries"),
    ("A", "Agriculture, forestry and fishing"),
    ("BE", "Production"),
    ("F", "Construction"),
    ("GT", "Distribution, transport, accommodation and food"),
    ("K", "Financial and insurance activities"),
    ("L", "Real estate activities"),
    ("MN", "Business services"),
    ("OQ", "Public administration, education and health"),
    ("RT", "Other services and household activities"),
]

PRICE_BASES = [
    ("current", "Current basic prices (£m)"),
    ("chained_volume", "Chained volume measure (£m, reference year)"),
]

# --- Geography seed data -------------------------------------------------
# A curated, representative sample. Real boundary sets are loaded by the
# ingest commands (which upsert any geography codes they encounter).

COUNTRIES = [
    ("E92000001", "England"),
    ("S92000003", "Scotland"),
    ("W92000004", "Wales"),
    ("N92000002", "Northern Ireland"),
]

REGIONS = [
    ("E12000001", "North East", "E92000001"),
    ("E12000002", "North West", "E92000001"),
    ("E12000003", "Yorkshire and The Humber", "E92000001"),
    ("E12000004", "East Midlands", "E92000001"),
    ("E12000005", "West Midlands", "E92000001"),
    ("E12000006", "East of England", "E92000001"),
    ("E12000007", "London", "E92000001"),
    ("E12000008", "South East", "E92000001"),
    ("E12000009", "South West", "E92000001"),
]

# (code, name, parent_region, lat, lon)
LADS = [
    ("E06000001", "Hartlepool", "E12000001", 54.69, -1.21),
    ("E08000003", "Manchester", "E12000002", 53.48, -2.24),
    ("E08000025", "Birmingham", "E12000005", 52.48, -1.90),
    ("E06000018", "Nottingham", "E12000004", 52.95, -1.15),
    ("E06000023", "Bristol, City of", "E12000009", 51.45, -2.59),
    ("E09000001", "City of London", "E12000007", 51.52, -0.09),
    ("E09000007", "Camden", "E12000007", 51.54, -0.14),
    ("E07000178", "Oxford", "E12000008", 51.75, -1.26),
    ("E06000031", "Peterborough", "E12000006", 52.57, -0.24),
    ("E06000010", "Kingston upon Hull, City of", "E12000003", 53.74, -0.33),
]

# (code, name, parent_region)
WPCS = [
    ("E14000615", "Cities of London and Westminster", "E12000007"),
    ("E14000530", "Birmingham, Edgbaston", "E12000005"),
    ("E14000639", "Manchester Central", "E12000002"),
    ("E14000929", "Oxford East", "E12000008"),
]

# --- Illustrative demo figures (NOT official statistics) -----------------
# gva_gbp_million and population are order-of-magnitude only.
DEMO = {
    # code: (gva_2021_current_£m, population_2021)
    "E06000001": (2_100, 92_000),
    "E08000003": (28_500, 552_000),
    "E08000025": (33_800, 1_144_000),
    "E06000018": (9_200, 323_000),
    "E06000023": (16_400, 472_000),
    "E09000001": (79_000, 8_600),
    "E09000007": (34_000, 210_000),
    "E07000178": (9_800, 162_000),
    "E06000031": (5_600, 215_000),
    "E06000010": (5_900, 267_000),
}
DEMO_YEAR = 2021


class Command(BaseCommand):
    help = "Seed dimensions and geography for the v1 UK economy model."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dimensions", action="store_true", help="Seed dimension tables."
        )
        parser.add_argument(
            "--geography", action="store_true", help="Seed the geography sample."
        )
        parser.add_argument(
            "--demo",
            action="store_true",
            help="Also load illustrative GVA/population so /places/ renders.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        # Default to seeding everything when no specific flag is passed.
        do_dimensions = options["dimensions"] or not (
            options["dimensions"] or options["geography"]
        )
        do_geography = options["geography"] or not (
            options["dimensions"] or options["geography"]
        )

        if do_dimensions:
            self._seed_dimensions()
        if do_geography:
            self._seed_geography()
        if options["demo"]:
            self._seed_demo()

        self.stdout.write(self.style.SUCCESS("Seed complete."))

    def _seed_dimensions(self):
        for code, name, rank in GEOGRAPHY_LEVELS:
            GeographyLevel.objects.update_or_create(
                code=code, defaults={"name": name, "rank": rank}
            )
        for code, name in INDUSTRIES:
            Industry.objects.update_or_create(code=code, defaults={"name": name})
        for code, name in PRICE_BASES:
            PriceBasis.objects.update_or_create(code=code, defaults={"name": name})
        self.stdout.write(
            f"  dimensions: {len(GEOGRAPHY_LEVELS)} levels, "
            f"{len(INDUSTRIES)} industries, {len(PRICE_BASES)} price bases"
        )

    def _seed_geography(self):
        levels = {lvl.code: lvl for lvl in GeographyLevel.objects.all()}
        if not levels:
            self.stderr.write(
                "  geography: run --dimensions first (levels missing)."
            )
            return

        for code, name in COUNTRIES:
            Geography.objects.update_or_create(
                code=code, defaults={"name": name, "level": levels["CTRY"]}
            )
        for code, name, parent_code in REGIONS:
            Geography.objects.update_or_create(
                code=code,
                defaults={
                    "name": name,
                    "level": levels["RGN"],
                    "parent": Geography.objects.filter(code=parent_code).first(),
                },
            )
        for code, name, parent_code, lat, lon in LADS:
            Geography.objects.update_or_create(
                code=code,
                defaults={
                    "name": name,
                    "level": levels["LAD"],
                    "parent": Geography.objects.filter(code=parent_code).first(),
                    "latitude": lat,
                    "longitude": lon,
                },
            )
        for code, name, parent_code in WPCS:
            Geography.objects.update_or_create(
                code=code,
                defaults={
                    "name": name,
                    "level": levels["WPC"],
                    "parent": Geography.objects.filter(code=parent_code).first(),
                },
            )
        self.stdout.write(
            f"  geography: {len(COUNTRIES)} countries, {len(REGIONS)} regions, "
            f"{len(LADS)} LADs, {len(WPCS)} constituencies"
        )

    def _seed_demo(self):
        try:
            total = Industry.objects.get(code="TOTAL")
            current = PriceBasis.objects.get(code="current")
        except (Industry.DoesNotExist, PriceBasis.DoesNotExist):
            self.stderr.write("  demo: run --dimensions first.")
            return
        vintage, _ = PopulationVintage.objects.update_or_create(
            code="demo-mye",
            defaults={"label": "Illustrative demo estimates (not official)"},
        )
        loaded = 0
        for code, (gva, pop) in DEMO.items():
            geo = Geography.objects.filter(code=code).first()
            if geo is None:
                continue
            GvaValue.objects.update_or_create(
                geography=geo,
                industry=total,
                price_basis=current,
                year=DEMO_YEAR,
                defaults={
                    "value_gbp_million": Decimal(gva),
                    "source": "seed_v1 --demo (illustrative)",
                },
            )
            PopulationValue.objects.update_or_create(
                geography=geo,
                vintage=vintage,
                year=DEMO_YEAR,
                defaults={"population": pop},
            )
            loaded += 1
        self.stdout.write(
            self.style.WARNING(
                f"  demo: loaded {loaded} illustrative GVA/population rows "
                f"(year {DEMO_YEAR}). Run derive_per_head next."
            )
        )
