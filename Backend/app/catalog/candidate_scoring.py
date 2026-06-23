import numpy as np
import pandas as pd


DATA_RELIABILITY_WEIGHTS = {
    "ratingCount": 0.65,
    "averageRating": 0.35,
}

CANDIDATE_SCORE_WEIGHTS = {
    "dataReliabilityScore": 0.60,
    "recencyScore": 0.25,
    "userTags": 0.15,
}

USER_TAGS_SIGNAL_SATURATION_COUNT = 20

RECENCY_SCORE_MIN_YEAR = 1990
RECENCY_SCORE_REFERENCE_YEAR = 2026
RECENCY_SCORE_MIN = 0.40
RECENCY_SCORE_MAX = 1.0
RECENCY_SCORE_BELOW_MIN_YEAR = 0.25
RECENCY_SCORE_MISSING = 0.0


def compute_data_reliability_scores(
    candidates_df: pd.DataFrame,
    *,
    max_rating_count: int,
) -> pd.Series:
    rating_count_signal = (
        np.minimum(
            np.log1p(candidates_df["ratingCount"].to_numpy(dtype=float))
            / np.log1p(max_rating_count),
            1.0,
        )
        if max_rating_count
        else np.zeros(len(candidates_df), dtype=float)
    )
    average_rating_signal = candidates_df["averageRating"].to_numpy(dtype=float) / 5.0

    return pd.Series(
        np.round(
            DATA_RELIABILITY_WEIGHTS["ratingCount"] * rating_count_signal
            + DATA_RELIABILITY_WEIGHTS["averageRating"] * average_rating_signal,
            4,
        ),
        index=candidates_df.index,
    )


def compute_recency_scores(years: pd.Series) -> pd.Series:
    year_values = years.astype("float64").to_numpy()
    scores = np.full(len(year_values), RECENCY_SCORE_BELOW_MIN_YEAR, dtype=float)
    valid_mask = ~np.isnan(year_values)
    recent_mask = valid_mask & (year_values >= RECENCY_SCORE_REFERENCE_YEAR)
    in_range_mask = (
        valid_mask
        & (year_values >= RECENCY_SCORE_MIN_YEAR)
        & (year_values < RECENCY_SCORE_REFERENCE_YEAR)
    )

    scores[recent_mask] = RECENCY_SCORE_MAX
    scores[in_range_mask] = RECENCY_SCORE_MIN + (
        (year_values[in_range_mask] - RECENCY_SCORE_MIN_YEAR)
        / (RECENCY_SCORE_REFERENCE_YEAR - RECENCY_SCORE_MIN_YEAR)
    ) * (RECENCY_SCORE_MAX - RECENCY_SCORE_MIN)
    scores[valid_mask] = np.clip(scores[valid_mask], 0.0, RECENCY_SCORE_MAX)
    scores[~valid_mask] = RECENCY_SCORE_MISSING
    return pd.Series(scores, index=years.index)


def compute_user_tags_scores(candidates_df: pd.DataFrame) -> pd.Series:
    tag_counts = candidates_df["userTags"].apply(
        lambda tags: len(tags) if isinstance(tags, list) else 0
    ).to_numpy(dtype=float)
    user_tags_signal = np.minimum(
        np.log1p(tag_counts) / np.log1p(USER_TAGS_SIGNAL_SATURATION_COUNT),
        1.0,
    )
    return pd.Series(
        np.round(user_tags_signal, 4),
        index=candidates_df.index,
    )


def compute_candidate_scores(candidates_df: pd.DataFrame) -> pd.Series:
    data_reliability_signal = candidates_df["dataReliabilityScore"].to_numpy(dtype=float)
    recency_signal = candidates_df["recencyScore"].to_numpy(dtype=float)
    user_tags_signal = compute_user_tags_scores(candidates_df).to_numpy(dtype=float)

    return pd.Series(
        np.round(
            CANDIDATE_SCORE_WEIGHTS["dataReliabilityScore"] * data_reliability_signal
            + CANDIDATE_SCORE_WEIGHTS["recencyScore"] * recency_signal
            + CANDIDATE_SCORE_WEIGHTS["userTags"] * user_tags_signal,
            4,
        ),
        index=candidates_df.index,
    )
