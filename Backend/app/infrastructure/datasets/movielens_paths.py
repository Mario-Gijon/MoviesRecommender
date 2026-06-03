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

