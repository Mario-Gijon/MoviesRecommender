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

Docker users configure `DATA_DIR` in `.env`; the interactive manager supplies the
appropriate Compose environment internally. `MOVIES_RECOMMENDER_DATA_DIR=/app/data`
is used inside backend containers. It is only relevant when running Python directly
outside Docker, where its default remains `Backend/data`.

The backend is available by itself on `${BACKEND_BIND_HOST}:${BACKEND_PORT}`. The
optional production frontend is served on `${FRONTEND_BIND_HOST}:${FRONTEND_PORT}`
and proxies `/api/`, `/offline/`, and `/audit/` to the backend internally. Defaults
bind to `127.0.0.1`; set either bind host to `0.0.0.0` only when LAN/server access is
intended. Image names, ports, bind hosts, and `DATA_DIR` are configurable in `.env`.

The manager selects source-mounted local development or published-image production.
The development frontend keeps `VITE_API_URL=http://localhost:8014`; the production
frontend uses relative `/api` URLs through Nginx.

## Dataset generation

The opt-in `dataset` service generates `offline_dataset/` from MovieLens 32M and
TMDB metadata. It reuses valid raw files and cached work where possible, but
regenerates the selected candidate, enrichment, catalogue, ratings, export, poster,
and audit outputs. It never rebuilds `recommender_models/`.

During this transition phase, choose Dataset from `python manage.py` to open the
existing interactive wizard.

The `recommended` profile creates the broad 15,000-item configuration; choose
`custom` in the wizard for individual limits, years, language, stages, poster and
audit options. Deterministic installation-style use is available with, for example:

```bash
MOVIES_RECOMMENDER_TMDB_BEARER_TOKEN='...' \
  .venv/bin/python -m pipelines.dataset_generation.cli \
  --non-interactive --yes --source download --preset recommended --audit
```

The imported raw CSVs are written under persistent `DATA_DIR`; the original host ZIP
is not modified. Enrichment requires `MOVIES_RECOMMENDER_TMDB_BEARER_TOKEN`; set it
in the environment (or enter it through the existing interactive prompt). Dataset
source selection, resume behavior, poster download, audit generation and cleanup are
being redesigned in the next phase.

## Gestor interactivo

Only Python, Docker, and Docker Compose are needed. Configure any writable
`DATA_DIR`, then start the manager with:

```bash
python manage.py
```

The manager guides application lifecycle actions without requiring Compose commands,
profiles, flags, or algorithm selections. Development uses local code with reload and
HMR; Production uses the published images. Recommendation-model rebuilding always
uses the active variants declared in `.env` and keeps `DATA_DIR` persistent.

Dataset currently opens its existing interactive flow while its dedicated management
phase is prepared. Configuration management is the next phase.

## Recommender artifact rebuilding

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

The interactive manager runs this maintenance flow with the appropriate environment
and profile; it is not necessary to invoke Docker Compose directly.

## Current scope

- Configurable persistent runtime data and Docker deployment foundations.
- No authentication or user accounts.
- No external installation package or Docker Hub publication workflow yet.

## Later phases

- External installation package and Docker Hub publication workflow.
