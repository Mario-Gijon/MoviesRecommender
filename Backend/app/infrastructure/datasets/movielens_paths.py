from pathlib import Path


DATA_DIR = Path(__file__).resolve().parents[2] / "data"
RAW_MOVIELENS_DIR = DATA_DIR / "raw" / "movielens"
PROCESSED_MOVIELENS_DIR = DATA_DIR / "processed" / "movielens"

ML_LATEST_SMALL_ZIP_PATH = RAW_MOVIELENS_DIR / "ml-latest-small.zip"
ML_LATEST_SMALL_EXTRACT_DIR = RAW_MOVIELENS_DIR / "ml-latest-small"
ML_LATEST_SMALL_DATASET_DIR = ML_LATEST_SMALL_EXTRACT_DIR / "ml-latest-small"

MOVIES_CSV_PATH = ML_LATEST_SMALL_DATASET_DIR / "movies.csv"
RATINGS_CSV_PATH = ML_LATEST_SMALL_DATASET_DIR / "ratings.csv"
TAGS_CSV_PATH = ML_LATEST_SMALL_DATASET_DIR / "tags.csv"
LINKS_CSV_PATH = ML_LATEST_SMALL_DATASET_DIR / "links.csv"

ML_LATEST_SMALL_SUMMARY_PATH = PROCESSED_MOVIELENS_DIR / "ml_latest_small_summary.json"
ML_LATEST_SMALL_CANDIDATES_PATH = PROCESSED_MOVIELENS_DIR / "ml_latest_small_candidates.json"
ML_LATEST_SMALL_TMDB_ENRICHED_PATH = PROCESSED_MOVIELENS_DIR / "ml_latest_small_tmdb_enriched.json"
ML_LATEST_SMALL_TMDB_INSPECTION_PATH = PROCESSED_MOVIELENS_DIR / "ml_latest_small_tmdb_inspection.json"
ML_LATEST_SMALL_DEMO_CATALOG_PATH = PROCESSED_MOVIELENS_DIR / "ml_latest_small_demo_catalog.json"
ML_LATEST_SMALL_DEMO_CATALOG_VISIBLE_CSV_PATH = PROCESSED_MOVIELENS_DIR / "ml_latest_small_demo_catalog_visible.csv"
ML_LATEST_SMALL_DEMO_CATALOG_RECOMMENDATION_POOL_CSV_PATH = PROCESSED_MOVIELENS_DIR / "ml_latest_small_demo_catalog_recommendation_pool.csv"
ML_LATEST_SMALL_DEMO_CATALOG_COLLABORATIVE_CORE_CSV_PATH = PROCESSED_MOVIELENS_DIR / "ml_latest_small_demo_catalog_collaborative_core.csv"
ML_LATEST_SMALL_DEMO_CATALOG_EXCLUDED_CSV_PATH = PROCESSED_MOVIELENS_DIR / "ml_latest_small_demo_catalog_excluded.csv"
