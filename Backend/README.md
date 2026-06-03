# Backend

FastAPI backend for the explainable movie recommender demo.

## Run locally

Install dependencies:

```bash
pip install -r requirements.txt
```

MovieLens 32M dataset download/extract:

```bash
python -m app.scripts.download_movielens_32m
```

MovieLens 32M dataset inspection:

```bash
python -m app.scripts.inspect_movielens_32m
```

MovieLens 32M candidate generation:

```bash
python -m app.scripts.build_movielens_32m_candidates
```

MovieLens 32M TMDB enrichment:

```bash
python -m app.scripts.enrich_movielens_32m_with_tmdb --limit 100
```

MovieLens 32M TMDB-enriched catalog inspection:

```bash
python -m app.scripts.inspect_tmdb_enriched_movielens_32m
```

MovieLens 32M demo catalog generation:

```bash
python -m app.scripts.build_demo_catalog_from_movielens_32m
```

MovieLens 32M demo catalog CSV review export:

```bash
python -m app.scripts.export_demo_catalog_32m_review_files
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

- The previous `ml-latest-small` offline pipeline has been removed.
- `ml-32m` is now the active offline MovieLens dataset source.
- The final catalog may later use `ml-25m` or a larger MovieLens dataset.
- Raw and processed MovieLens files should not be committed.
- The 32M utilities do not modify SQLite.
- The 32M utilities do not call TMDB.
- The 32M inspection output is used to decide filters for a more modern demo catalog.
- The 32M candidate builder creates the first filtered modern candidate list from MovieLens 32M.
- The 32M candidate builder does not call TMDB.
- The 32M candidate builder does not modify SQLite.
- The 32M candidate JSON will feed a later TMDB enrichment step.
- 32M TMDB enrichment requires `MOVIES_RECOMMENDER_TMDB_BEARER_TOKEN`.
- 32M TMDB enrichment is offline preprocessing only.
- 32M TMDB enrichment does not modify SQLite or the runtime API.
- Generated enriched files should not be committed.
- Use `--limit` first to test before enriching all candidates.
- 32M TMDB-enriched catalog inspection is offline analysis only.
- Suitability classification is a transparent heuristic for exploration, not an official age-rating decision.
- The 32M demo catalog builder creates a processed demo-catalog JSON for review.
- The 32M CSV export step creates manual review files only.
- The demo catalog contains `publicCatalog`, `collaborativeCore`, and `excludedOrSensitive`.
- `publicCatalog` is the full public set for rating, searching, and recommendations.
- `publicCatalog` is ordered by `standDisplayScore` so the first page is demo-friendly.
- `publicCatalog` is complete by default.
- `--public-limit` is only for manual experiments or reduced review exports.
- The frontend should later paginate or progressively render this list instead of rendering every card at once.
- `collaborativeCore` is internal future collaborative evidence.
- The demo-catalog JSON and review CSVs do not modify SQLite.
- Final SQLite seeding will come after review.
- Suitability and `standDisplayScore` are transparent heuristics for demo preparation, not official age-rating decisions.
- Runtime SQLite and the frontend are not changed by this cleanup.

Examples:

```bash
python -m app.scripts.build_movielens_32m_candidates --limit 2000 --min-ratings 100 --min-year 2000
python -m app.scripts.build_movielens_32m_candidates --limit 3000 --min-ratings 50 --min-year 1995
python -m app.scripts.enrich_movielens_32m_with_tmdb --limit 100
python -m app.scripts.enrich_movielens_32m_with_tmdb --force --sleep 0.35
python -m app.scripts.enrich_movielens_32m_with_tmdb --resume --sleep 0.35
python -m app.scripts.inspect_tmdb_enriched_movielens_32m
python -m app.scripts.build_demo_catalog_from_movielens_32m
python -m app.scripts.build_demo_catalog_from_movielens_32m --public-limit 700
python -m app.scripts.build_demo_catalog_from_movielens_32m --public-limit 200
python -m app.scripts.build_demo_catalog_from_movielens_32m --family-only
python -m app.scripts.export_demo_catalog_32m_review_files
```
