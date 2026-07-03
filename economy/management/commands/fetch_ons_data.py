"""Download the ONS source workbooks used by this project.

    python manage.py fetch_ons_data

Fetches, into ``data/gva/`` by default:

* the 12 regional "Regional GVA (balanced) by industry: local authorities by
  ITL1 region" workbooks (current prices live on their "Table 3" sheet), and
* the companion "population estimates by local authority" workbook.

These files are git-ignored (they total ~25 MB), so this command is how you
get them onto a fresh checkout. Data is Crown copyright, Open Government
Licence v3.0.
"""
from __future__ import annotations

import time
import urllib.error
import urllib.request
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

ONS_FILE_BASE = "https://www.ons.gov.uk/file?uri="
GVA_DIR = (
    "/economy/grossdomesticproductgdp/datasets/"
    "regionalgrossvalueaddedbalancedbyindustrylocalauthoritiesbyitl1region"
)

# (local filename, remote path under ONS_FILE_BASE)
GVA_REGIONS = [
    "tlcnortheast/regionalgrossvalueaddedbalancedbyindustrylocalauthoritiestlcnortheast",
    "tldnorthwest/regionalgrossvalueaddedbalancedbyindustrylocalauthoritiestldnorthwest",
    "tleyorkshireandthehumber/regionalgrossvalueaddedbalancedbyindustrylocalauthoritiestleyorkshireandthehumber",
    "tlfeastmidlands/regionalgrossvalueaddedbalancedbyindustrylocalauthoritiestlfeastmidlands",
    "tlgwestmidlands/regionalgrossvalueaddedbalancedbyindustrylocalauthoritiestlgwestmidlands",
    "tlheastofengland/regionalgrossvalueaddedbalancedbyindustrylocalauthoritiestlheast",
    "tlilondon/regionalgrossvalueaddedbalancedbyindustrylocalauthoritiestlilondon",
    "tljsoutheast/regionalgrossvalueaddedbalancedbyindustrylocalauthoritiestljsoutheast",
    "tlksouthwest/regionalgrossvalueaddedbalancedbyindustrylocalauthoritiestlksouthwest",
    "tllwales/regionalgrossvalueaddedbalancedbyindustrylocalauthoritiestllwales",
    "tlmscotland/regionalgrossvalueaddedbalancedbyindustrylocalauthoritiestlmscotland",
    "tlnnorthernireland/regionalgrossvalueaddedbalancedbyindustrylocalauthoritiestlnnorthernireland",
]
POPULATION = "populationestimatesbylocalauthority/populationestimatesbylocalauthority"

USER_AGENT = "uk-economy-model/1.0 (+https://github.com/jattwell99)"


class Command(BaseCommand):
    help = "Download the ONS GVA and population workbooks into data/gva/."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dest",
            default="data/gva",
            help="Directory to download into (default: data/gva).",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Re-download files that already exist.",
        )

    def handle(self, *args, **options):
        dest = Path(options["dest"])
        dest.mkdir(parents=True, exist_ok=True)

        targets = [
            (f"gva_{region.split('/')[0]}.xlsx", f"{GVA_DIR}/{region}.xlsx")
            for region in GVA_REGIONS
        ]
        targets.append(
            ("populationestimatesbylocalauthority.xlsx", f"{GVA_DIR}/{POPULATION}.xlsx")
        )

        downloaded = skipped = 0
        for filename, remote in targets:
            out = dest / filename
            if out.exists() and not options["force"]:
                self.stdout.write(f"  skip {filename} (exists)")
                skipped += 1
                continue
            url = ONS_FILE_BASE + remote
            try:
                size = self._download(url, out)
            except Exception as exc:  # noqa: BLE001 — surface any fetch failure
                raise CommandError(f"Failed to download {filename}: {exc}") from exc
            self.stdout.write(f"  got  {filename} ({size // 1024} KiB)")
            downloaded += 1
            # Be polite: ONS rate-limits bursts (HTTP 429).
            time.sleep(1.5)

        self.stdout.write(
            self.style.SUCCESS(
                f"Done: {downloaded} downloaded, {skipped} already present, "
                f"in {dest}/."
            )
        )
        if downloaded or skipped:
            self.stdout.write(
                "Next: ingest_gva --path %s --sheet 'Table 3', then "
                "ingest_population and derive_per_head." % dest
            )

    def _download(self, url: str, out: Path, retries: int = 4) -> int:
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        for attempt in range(retries):
            try:
                with urllib.request.urlopen(request, timeout=120) as response:
                    data = response.read()
                break
            except urllib.error.HTTPError as exc:
                # Retry rate-limits / transient server errors with backoff.
                if exc.code in (429, 500, 502, 503, 504) and attempt < retries - 1:
                    wait = 2 ** (attempt + 1)
                    self.stdout.write(f"    {exc.code}; retrying in {wait}s ...")
                    time.sleep(wait)
                    continue
                raise
        # ONS returns a small XML error body with a 200 in some edge cases;
        # a real workbook is a zip starting with "PK".
        if not data[:2] == b"PK":
            raise CommandError(f"unexpected response ({len(data)} bytes, not xlsx)")
        out.write_bytes(data)
        return len(data)
