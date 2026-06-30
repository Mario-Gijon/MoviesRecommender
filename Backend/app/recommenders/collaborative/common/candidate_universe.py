from typing import Literal

import pandas as pd

from app.recommenders.collaborative.common.offline_context import (
    CollaborativeOfflineContext,
    get_default_collaborative_offline_context,
)


CandidateUniverseMode = Literal["public_only", "public_plus_support"]


def load_public_movie_ids(
    offline_context: CollaborativeOfflineContext | None = None,
) -> set[int]:
    context = offline_context or get_default_collaborative_offline_context()
    public_movies = pd.read_csv(
        context.public_movies_csv_path,
        usecols=["movieId"],
        dtype={"movieId": "int32"},
    )
    return set(public_movies["movieId"].drop_duplicates().astype(int))


def load_collaborative_support_movie_ids(
    offline_context: CollaborativeOfflineContext | None = None,
) -> set[int]:
    context = offline_context or get_default_collaborative_offline_context()
    support_movies = pd.read_csv(
        context.collaborative_support_movies_csv_path,
        usecols=["movieId"],
        dtype={"movieId": "int32"},
    )
    return set(support_movies["movieId"].drop_duplicates().astype(int))


def load_candidate_movie_ids(
    *,
    candidate_universe: CandidateUniverseMode,
    offline_context: CollaborativeOfflineContext | None = None,
) -> set[int]:
    public_movie_ids = load_public_movie_ids(offline_context)
    if candidate_universe == "public_only":
        return public_movie_ids

    support_movie_ids = load_collaborative_support_movie_ids(offline_context)
    return set(public_movie_ids) | set(support_movie_ids)


def candidate_policy_label(candidate_universe: CandidateUniverseMode) -> str:
    if candidate_universe == "public_plus_support":
        return "public_plus_support_movies"
    return "public_movies_only"
