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
requests, or writes. Source modes are `existing`, `download`, and `zip`; `existing`
requires all four extracted MovieLens CSVs, while `download` reuses a valid cached
official ZIP and existing raw data. For a custom ZIP in Docker, mount it read-only;
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

## Current scope

- Configurable persistent runtime data and Docker deployment foundations.
- No authentication or user accounts.
- No dataset cleanup modes, recommender rebuilding command, external installation
  package, or Docker Hub publication workflow yet.

## Later phases

- Dataset cleanup and recommender rebuilding commands.
- External installation package and Docker Hub publication workflow.
