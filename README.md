# UK economy model

A small Django application for exploring **GVA per head** across UK places
(Local Authority Districts and Westminster Parliamentary Constituencies),
built from ONS open data.

It ingests two ONS sources:

- **Regional GVA (balanced) by local authority** — gross value added in £m
- **Mid-year population estimates by local authority**

and derives **GVA per head** = `GVA (£m) × 1,000,000 / population`, which the
`/places/` page ranks and lets you drill into per place.

## Quickstart

```bash
git clone https://github.com/jattwell99/UK-economy-model && cd UK-economy-model
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
docker compose up -d db          # Postgres
cp .env.example .env
python manage.py migrate
python manage.py seed_v1 --dimensions --geography   # dimensions + LAD/WPC boundaries
# download the real ONS workbooks into data/gva/ (~25 MB, git-ignored):
python manage.py fetch_ons_data
# ingest current-price GVA (Table 3) and population, then derive:
python manage.py ingest_gva --path data/gva/ --sheet "Table 3"
python manage.py ingest_population --path data/gva/populationestimatesbylocalauthority.xlsx --vintage ons-lad-2024
python manage.py derive_per_head
python manage.py runserver        # → http://127.0.0.1:8000/places/
```

This loads real balanced GVA per head for every UK local authority,
1998–2023 (e.g. City of London ~£8.1m/head from its tiny resident
population, Milton Keynes ~£56k). `fetch_ons_data` pulls the 12 regional GVA
workbooks plus the companion population file straight from the ONS.

> **No Postgres / no data yet?** The project falls back to a local SQLite
> file when `DATABASE_URL` is unset, and you can load an illustrative dataset
> to see the UI immediately:
>
> ```bash
> python manage.py migrate
> python manage.py seed_v1 --dimensions --geography --demo
> python manage.py derive_per_head
> python manage.py runserver
> ```
>
> The `--demo` figures are **order-of-magnitude illustrations, not official
> statistics** — replace them by ingesting the real ONS workbooks.

## Data model

| App | Model | Purpose |
| --- | --- | --- |
| `geography` | `GeographyLevel` | LAD / WPC / region / country tiers |
| `geography` | `Geography` | one statistical area (ONS code, name, parent, centroid) |
| `economy` | `Industry`, `PriceBasis` | dimensions (SIC section; current / chained volume) |
| `economy` | `GvaValue` | GVA (£m) per geography × industry × price basis × year |
| `economy` | `PopulationVintage`, `PopulationValue` | population by release and year |
| `economy` | `GvaPerHead` | derived £/head per geography × year |

## Management commands

| Command | What it does |
| --- | --- |
| `fetch_ons_data` | Download the ONS GVA + population workbooks into `data/gva/` |
| `seed_v1 --dimensions` | Seed geography levels, industries, price bases |
| `seed_v1 --geography` | Seed a curated sample of LADs, constituencies, regions |
| `seed_v1 --demo` | Load illustrative GVA + population (for the UI only) |
| `ingest_gva --path <file\|dir> --sheet "Table 3"` | Read ONS balanced-GVA-by-LAD workbook(s) |
| `ingest_population --path <file> --vintage <code>` | Read ONS population estimates |
| `derive_per_head [--vintage <code>]` | Compute GVA per head |

The ingest commands detect the ONS header row and year columns heuristically
(see `economy/management/commands/_xlsx.py`), so they tolerate the layout
differences between releases. Notes on the current ONS layout:

- GVA is split across four sheets per file; **Table 3 is current prices
  (£m)**, so pass `--sheet "Table 3"`. (Table 1 is a volume index, Table 2
  chained volume, Table 4 the deflator.) This also skips the population
  workbook if it's in the same folder.
- Each GVA sheet breaks figures down by industry; the importer keeps only the
  all-industries **Total** row (override with `--industry-total`).
- Any geography code not already seeded is created automatically (as an LAD by
  default; override with `--level`). Pass `--dry-run` to parse without writing.

Source datasets (Crown copyright, Open Government Licence v3.0):

- [Regional GVA (balanced) by industry: local authorities by ITL1 region](https://www.ons.gov.uk/economy/grossdomesticproductgdp/datasets/regionalgrossvalueaddedbalancedbyindustrylocalauthoritiesbyitl1region)
- Companion population-by-local-authority workbook (linked from the same page)

## Configuration

Settings are read from the environment (see `.env.example`):

| Variable | Default | Notes |
| --- | --- | --- |
| `DJANGO_SECRET_KEY` | dev key | set a real value in production |
| `DJANGO_DEBUG` | `False` | |
| `DJANGO_ALLOWED_HOSTS` | `127.0.0.1,localhost` | comma-separated |
| `DATABASE_URL` | SQLite file | e.g. `postgres://user:pass@host:5432/db` |

## Layout

```
config/     Django project (settings, urls, wsgi/asgi)
geography/  geography dimension + seed_v1 command
economy/    GVA / population / per-head models + ingest & derive commands
places/     the /places/ views and templates
data/gva/   drop ONS workbooks here (git-ignored)
```

## License

[MIT](LICENSE)
