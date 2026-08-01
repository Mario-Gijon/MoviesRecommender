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

## Current scope

- Local development only.
- No authentication or user accounts.
- Placeholder deterministic recommendations only.

## Docker deployment foundation

This phase provides image-based deployment and local Compose development. It
does not yet provide interactive dataset generation, custom MovieLens ZIP
installation, dataset cleanup, recommender artifact rebuilding, an external
installer, or a Docker Hub publication workflow.

### Production/image-based usage

Copy `.env.example` to `.env`, set image references and choose a persistent
`DATA_DIR`, then start the published API image:

```bash
docker compose up -d api
```

The optional frontend image is enabled explicitly:

```bash
docker compose --profile frontend up -d
```

`compose.yaml` mounts `DATA_DIR` at `/app/data`. The persistent
`offline_dataset/` and `recommender_models/` directories survive container
recreation and are never included in an image build. `docker compose stop`,
`docker compose down`, `docker compose pull`, and `docker compose up -d` do
not delete this bind-mounted data. Manually deleting `DATA_DIR` does.

### Local development

Build and run the API from local source with reload:

```bash
docker compose -f compose.yaml -f compose.dev.yaml up --build api
```

Run the Vite frontend as well:

```bash
docker compose -f compose.yaml -f compose.dev.yaml --profile frontend up --build
```

Development defaults to `VITE_API_URL=http://localhost:8014`. Production
frontend requests use `/api` and Nginx proxies `/api/*`, `/offline/*` poster
paths, and `/audit/*` to the API container.

### Network access

The default bind hosts are `127.0.0.1`, with API port `8014` and frontend port
`5173`. Set `BACKEND_BIND_HOST=0.0.0.0` and/or
`FRONTEND_BIND_HOST=0.0.0.0` when Unity or another client runs on a different
machine. Container ports remain fixed at `8014` and `80` respectively.

## Later phases

- Real TMDB, MovieLens, and SQLite local catalog integration.
- Offline-ready public app behavior without triggering catalog syncs.
- Deployment and packaging details after the local product shape is stable.
