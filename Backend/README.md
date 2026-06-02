# Backend

FastAPI backend for the explainable movie recommender demo.

## Run locally

Install dependencies:

```bash
pip install -r requirements.txt
```

Seed placeholder catalog:

```bash
python -m app.scripts.seed_placeholder_catalog
```

Run API:

```bash
uvicorn app.main:app --reload --port 8014
```

## Current scope

- Uses placeholder deterministic data only.
- SQLite currently stores placeholder catalog data.
- Exposes health, catalog, featured movies, and recommendation endpoints.
- No external API is used at runtime yet.
- Placeholder external IDs remain `null` until the offline TMDB/MovieLens pipeline is implemented.
- Real TMDB, MovieLens, and offline SQLite catalog build steps will replace the placeholder seed later.
