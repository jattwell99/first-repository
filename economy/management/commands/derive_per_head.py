"""Derive GVA per head from all-industries current-price GVA and population.

    python manage.py derive_per_head

For every all-industries, current-price :class:`GvaValue` that has a matching
:class:`PopulationValue` (same geography and year), this computes

    GVA per head (£) = value_gbp_million × 1,000,000 / population

and upserts a :class:`GvaPerHead` row. By default the most recent population
vintage is used; pass ``--vintage`` to pin a specific release.
"""
from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

from django.core.management.base import BaseCommand, CommandError

from economy.models import (
    GvaPerHead,
    GvaValue,
    Industry,
    PopulationValue,
    PopulationVintage,
    PriceBasis,
)

MILLION = Decimal(1_000_000)
PENNY = Decimal("0.01")


class Command(BaseCommand):
    help = "Compute GVA per head from GVA and population data."

    def add_arguments(self, parser):
        parser.add_argument(
            "--vintage",
            default="",
            help="Population vintage code to use (default: most recent).",
        )
        parser.add_argument(
            "--industry",
            default="TOTAL",
            help="Industry code to derive from (default: TOTAL).",
        )
        parser.add_argument(
            "--price-basis",
            default="current",
            help="Price basis to derive from (default: current).",
        )

    def handle(self, *args, **options):
        industry = self._get(Industry, code=options["industry"], label="industry")
        price_basis = self._get(
            PriceBasis, code=options["price_basis"], label="price basis"
        )
        vintage = self._resolve_vintage(options["vintage"])

        # Index population by (geography_id, year) for the chosen vintage.
        pop_index = {
            (pv.geography_id, pv.year): pv.population
            for pv in PopulationValue.objects.filter(vintage=vintage)
        }
        if not pop_index:
            raise CommandError(
                f"No population values for vintage '{vintage.code}'. "
                "Ingest population first."
            )

        gva_qs = GvaValue.objects.filter(
            industry=industry, price_basis=price_basis
        ).select_related("geography")

        created = updated = skipped = 0
        for gva in gva_qs.iterator():
            population = pop_index.get((gva.geography_id, gva.year))
            if not population:  # no match, or population of zero
                skipped += 1
                continue
            per_head = (gva.value_gbp_million * MILLION / Decimal(population)).quantize(
                PENNY, rounding=ROUND_HALF_UP
            )
            _, was_created = GvaPerHead.objects.update_or_create(
                geography=gva.geography,
                year=gva.year,
                defaults={
                    "gva_gbp_million": gva.value_gbp_million,
                    "population": population,
                    "gva_per_head_gbp": per_head,
                    "vintage": vintage,
                },
            )
            created += was_created
            updated += not was_created

        self.stdout.write(
            self.style.SUCCESS(
                f"Derived GVA per head using vintage '{vintage.code}': "
                f"{created} created, {updated} updated, "
                f"{skipped} GVA rows had no population match."
            )
        )

    def _get(self, model, *, code, label):
        try:
            return model.objects.get(code=code)
        except model.DoesNotExist as exc:
            raise CommandError(
                f"Unknown {label} '{code}'. Run seed_v1 --dimensions first."
            ) from exc

    def _resolve_vintage(self, code: str) -> PopulationVintage:
        if code:
            try:
                return PopulationVintage.objects.get(code=code)
            except PopulationVintage.DoesNotExist as exc:
                raise CommandError(f"Unknown population vintage '{code}'.") from exc
        vintage = PopulationVintage.objects.order_by("-code").first()
        if vintage is None:
            raise CommandError(
                "No population vintages exist. Ingest population first."
            )
        return vintage
