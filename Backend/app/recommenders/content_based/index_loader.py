from __future__ import annotations

import json
from functools import lru_cache

from scipy.sparse import load_npz

from .constants import CONTENT_INDEX_REQUIRED_PATHS
from .models import ContentIndex


@lru_cache(maxsize=1)
def load_content_index() -> ContentIndex:
    missing_paths = [
        f"{name}={path}"
        for name, path in CONTENT_INDEX_REQUIRED_PATHS.items()
        if not path.exists()
    ]
    if missing_paths:
        missing_text = ", ".join(missing_paths)
        raise RuntimeError(
            "Content index files are missing. "
            f"Expected files: {missing_text}. "
            "Run python -m app.recommenders.content_based.build_content_index first."
        )

    features = load_npz(CONTENT_INDEX_REQUIRED_PATHS["features"]).tocsr()
    movies = json.loads(CONTENT_INDEX_REQUIRED_PATHS["movies"].read_text(encoding="utf-8"))
    feature_names = json.loads(
        CONTENT_INDEX_REQUIRED_PATHS["featureNames"].read_text(encoding="utf-8")
    )
    metadata = json.loads(CONTENT_INDEX_REQUIRED_PATHS["metadata"].read_text(encoding="utf-8"))

    if features.shape[0] != len(movies):
        raise RuntimeError(
            "Content index row count mismatch: "
            f"matrix has {features.shape[0]} rows but movie index has {len(movies)} rows."
        )
    if features.shape[1] != len(feature_names):
        raise RuntimeError(
            "Content index column count mismatch: "
            f"matrix has {features.shape[1]} columns but feature names list has {len(feature_names)} entries."
        )

    movie_id_to_row_index: dict[int, int] = {}
    for row_index, movie in enumerate(movies):
        movie_id = int(movie["movieId"])
        if movie_id in movie_id_to_row_index:
            raise RuntimeError(f"Duplicate movieId detected in content index: {movie_id}")
        recorded_row_index = int(movie.get("rowIndex", row_index))
        if recorded_row_index != row_index:
            raise RuntimeError(
                f"Row index mismatch for movieId {movie_id}: "
                f"movie index has {recorded_row_index}, expected {row_index}."
            )
        movie_id_to_row_index[movie_id] = row_index

    return ContentIndex(
        features=features,
        movies=movies,
        featureNames=feature_names,
        metadata=metadata,
        movieIdToRowIndex=movie_id_to_row_index,
    )
