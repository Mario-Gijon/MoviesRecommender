# Backend

FastAPI backend for the explainable movie recommender demo.

## Run locally

```bash
uvicorn app.main:app --reload --port 8014
```

## Current scope

- Uses placeholder deterministic data only.
- Includes local settings with a SQLite URL for future integration.
- Exposes health, catalog, featured movies, and recommendation endpoints.
- No external API is used at runtime yet.
- Real TMDB, MovieLens, and offline SQLite catalog build steps will come later.
