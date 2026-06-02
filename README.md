# Movies Recommender
<<<<<<< HEAD
=======

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
- No Docker or deployment setup yet.
- No authentication or user accounts.
- Placeholder deterministic recommendations only.

## Later phases

- Real TMDB, MovieLens, and SQLite local catalog integration.
- Offline-ready public app behavior without triggering catalog syncs.
- Deployment and packaging details after the local product shape is stable.
>>>>>>> e1a3c90 (Refactor pages frontend)
