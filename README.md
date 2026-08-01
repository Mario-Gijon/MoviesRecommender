# Movies Recommender

Explainable movie recommender web app for a public science outreach event. The project is designed to teach recommendation systems in a white-box way, starting with simple deterministic placeholders before real catalog and recommendation logic is added.

## Local development

### Frontend

```bash
cd Frontend
bun install
bun dev
```

### Backend

```bash
cd Backend
uvicorn app.main:app --reload --port 8014
```

## Docker and deployment

Production Compose uses image references and keeps all generated runtime data on the
host through `DATA_DIR` (default `./Backend/data`). This includes both the shared
`offline_dataset/` and recommender-specific `recommender_models/` directories, so
they survive `stop`, `down`, image pulls, and restarts.

Docker users configure only `DATA_DIR`; Compose supplies
`MOVIES_RECOMMENDER_DATA_DIR=/app/data` inside each backend container. The latter
setting is only useful when running Python directly outside Docker, where its
default remains `Backend/data`.

```bash
cp .env.example .env
docker compose up -d api
docker compose --profile frontend up -d
```

The backend is available by itself on `${BACKEND_BIND_HOST}:${BACKEND_PORT}`. The
optional production frontend is served on `${FRONTEND_BIND_HOST}:${FRONTEND_PORT}`
and proxies `/api/`, `/offline/`, and `/audit/` to the backend internally. Defaults
bind to `127.0.0.1`; set either bind host to `0.0.0.0` only when LAN/server access is
intended. Image names, ports, bind hosts, and `DATA_DIR` are configurable in `.env`.

For source-based local development:

```bash
docker compose -f compose.yaml -f compose.dev.yaml up --build api
docker compose --profile frontend -f compose.yaml -f compose.dev.yaml up --build
```

The development frontend keeps `VITE_API_URL=http://localhost:8014`; the production
frontend uses relative `/api` URLs through Nginx.

## Dataset generation

The opt-in `dataset` service generates `offline_dataset/` from MovieLens 32M and
TMDB metadata. It reuses valid raw files and cached work where possible, but
regenerates the selected candidate, enrichment, catalogue, ratings, export, poster,
and audit outputs. It never rebuilds `recommender_models/`.

Run the local terminal wizard from `Backend`:

```bash
.venv/bin/python -m pipelines.dataset_generation.cli
```

Or run the same wizard in Docker:

```bash
docker compose --profile dataset run --rm dataset
```

The `recommended` profile creates the broad 15,000-item configuration; choose
`custom` in the wizard for individual limits, years, language, stages, poster and
audit options. Deterministic installation-style use is available with, for example:

```bash
MOVIES_RECOMMENDER_TMDB_BEARER_TOKEN='...' \
  .venv/bin/python -m pipelines.dataset_generation.cli \
  --non-interactive --yes --source download --preset recommended --audit
```

Use `--dry-run` to print exact stage commands without downloads, TMDB calls, poster
requests, or writes. Raw MovieLens source preparation is required for stage ranges
containing `candidates` or `ratings`. Source modes are `existing`, `download`, and
`zip`; `existing` requires all four extracted MovieLens CSVs, while `download`
reuses valid raw data first, then a validated cached official ZIP. `--force` on the
legacy downloader performs a fresh validated official download. Corrupt cached ZIPs
are replaced only after a valid replacement is downloaded; custom ZIP mode never
modifies the supplied host ZIP. For a custom ZIP in Docker, mount it read-only;
the CLI path is inside the container:

```bash
docker compose --profile dataset run --rm \
  -v /absolute/host/path/ml-32m.zip:/input/ml-32m.zip:ro \
  dataset --source zip --zip-path /input/ml-32m.zip
```

The imported raw CSVs are written under persistent `DATA_DIR`; the original host ZIP
is not modified. Enrichment requires `MOVIES_RECOMMENDER_TMDB_BEARER_TOKEN`; set it
in the environment (or enter it through the hidden interactive prompt). Use resume
to reuse enrichment progress. Poster download and audit generation are optional.

## Recommender artifact rebuilding

## Quick local workflow

Dataset setup offers Recommended (balanced defaults), Custom (movie count, ratings,
years and minimum distinct tags), and Advanced settings. Minimum tags filters on all
distinct normalized MovieLens tags; maximum stored tags only limits exported tags.
For automation, for example: `python manage.py dataset --non-interactive --source
existing --candidate-min-tags 0 --yes`. The movie count is a maximum and later
validation may produce a smaller catalogue.

Only Python, Docker, and Docker Compose are needed. Choose any writable `DATA_DIR`;
the dataset container creates the portable dataset, and the backend container builds
and loads recommenders. The frontend is optional.

```bash
python manage.py dataset
python manage.py deploy
python manage.py status
python manage.py restart
python manage.py stop
```

Bare commands are interactive; use `--non-interactive --yes` for automation. ZIP
imports are mounted into the dataset container automatically. Deploy asks for model
variants, algorithms, cleanup, and frontend; restart never rebuilds models.

`standard` dataset cleanup removes the pipeline cache and original MovieLens source
files, while retaining the audit report. `minimal` also removes the audit report.
Posters, final CSV files, and the manifest are always retained; MovieLens source data
can be downloaded again for a future dataset regeneration. Model `--clean` removes
optional model exports. `stop` never deletes persistent data. Requests select
algorithms while deployment selects model variants. Manual Compose commands below
remain available as an advanced fallback.

Generating `offline_dataset/` does not rebuild `recommender_models/`. Rebuilding
`recommender_models/` does not regenerate `offline_dataset/`. Rebuild the current
runtime artifacts locally with:

```bash
cd Backend
.venv/bin/python -m pipelines.recommender_build.cli --yes
.venv/bin/python -m pipelines.recommender_build.cli --algorithm item_knn --algorithm biased --yes
.venv/bin/python -m pipelines.recommender_build.cli --algorithm item_knn --clean --yes
```

The maintenance command builds each selected target under `DATA_DIR/tmp`, validates
it, optionally removes non-runtime artifacts with `--clean`, then installs that target
under `recommender_models/` before proceeding to the next selection.
For Compose deployments, copy the root `.env.example` to `.env`; for direct Python
backend runs, copy `Backend/.env.example` to `Backend/.env`. API requests select
algorithms, never variants. Each target replacement uses a same-filesystem sibling
backup; if recovery fails, the error identifies that backup for manual recovery. A
later failed build does not undo targets already installed.
Requests select algorithms, while variants are deployment-internal. Item KNN defaults
to `top_k_100_min_support_25`; `top_k_50_min_support_25` is also a supported profile.
The BMF deployment profile is `factors_128_epochs_100_lr_0_005_reg_0_02`. The API and
maintenance command share active-variant environment settings, and maintenance builds
only the active code-supported profile; arbitrary variant IDs are rejected. Adding a
variant requires registering it in code, and generating a second variant does not make
it active. Changing the active variant requires rebuilding that target and restarting
the API. A future deployment CLI will select supported profiles. Use `--dry-run` for a
read-only input preflight (it exits nonzero when required CSVs are absent), and use
`--yes` for automation; otherwise an interactive terminal confirmation is required.
Unselected variants are preserved. This command neither regenerates the offline
dataset nor creates recommender audits.

In Docker, use the opt-in maintenance profile:

```bash
docker compose --profile maintenance run --rm recommender-build --yes
docker compose --profile maintenance run --rm recommender-build --algorithm biased --yes
docker compose --profile maintenance run --rm recommender-build --algorithm item_knn --clean --yes
```

## Current scope

- Configurable persistent runtime data and Docker deployment foundations.
- No authentication or user accounts.
- No external installation package or Docker Hub publication workflow yet.

## Later phases

- External installation package and Docker Hub publication workflow.
