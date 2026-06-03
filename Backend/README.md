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

MovieLens development dataset download/extract:

```bash
python -m app.scripts.download_movielens_small
```

MovieLens development dataset inspection:

```bash
python -m app.scripts.inspect_movielens_small
```

MovieLens candidate generation:

```bash
python -m app.scripts.build_movielens_small_candidates
```

Offline TMDB enrichment:

```bash
python -m app.scripts.enrich_movielens_small_with_tmdb --limit 50
```

Offline TMDB-enriched catalog inspection:

```bash
python -m app.scripts.inspect_tmdb_enriched_movielens_small
```

Offline demo catalog build:

```bash
python -m app.scripts.build_demo_catalog_from_movielens_small
```

Demo catalog review export:

```bash
python -m app.scripts.export_demo_catalog_review_files
```

Seed runtime catalog from processed demo catalog:

```bash
python -m app.scripts.seed_demo_catalog_from_movielens_small
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

## MovieLens Development Dataset

- `ml-latest-small` is used only for offline pipeline development and inspection.
- The final catalog may later use `ml-25m` or a larger MovieLens dataset.
- Raw and processed MovieLens files should not be committed.
- Candidate generation only writes a processed JSON file and does not modify the runtime SQLite catalog.
- TMDB enrichment will come later.
- TMDB enrichment requires `MOVIES_RECOMMENDER_TMDB_BEARER_TOKEN`.
- TMDB enrichment is offline preprocessing only and does not modify the runtime SQLite catalog.
- Do not commit `.env` or generated processed files.
- TMDB-enriched catalog inspection is offline analysis only.
- Demo suitability classification is a simple heuristic for exploration, not a final age-rating authority.
- Demo catalog building creates a processed JSON only and does not modify the runtime SQLite catalog.
- Final seeding from the processed demo catalog into SQLite will come later.
- Suitability is a transparent heuristic for demo preparation, not an official age-rating decision.
- `candidateScore` is data/reliability-oriented.
- `standDisplayScore` is stand/audience-display-oriented.
- The display heuristic is transparent and can be adjusted after manual CSV review.
- CSV review files are manual review artifacts only.
- Generated CSV files should not be committed.
- Review export does not modify SQLite or the runtime API.
- Demo catalog seeding replaces the runtime SQLite catalog with already processed local JSON.
- Demo catalog seeding does not call TMDB.
- Images currently use TMDB CDN URLs for development.
- Local image download and offline image serving will come later.
- Development seed scripts reset and recreate the local SQLite catalog schema before inserting data.
- When seeded from the processed MovieLens/TMDB demo catalog, `/catalog/status` reflects demo-catalog counts and `/movies/featured` follows the processed visible-movie order.

Examples:

```bash
python -m app.scripts.build_movielens_small_candidates --limit 500 --min-ratings 20
python -m app.scripts.build_movielens_small_candidates --limit 800 --min-ratings 10 --min-year 1980
python -m app.scripts.enrich_movielens_small_with_tmdb --limit 50
python -m app.scripts.inspect_tmdb_enriched_movielens_small
python -m app.scripts.build_demo_catalog_from_movielens_small --visible-limit 120 --recommendation-limit 220
python -m app.scripts.export_demo_catalog_review_files
python -m app.scripts.seed_demo_catalog_from_movielens_small
```
