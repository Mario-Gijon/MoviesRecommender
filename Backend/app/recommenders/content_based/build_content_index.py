from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
from scipy.sparse import csr_matrix, hstack, save_npz
from sklearn.feature_extraction import DictVectorizer
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import normalize

from .constants import (
    CONTENT_BASED_OUTPUT_DIR,
    CONTENT_FEATURE_BLOCK_WEIGHTS,
    CONTENT_FEATURE_METADATA_PATH,
    CONTENT_FEATURE_NAMES_PATH,
    CONTENT_INDEX_SUMMARY_PATH,
    MOVIE_CONTENT_FEATURES_PATH,
    MOVIE_CONTENT_INDEX_PATH,
    OPTIONAL_COLUMNS,
    PUBLIC_MOVIES_CSV_PATH,
    REQUIRED_COLUMNS,
    STRUCTURED_TFIDF_CONFIG,
    TEXT_TFIDF_CONFIG,
    TOP_TOKEN_LIMIT,
)
from .feature_parsing import (
    build_prefixed_binary_documents,
    build_text_document,
    is_missing_value,
    normalize_feature_token,
    parse_movie_keywords,
    parse_movie_tags,
    split_pipe_values,
    to_feature_name,
)


def build_content_index(
    *,
    public_movies_path: Path = PUBLIC_MOVIES_CSV_PATH,
    output_dir: Path = CONTENT_BASED_OUTPUT_DIR,
) -> None:
    public_movies_df = _read_public_movies(public_movies_path)
    output_dir.mkdir(parents=True, exist_ok=True)
    features_path = output_dir / MOVIE_CONTENT_FEATURES_PATH.name
    index_path = output_dir / MOVIE_CONTENT_INDEX_PATH.name
    feature_names_path = output_dir / CONTENT_FEATURE_NAMES_PATH.name
    metadata_path = output_dir / CONTENT_FEATURE_METADATA_PATH.name
    summary_path = output_dir / CONTENT_INDEX_SUMMARY_PATH.name

    prepared_movies = _prepare_movies(public_movies_df)
    block_results = _build_all_blocks(prepared_movies)

    final_matrix, feature_names = _combine_blocks(block_results=block_results)
    movie_index = _build_movie_index(prepared_movies)
    metadata = _build_metadata(
        movie_count=len(prepared_movies),
        final_matrix=final_matrix,
        block_results=block_results,
        public_movies_path=public_movies_path,
        output_dir=output_dir,
    )
    summary = _build_summary(
        source_movie_count=len(public_movies_df),
        movies=prepared_movies,
        final_matrix=final_matrix,
        block_results=block_results,
    )

    save_npz(features_path, final_matrix)
    index_path.write_text(
        json.dumps(movie_index, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    feature_names_path.write_text(
        json.dumps(feature_names, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    metadata_path.write_text(
        json.dumps(metadata, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    summary_path.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print(f"Input CSV: {public_movies_path}")
    print(f"Output directory: {output_dir}")
    print(f"Movies indexed: {len(prepared_movies)}")
    print(f"Feature count: {final_matrix.shape[1]}")
    print(f"Non-zero count: {int(final_matrix.nnz)}")
    print(f"Feature matrix: {features_path}")
    print(f"Movie index: {index_path}")
    print(f"Feature names: {feature_names_path}")
    print(f"Feature metadata: {metadata_path}")
    print(f"Content summary: {summary_path}")


def main() -> None:
    build_content_index()


def _read_public_movies(public_movies_path: Path = PUBLIC_MOVIES_CSV_PATH) -> pd.DataFrame:
    if not public_movies_path.exists():
        raise RuntimeError(
            f"Required input CSV is missing: {public_movies_path}. "
            "Generate the offline dataset export first."
        )

    dataframe = pd.read_csv(public_movies_path)
    missing_columns = [column for column in REQUIRED_COLUMNS if column not in dataframe.columns]
    if missing_columns:
        missing_text = ", ".join(missing_columns)
        raise RuntimeError(f"public_movies.csv is missing required columns: {missing_text}")
    if dataframe.empty:
        raise RuntimeError("public_movies.csv is empty. Cannot build a content index.")

    optional_columns = set(OPTIONAL_COLUMNS) | {
        "keywordNames",
        "tmdbKeywordNames",
        "tmdbKeywords",
        "keywords",
    }
    for column in optional_columns:
        if column not in dataframe.columns:
            dataframe[column] = pd.NA

    return dataframe


def _prepare_movies(public_movies_df: pd.DataFrame) -> list[dict[str, Any]]:
    movies: list[dict[str, Any]] = []
    for row_index, row in public_movies_df.iterrows():
        movie_id_hint = _safe_identifier(row.get("movieId"))
        display_title_hint = _safe_identifier(row.get("displayTitle"))
        row_context = f"row {row_index}"
        if movie_id_hint is not None:
            row_context += f", movieId={movie_id_hint}"
        if display_title_hint is not None:
            row_context += f", displayTitle={display_title_hint}"

        movie_id = _parse_int(row.get("movieId"), field_name="movieId", row_context=row_context)
        display_title = _required_text(
            row.get("displayTitle"),
            field_name="displayTitle",
            row_context=row_context,
        )
        genres = _required_pipe_values(
            row.get("genres"),
            field_name="genres",
            row_context=row_context,
        )
        suitability_category = _required_text(
            row.get("suitabilityCategory"),
            field_name="suitabilityCategory",
            row_context=row_context,
        )
        stand_display_score = _parse_float(
            row.get("standDisplayScore"),
            field_name="standDisplayScore",
            row_context=row_context,
        )

        movie = {
            "movieId": movie_id,
            "displayTitle": display_title,
            "year": _optional_int(row.get("year")),
            "suitabilityCategory": suitability_category,
            "standDisplayScore": stand_display_score,
            "posterPath": _optional_text(row.get("posterPath")),
            "genres": genres,
            "userTags": parse_movie_tags(row),
            "keywords": parse_movie_keywords(row),
            "overviewText": build_text_document(row),
            "tmdbPopularity": _optional_float(row.get("tmdbPopularity")),
        }
        movies.append(movie)
    return movies


def _build_all_blocks(movies: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        "genres": _build_genres_block(movies),
        "userTags": _build_user_tags_block(movies),
        "keywords": _build_keywords_block(movies),
        "text": _build_text_block(movies),
        "suitability": _build_suitability_block(movies),
        "context": _build_context_block(movies),
    }


def _build_genres_block(movies: list[dict[str, Any]]) -> dict[str, Any]:
    feature_dicts: list[dict[str, float]] = []
    has_data = False
    for movie in movies:
        features = {}
        for genre in movie["genres"]:
            feature_name = to_feature_name("genre:", genre)
            if feature_name:
                features[feature_name] = 1.0
        if features:
            has_data = True
        feature_dicts.append(features)

    if not has_data:
        return _skipped_block("genres", "No usable genre values found.")

    vectorizer = DictVectorizer(sparse=True, sort=True)
    matrix = vectorizer.fit_transform(feature_dicts).tocsr()
    feature_names = list(vectorizer.get_feature_names_out())
    return _included_block("genres", matrix=matrix, feature_names=feature_names)


def _build_user_tags_block(movies: list[dict[str, Any]]) -> dict[str, Any]:
    documents = build_prefixed_binary_documents(
        [movie["userTags"] for movie in movies],
        prefix="tag:",
    )
    return _build_structured_tfidf_block(
        block_name="userTags",
        documents=documents,
    )


def _build_keywords_block(movies: list[dict[str, Any]]) -> dict[str, Any]:
    if not any(movie["keywords"] for movie in movies):
        return _skipped_block("keywords", "No usable keyword values found in supported keyword columns.")

    documents = build_prefixed_binary_documents(
        [movie["keywords"] for movie in movies],
        prefix="keyword:",
    )
    return _build_structured_tfidf_block(
        block_name="keywords",
        documents=documents,
    )


def _build_structured_tfidf_block(*, block_name: str, documents: list[str]) -> dict[str, Any]:
    if not any(document.strip() for document in documents):
        return _skipped_block(block_name, f"No usable {block_name} values found.")

    vectorizer = TfidfVectorizer(
        analyzer="word",
        binary=STRUCTURED_TFIDF_CONFIG["binary"],
        lowercase=STRUCTURED_TFIDF_CONFIG["lowercase"],
        norm=STRUCTURED_TFIDF_CONFIG["norm"],
        preprocessor=None,
        token_pattern=None,
        tokenizer=str.split,
    )
    try:
        matrix = vectorizer.fit_transform(documents).tocsr()
    except ValueError as exc:
        return _skipped_block(block_name, f"Unable to build {block_name} block: {exc}")

    feature_names = list(vectorizer.get_feature_names_out())
    return _included_block(block_name, matrix=matrix, feature_names=feature_names)


def _build_text_block(movies: list[dict[str, Any]]) -> dict[str, Any]:
    documents = [movie["overviewText"] for movie in movies]
    if not any(document.strip() for document in documents):
        return _skipped_block("text", "No usable overview/tagline text found.")

    vectorizer = TfidfVectorizer(
        max_features=TEXT_TFIDF_CONFIG["max_features"],
        ngram_range=TEXT_TFIDF_CONFIG["ngram_range"],
        min_df=TEXT_TFIDF_CONFIG["min_df"],
        max_df=TEXT_TFIDF_CONFIG["max_df"],
        strip_accents=TEXT_TFIDF_CONFIG["strip_accents"],
        lowercase=TEXT_TFIDF_CONFIG["lowercase"],
        sublinear_tf=TEXT_TFIDF_CONFIG["sublinear_tf"],
        norm=TEXT_TFIDF_CONFIG["norm"],
    )
    try:
        matrix = vectorizer.fit_transform(documents).tocsr()
    except ValueError as exc:
        return _skipped_block("text", f"Unable to build text block: {exc}")

    feature_names = [f"text:{name}" for name in vectorizer.get_feature_names_out()]
    return _included_block("text", matrix=matrix, feature_names=feature_names)


def _build_suitability_block(movies: list[dict[str, Any]]) -> dict[str, Any]:
    feature_dicts: list[dict[str, float]] = []
    has_data = False
    for movie in movies:
        suitability_token = normalize_feature_token(movie["suitabilityCategory"]).replace(" ", "_")
        features = {}
        if suitability_token:
            features[f"suitability:{suitability_token}"] = 1.0
            has_data = True
        feature_dicts.append(features)

    if not has_data:
        return _skipped_block("suitability", "No usable suitability values found.")

    vectorizer = DictVectorizer(sparse=True, sort=True)
    matrix = vectorizer.fit_transform(feature_dicts).tocsr()
    feature_names = list(vectorizer.get_feature_names_out())
    return _included_block("suitability", matrix=matrix, feature_names=feature_names)


def _build_context_block(movies: list[dict[str, Any]]) -> dict[str, Any]:
    feature_dicts: list[dict[str, float]] = []
    has_data = False
    for movie in movies:
        features: dict[str, float] = {}
        stand_bucket = _bucket_stand_quality(movie["standDisplayScore"])
        if stand_bucket:
            features[f"context:stand_quality:{stand_bucket}"] = 1.0
            has_data = True

        popularity_bucket = _bucket_popularity(movie["tmdbPopularity"])
        if popularity_bucket:
            features[f"context:popularity:{popularity_bucket}"] = 1.0
            has_data = True

        decade_bucket = _bucket_decade(movie["year"])
        if decade_bucket:
            features[f"context:decade:{decade_bucket}"] = 1.0
            has_data = True

        feature_dicts.append(features)

    if not has_data:
        return _skipped_block("context", "No usable context values found.")

    vectorizer = DictVectorizer(sparse=True, sort=True)
    matrix = vectorizer.fit_transform(feature_dicts).tocsr()
    feature_names = list(vectorizer.get_feature_names_out())
    return _included_block("context", matrix=matrix, feature_names=feature_names)


def _combine_blocks(
    *,
    block_results: dict[str, dict[str, Any]],
) -> tuple[csr_matrix, list[str]]:
    matrices: list[csr_matrix] = []
    feature_names: list[str] = []

    for block_name in CONTENT_FEATURE_BLOCK_WEIGHTS:
        result = block_results[block_name]
        if result["status"] != "included":
            continue
        normalized_matrix = normalize(result["matrix"], norm="l2", axis=1, copy=True)
        weighted_matrix = normalized_matrix.multiply(CONTENT_FEATURE_BLOCK_WEIGHTS[block_name]).tocsr()
        result["matrix"] = weighted_matrix
        result["featureCount"] = int(weighted_matrix.shape[1])
        result["nonZeroCount"] = int(weighted_matrix.nnz)
        matrices.append(weighted_matrix)
        feature_names.extend(result["feature_names"])

    if not matrices:
        raise RuntimeError("No content feature blocks could be built from public_movies.csv.")

    final_matrix = hstack(matrices, format="csr")
    final_matrix = normalize(final_matrix, norm="l2", axis=1, copy=False)
    return final_matrix, feature_names


def _build_movie_index(movies: list[dict[str, Any]]) -> list[dict[str, Any]]:
    movie_index: list[dict[str, Any]] = []
    for row_index, movie in enumerate(movies):
        movie_index.append(
            {
                "rowIndex": row_index,
                "movieId": movie["movieId"],
                "displayTitle": movie["displayTitle"],
                "year": movie["year"],
                "suitabilityCategory": movie["suitabilityCategory"],
                "standDisplayScore": movie["standDisplayScore"],
                "posterPath": movie["posterPath"],
                "genres": movie["genres"],
                "userTags": movie["userTags"],
                "keywords": movie["keywords"],
            }
        )
    return movie_index


def _build_metadata(
    *,
    movie_count: int,
    final_matrix: csr_matrix,
    block_results: dict[str, dict[str, Any]],
    public_movies_path: Path = PUBLIC_MOVIES_CSV_PATH,
    output_dir: Path = CONTENT_BASED_OUTPUT_DIR,
) -> dict[str, Any]:
    included_blocks = [name for name, result in block_results.items() if result["status"] == "included"]
    skipped_blocks = [
        {"name": name, "reason": result["reason"]}
        for name, result in block_results.items()
        if result["status"] == "skipped"
    ]
    return {
        "generatedAt": _utc_timestamp(),
        "sourcePath": str(public_movies_path),
        "outputDir": str(output_dir),
        "movieCount": movie_count,
        "featureCount": int(final_matrix.shape[1]),
        "nonZeroCount": int(final_matrix.nnz),
        "blockWeights": CONTENT_FEATURE_BLOCK_WEIGHTS,
        "tfidfConfig": {
            "text": {
                **TEXT_TFIDF_CONFIG,
                "ngram_range": list(TEXT_TFIDF_CONFIG["ngram_range"]),
            },
            "userTags": STRUCTURED_TFIDF_CONFIG,
            "keywords": STRUCTURED_TFIDF_CONFIG,
        },
        "includedBlocks": included_blocks,
        "skippedBlocks": skipped_blocks,
        "note": "Built only from public_movies.csv; collaborative_support is not directly recommendable.",
    }


def _build_summary(
    *,
    source_movie_count: int,
    movies: list[dict[str, Any]],
    final_matrix: csr_matrix,
    block_results: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    suitability_counts = Counter(movie["suitabilityCategory"] for movie in movies)
    top_genres = _top_token_counts(movie["genres"] for movie in movies)
    top_user_tags = _top_token_counts(movie["userTags"] for movie in movies)
    top_keywords = _top_token_counts(movie["keywords"] for movie in movies)

    return {
        "sourceMovieCount": source_movie_count,
        "indexedMovieCount": len(movies),
        "droppedMovieCount": source_movie_count - len(movies),
        "movieCount": len(movies),
        "featureCount": int(final_matrix.shape[1]),
        "nonZeroCount": int(final_matrix.nnz),
        "averageNonZeroFeaturesPerMovie": round(float(final_matrix.nnz) / float(len(movies)), 4),
        "moviesWithUserTags": sum(1 for movie in movies if movie["userTags"]),
        "moviesWithKeywords": sum(1 for movie in movies if movie["keywords"]),
        "moviesWithOverview": sum(1 for movie in movies if movie["overviewText"].strip()),
        "suitabilityCounts": dict(sorted(suitability_counts.items())),
        "topGenres": top_genres,
        "topUserTags": top_user_tags,
        "topKeywords": top_keywords if block_results["keywords"]["status"] == "included" else [],
        "blockFeatureCounts": {
            name: int(block_results[name]["featureCount"])
            for name in block_results
        },
    }


def _included_block(block_name: str, *, matrix: csr_matrix, feature_names: list[str]) -> dict[str, Any]:
    return {
        "status": "included",
        "name": block_name,
        "matrix": matrix,
        "feature_names": feature_names,
        "featureCount": int(matrix.shape[1]),
        "nonZeroCount": int(matrix.nnz),
    }


def _skipped_block(block_name: str, reason: str) -> dict[str, Any]:
    return {
        "status": "skipped",
        "name": block_name,
        "reason": reason,
        "featureCount": 0,
        "nonZeroCount": 0,
    }


def _top_token_counts(token_groups: Any) -> list[dict[str, Any]]:
    counter: Counter[str] = Counter()
    for tokens in token_groups:
        normalized_tokens = {
            normalize_feature_token(token)
            for token in tokens
            if normalize_feature_token(token)
        }
        counter.update(normalized_tokens)
    return [
        {"token": token, "count": count}
        for token, count in counter.most_common(TOP_TOKEN_LIMIT)
    ]


def _parse_int(value: object, *, field_name: str, row_context: str) -> int:
    if is_missing_value(value):
        raise RuntimeError(f"Required field {field_name} is empty for {row_context}.")
    return int(value)


def _optional_int(value: object) -> int | None:
    if is_missing_value(value):
        return None
    return int(value)


def _parse_float(value: object, *, field_name: str, row_context: str) -> float:
    if is_missing_value(value):
        raise RuntimeError(f"Required field {field_name} is empty for {row_context}.")
    return float(value)


def _optional_float(value: object) -> float | None:
    if is_missing_value(value):
        return None
    return float(value)


def _required_text(value: object, *, field_name: str, row_context: str) -> str:
    if is_missing_value(value):
        raise RuntimeError(f"Required field {field_name} is empty for {row_context}.")
    text = str(value).strip()
    if not normalize_feature_token(text):
        raise RuntimeError(f"Required field {field_name} is empty for {row_context}.")
    return text


def _optional_text(value: object) -> str | None:
    if is_missing_value(value):
        return None
    text = str(value).strip()
    return text if normalize_feature_token(text) else None


def _required_pipe_values(value: object, *, field_name: str, row_context: str) -> list[str]:
    values = split_pipe_values(value)
    if not values:
        raise RuntimeError(f"Required field {field_name} has no usable values for {row_context}.")
    return values


def _safe_identifier(value: object) -> str | None:
    if is_missing_value(value):
        return None
    return str(value).strip() or None


def _bucket_stand_quality(score: float) -> str:
    if score >= 0.8:
        return "high"
    if score >= 0.6:
        return "medium"
    return "low"


def _bucket_popularity(score: float | None) -> str | None:
    if score is None:
        return None
    if score >= 30:
        return "high"
    if score >= 10:
        return "medium"
    return "low"


def _bucket_decade(year: int | None) -> str | None:
    if year is None:
        return None
    decade_start = (year // 10) * 10
    return f"{decade_start}s"


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


if __name__ == "__main__":
    main()
