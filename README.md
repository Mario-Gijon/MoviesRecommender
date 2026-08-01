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
frontend uses relative `/api` URLs through Nginx. The `dataset` service is opt-in
with `--profile dataset` and is a safe placeholder in this phase.

## Current scope

- Configurable persistent runtime data and Docker deployment foundations.
- No authentication or user accounts.
- No interactive dataset generator, custom MovieLens ZIP selection, cleanup modes,
  recommender rebuilding command, external installation package, or Docker Hub
  publication workflow yet.

## Later phases

- Interactive dataset generation and MovieLens source selection.
- Dataset cleanup and recommender rebuilding commands.
- External installation package and Docker Hub publication workflow.
