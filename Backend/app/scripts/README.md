# Scripts

This folder will hold local helper scripts for catalog preparation and maintenance.

Current scripts cover placeholder catalog seeding plus MovieLens 32M download, inspection, candidate-generation, offline TMDB enrichment, enriched-catalog inspection, demo-catalog generation, and CSV review export helpers.

Active MovieLens 32M commands:

- `python -m app.scripts.download_movielens_32m`
- `python -m app.scripts.inspect_movielens_32m`
- `python -m app.scripts.build_movielens_32m_candidates`
- `python -m app.scripts.enrich_movielens_32m_with_tmdb --limit 100`
- `python -m app.scripts.inspect_tmdb_enriched_movielens_32m`
- `python -m app.scripts.build_demo_catalog_from_movielens_32m`
- `python -m app.scripts.export_demo_catalog_32m_review_files`
- `python -m app.scripts.build_demo_ratings_from_movielens_32m`
- `python -m app.scripts.seed_demo_catalog_from_movielens_32m`

The previous `ml-latest-small` pipeline has been removed. MovieLens 32M is now the active offline dataset source.

The 32M demo-catalog JSON now contains:

- `publicCatalog`
- `collaborativeCore`
- `excludedOrSensitive`

`publicCatalog` is the full public set for rating, searching, and recommendations. It is ordered by `standDisplayScore` so the first page is demo-friendly. `collaborativeCore` is internal future collaborative evidence. The CSV review files are for manual review only. Neither step modifies SQLite or the runtime API.

`publicCatalog` is complete by default. `--public-limit` is only for manual experiments or reduced review exports. The frontend should later paginate or progressively render/search the full public catalog.

TMDB enrichment keeps canonical/internal English metadata in `title`, `overview`, `genres`, `keywords`, and related fields. It also stores optional display-oriented localized fields in `displayTitle`, `displayOverview`, and `displayGenres`. `python -m app.scripts.enrich_movielens_32m_with_tmdb --display-language es-ES --resume` can backfill those display fields for already enriched items without replacing canonical metadata.

`python -m app.scripts.build_demo_ratings_from_movielens_32m` creates a processed ratings CSV for the current 32M demo catalog. It streams raw MovieLens 32M `ratings.csv`, filters ratings to `collaborativeCore`, writes processed ratings artifacts for later offline collaborative work, does not modify SQLite, and does not implement collaborative recommendations yet.

Generated processed artifacts should stay out of git.

`python -m app.scripts.seed_demo_catalog_from_movielens_32m` replaces the local runtime SQLite catalog with the processed 32M demo catalog. It uses only local processed JSON, does not call TMDB, maps `publicCatalog` to the current featured/recommendable runtime flags for compatibility, stores `collaborativeCore` for future collaborative filtering, and currently keeps TMDB CDN image URLs for development.
