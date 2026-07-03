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
# then ingest your ONS workbooks into data/gva/ :
python manage.py ingest_gva --path data/gva/
python manage.py ingest_population --path data/gva/populationestimatesbylocalauthority.xlsx --vintage 2020-06-mye
python manage.py derive_per_head
python manage.py runserver        # → http://127.0.0.1:8000/places/
```

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
| `seed_v1 --dimensions` | Seed geography levels, industries, price bases |
| `seed_v1 --geography` | Seed a curated sample of LADs, constituencies, regions |
| `seed_v1 --demo` | Load illustrative GVA + population (for the UI only) |
| `ingest_gva --path <file\|dir>` | Read ONS balanced-GVA-by-LAD workbook(s) |
| `ingest_population --path <file> --vintage <code>` | Read ONS population estimates |
| `derive_per_head [--vintage <code>]` | Compute GVA per head |

The ingest commands detect the ONS header row and year columns heuristically
(see `economy/management/commands/_xlsx.py`), so they tolerate the layout
differences between releases. Any geography code they meet that isn't already
seeded is created automatically (as an LAD by default; override with
`--level`). Pass `--dry-run` to parse and report without writing.

Get the source workbooks from the ONS:

- <https://www.ons.gov.uk/economy/grossvalueaddedgva>
- <https://www.ons.gov.uk/peoplepopulationandcommunity/populationandmigration/populationestimates>

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
