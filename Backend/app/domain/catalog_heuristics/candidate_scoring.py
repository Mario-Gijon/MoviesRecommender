import numpy as np
import pandas as pd


DATA_RELIABILITY_WEIGHTS = {
    "ratingCount": 0.55,
    "averageRating": 0.30,
    "metadata": 0.15,
}

CANDIDATE_SCORE_WEIGHTS = {
    "dataReliabilityScore": 0.55,
    "recencyScore": 0.30,
    "userTags": 0.15,
}

RECENCY_SCORE_BUCKETS = [
    (2020, 1.0),
    (2015, 0.9),
    (2010, 0.8),
    (2000, 0.7),
    (1995, 0.55),
    (1990, 0.45),
]

RECENCY_SCORE_DEFAULT = 0.25
RECENCY_SCORE_MISSING = 0.0


def compute_data_reliability_scores(
    candidates_df: pd.DataFrame,
    *,
    max_rating_count: int,
) -> pd.Series:
    rating_count_signal = (
        np.minimum(
            candidates_df["ratingCount"].to_numpy(dtype=float) / max_rating_count,
            1.0,
        )
        if max_rating_count
        else np.zeros(len(candidates_df), dtype=float)
    )
    average_rating_signal = candidates_df["averageRating"].to_numpy(dtype=float) / 5.0
    has_tmdb = candidates_df["tmdbId"].notna().to_numpy()
    has_imdb = candidates_df["imdbId"].notna().to_numpy()
    metadata_signal = np.select(
        [has_tmdb & has_imdb, has_tmdb | has_imdb],
        [1.0, 0.5],
        default=0.0,
    )

    return pd.Series(
        np.round(
            DATA_RELIABILITY_WEIGHTS["ratingCount"] * rating_count_signal
            + DATA_RELIABILITY_WEIGHTS["averageRating"] * average_rating_signal
            + DATA_RELIABILITY_WEIGHTS["metadata"] * metadata_signal,
            4,
        ),
        index=candidates_df.index,
    )


def compute_recency_scores(years: pd.Series) -> pd.Series:
    year_values = years.astype("float64").to_numpy()
    scores = np.select(
        [year_values >= threshold for threshold, _ in RECENCY_SCORE_BUCKETS],
        [score for _, score in RECENCY_SCORE_BUCKETS],
        default=RECENCY_SCORE_DEFAULT,
    )
    scores[np.isnan(year_values)] = RECENCY_SCORE_MISSING
    return pd.Series(scores, index=years.index)


def compute_candidate_scores(candidates_df: pd.DataFrame) -> pd.Series:
    user_tags_signal = candidates_df["userTags"].apply(lambda tags: 1.0 if tags else 0.0)
    return pd.Series(
        np.round(
            CANDIDATE_SCORE_WEIGHTS["dataReliabilityScore"]
            * candidates_df["dataReliabilityScore"].to_numpy(dtype=float)
            + CANDIDATE_SCORE_WEIGHTS["recencyScore"]
            * candidates_df["recencyScore"].to_numpy(dtype=float)
            + CANDIDATE_SCORE_WEIGHTS["userTags"] * user_tags_signal.to_numpy(dtype=float),
            4,
        ),
        index=candidates_df.index,
    )
