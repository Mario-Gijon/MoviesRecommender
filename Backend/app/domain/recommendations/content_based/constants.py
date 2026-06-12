from pathlib import Path


APP_DIR = Path(__file__).resolve().parents[3]
BACKEND_DIR = Path(__file__).resolve().parents[4]
DATA_DIR = APP_DIR / "data"
OFFLINE_DATASET_DIR = DATA_DIR / "offline_dataset"
OFFLINE_DATASET_CSV_DIR = OFFLINE_DATASET_DIR / "csv"
PUBLIC_MOVIES_CSV_PATH = OFFLINE_DATASET_CSV_DIR / "public_movies.csv"
CONTENT_BASED_OUTPUT_DIR = OFFLINE_DATASET_DIR / "recommendations" / "content_based"

MOVIE_CONTENT_FEATURES_PATH = CONTENT_BASED_OUTPUT_DIR / "movie_content_features.npz"
MOVIE_CONTENT_INDEX_PATH = CONTENT_BASED_OUTPUT_DIR / "movie_content_index.json"
CONTENT_FEATURE_NAMES_PATH = CONTENT_BASED_OUTPUT_DIR / "content_feature_names.json"
CONTENT_FEATURE_METADATA_PATH = CONTENT_BASED_OUTPUT_DIR / "content_feature_metadata.json"
CONTENT_INDEX_SUMMARY_PATH = CONTENT_BASED_OUTPUT_DIR / "content_index_summary.json"

REQUIRED_COLUMNS = [
    "movieId",
    "displayTitle",
    "genres",
    "suitabilityCategory",
    "standDisplayScore",
]
OPTIONAL_COLUMNS = [
    "userTags",
    "tmdbKeywords",
    "keywords",
    "overview",
    "tagline",
    "year",
    "tmdbPopularity",
    "posterPath",
]

CONTENT_FEATURE_BLOCK_WEIGHTS = {
    "genres": 1.00,
    "userTags": 0.95,
    "keywords": 0.90,
    "text": 0.70,
    "suitability": 0.25,
    "context": 0.20,
}

TEXT_TFIDF_CONFIG = {
    "max_features": 5000,
    "ngram_range": (1, 2),
    "min_df": 2,
    "max_df": 0.65,
    "strip_accents": "unicode",
    "lowercase": True,
    "sublinear_tf": True,
    "norm": None,
}

STRUCTURED_TFIDF_CONFIG = {
    "binary": True,
    "norm": None,
    "lowercase": False,
}

TOP_TOKEN_LIMIT = 20

MIN_RATING = 1
MAX_RATING = 5
NEUTRAL_RATING = 3
DEFAULT_PROFILE_SIGNAL_LIMIT = 10
DEFAULT_SIMILARITY_LIMIT = 20
MAX_SIMILARITY_LIMIT = 100
DEFAULT_MATCHED_SIGNAL_LIMIT = 8

CONTENT_RECOMMENDATION_SCORE_WEIGHTS = {
    "contentSimilarity": 0.88,
    "standDisplayScore": 0.12,
}

MIN_CONTENT_SIMILARITY_FOR_SCORING = 0.0
DEFAULT_SCORING_LIMIT = 20
MAX_SCORING_LIMIT = 100
MMR_LAMBDA = 0.70
DEFAULT_DIVERSIFIED_LIMIT = 10
MAX_DIVERSIFIED_LIMIT = 50
MMR_CANDIDATE_POOL_SIZE = 100
DEFAULT_EXPLANATION_LIMIT = 10
EXPLANATION_SIGNAL_LIMIT = 4
EXPLANATION_REASON_LIMIT = 3
SIMILAR_RATED_MOVIE_LIMIT = 2

EXPLANATION_SOURCE_WEIGHTS = {
    "tag": 1.00,
    "keyword": 0.95,
    "text": 0.70,
    "genre": 0.55,
}

GENERIC_EXPLANATION_TOKENS = {
    "action",
    "adventure",
    "animation",
    "comedy",
    "family",
    "fantasy",
    "science fiction",
    "drama",
    "romance",
}

NON_EXPLAINABLE_SIGNAL_TOKENS = {
    "duringcreditsstinger",
    "aftercreditsstinger",
    "woman director",
    "based on novel or book",
    "based on true story",
    "sequel",
    "from",
    "his",
    "her",
    "to stop",
    "cliche",
    "anti villain",
    "villain arrested",
    "dyslexia",
    "pin-up",
    "u.s. air force",
    "pearl harbor",
    "young",
    "man",
    "woman",
    "finds",
}

PROFILE_STYLE_SIGNAL_GROUPS = {
    "family": {
        "family friendly",
        "animation",
        "family",
        "comedy",
        "adventure",
    },
    "teen": {
        "teen",
        "action",
        "science fiction",
        "fantasy",
        "superhero",
    },
}

CONTENT_INDEX_REQUIRED_PATHS = {
    "features": MOVIE_CONTENT_FEATURES_PATH,
    "movies": MOVIE_CONTENT_INDEX_PATH,
    "featureNames": CONTENT_FEATURE_NAMES_PATH,
    "metadata": CONTENT_FEATURE_METADATA_PATH,
}
