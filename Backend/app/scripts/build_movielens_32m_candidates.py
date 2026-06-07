import argparse
import json
import re

import pandas as pd

from app.domain.catalog_heuristics.candidate_scoring import (
    compute_candidate_scores,
    compute_data_reliability_scores,
    compute_recency_scores,
)
from app.infrastructure.datasets.movielens_paths import (
    ML_32M_CANDIDATES_PATH,
    ML_32M_LINKS_CSV_PATH,
    ML_32M_MOVIES_CSV_PATH,
    ML_32M_RATINGS_CSV_PATH,
    ML_32M_TAGS_CSV_PATH,
)


YEAR_PATTERN = re.compile(r"\((\d{4})\)\s*$")


def main() -> None:
    args = _parse_args()
    _ensure_required_files()

    movies_df = _load_movies()
    ratings_summary_df, movies_with_ratings = _load_ratings_summary()
    tags_df = _load_tags(max_tags_per_movie=args.max_tags_per_movie)
    links_df = _load_links()

    total_movies_read = len(movies_df)
    max_rating_count = int(ratings_summary_df["ratingCount"].max()) if not ratings_summary_df.empty else 1

    candidates_df = movies_df.merge(ratings_summary_df, on="movieId", how="inner")
    candidates_df = candidates_df.merge(links_df, on="movieId", how="left")
    candidates_df = candidates_df.merge(tags_df, on="movieId", how="left")

    candidates_df["tmdbId"] = candidates_df["tmdbId"].astype("Int64")
    candidates_df["imdbId"] = candidates_df["imdbId"].where(
        candidates_df["imdbId"].notna(),
        None,
    )
    candidates_df["userTags"] = candidates_df["userTags"].apply(
        lambda value: value if isinstance(value, list) else []
    )

    min_ratings_mask = candidates_df["ratingCount"] >= args.min_ratings
    passed_min_ratings = int(min_ratings_mask.sum())
    candidates_df = candidates_df[min_ratings_mask].copy()

    year_mask = candidates_df["year"].notna() & (candidates_df["year"] >= args.min_year)
    if args.max_year is not None:
        year_mask &= candidates_df["year"] <= args.max_year
    passed_year_filter = int(year_mask.sum())
    candidates_df = candidates_df[year_mask].copy()

    candidates_df["dataReliabilityScore"] = compute_data_reliability_scores(
        candidates_df,
        max_rating_count=max_rating_count,
    )
    candidates_df["recencyScore"] = compute_recency_scores(candidates_df["year"])
    candidates_df["candidateScore"] = compute_candidate_scores(candidates_df)

    candidates_df = candidates_df.sort_values(
        by=[
            "candidateScore",
            "recencyScore",
            "dataReliabilityScore",
            "ratingCount",
            "averageRating",
            "cleanTitle",
        ],
        ascending=[False, False, False, False, False, True],
        kind="mergesort",
    ).head(args.limit)

    candidates = _serialize_candidates(candidates_df)

    ML_32M_CANDIDATES_PATH.parent.mkdir(parents=True, exist_ok=True)
    ML_32M_CANDIDATES_PATH.write_text(json.dumps(candidates, indent=2), encoding="utf-8")

    print(f"Total movies read: {total_movies_read}")
    print(f"Total movies with ratings: {len(movies_with_ratings)}")
    print(f"Movies passing min ratings: {passed_min_ratings}")
    print(f"Movies passing year filter: {passed_year_filter}")
    print(f"Candidates written: {len(candidates)}")
    print(f"Min ratings used: {args.min_ratings}")
    print(f"Min year used: {args.min_year}")
    print(f"Output path: {ML_32M_CANDIDATES_PATH}")
    print("Top 20 candidate titles:")
    for item in candidates[:20]:
        print(
            f"- {item['cleanTitle']} ({item['year']}) | score={item['candidateScore']} | "
            f"ratingCount={item['ratingCount']} | averageRating={item['averageRating']} | "
            f"tmdbId={item['tmdbId']}"
        )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a filtered modern candidate list from MovieLens 32M.",
    )
    parser.add_argument("--limit", type=int, default=2000)
    parser.add_argument("--min-ratings", type=int, default=100)
    parser.add_argument("--min-year", type=int, default=2000)
    parser.add_argument("--max-year", type=int)
    parser.add_argument("--max-tags-per-movie", type=int, default=10)
    return parser.parse_args()


def _ensure_required_files() -> None:
    required_files = [
        ML_32M_MOVIES_CSV_PATH,
        ML_32M_RATINGS_CSV_PATH,
        ML_32M_TAGS_CSV_PATH,
        ML_32M_LINKS_CSV_PATH,
    ]
    missing_files = [path for path in required_files if not path.exists()]
    if missing_files:
        missing_text = ", ".join(str(path) for path in missing_files)
        raise RuntimeError(
            "MovieLens 32M files are missing. "
            "Run `python -m app.scripts.download_movielens_32m` first. "
            f"Missing: {missing_text}"
        )


def _load_movies() -> pd.DataFrame:
    movies_df = pd.read_csv(
        ML_32M_MOVIES_CSV_PATH,
        usecols=["movieId", "title", "genres"],
        dtype={"movieId": "int64", "title": "string", "genres": "string"},
    )
    movies_df["cleanTitle"] = movies_df["title"].apply(_clean_title)
    movies_df["year"] = movies_df["title"].apply(_parse_year_from_title).astype("Int64")
    movies_df["genres"] = movies_df["genres"].apply(_parse_genres)
    return movies_df[["movieId", "title", "cleanTitle", "year", "genres"]]


def _load_ratings_summary() -> tuple[pd.DataFrame, set[int]]:
    ratings_df = pd.read_csv(
        ML_32M_RATINGS_CSV_PATH,
        usecols=["movieId", "rating"],
        dtype={"movieId": "int64", "rating": "float64"},
    )
    movies_with_ratings = set(ratings_df["movieId"].unique().tolist())
    summary_df = (
        ratings_df.groupby("movieId", sort=False)["rating"]
        .agg(ratingCount="size", averageRating="mean")
        .reset_index()
    )
    summary_df["ratingCount"] = summary_df["ratingCount"].astype("int64")
    summary_df["averageRating"] = summary_df["averageRating"].round(3)
    return summary_df, movies_with_ratings


def _load_tags(*, max_tags_per_movie: int) -> pd.DataFrame:
    tags_df = pd.read_csv(
        ML_32M_TAGS_CSV_PATH,
        usecols=["movieId", "tag"],
        dtype={"movieId": "int64", "tag": "string"},
    )
    tags_df["tag"] = tags_df["tag"].fillna("").apply(_normalize_tag)
    tags_df = tags_df[tags_df["tag"] != ""].copy()
    if tags_df.empty:
        return pd.DataFrame(columns=["movieId", "userTags"])

    tag_counts_df = (
        tags_df.groupby(["movieId", "tag"], sort=False)
        .size()
        .reset_index(name="tagCount")
        .sort_values(
            by=["movieId", "tagCount", "tag"],
            ascending=[True, False, True],
            kind="mergesort",
        )
    )
    top_tags_df = tag_counts_df.groupby("movieId", sort=False).head(max_tags_per_movie)
    user_tags_df = (
        top_tags_df.groupby("movieId", sort=False)["tag"]
        .agg(list)
        .reset_index(name="userTags")
    )
    return user_tags_df


def _load_links() -> pd.DataFrame:
    links_df = pd.read_csv(
        ML_32M_LINKS_CSV_PATH,
        usecols=["movieId", "imdbId", "tmdbId"],
        dtype={"movieId": "int64", "imdbId": "string", "tmdbId": "string"},
    )
    links_df["imdbId"] = links_df["imdbId"].replace({"": pd.NA})
    links_df["tmdbId"] = pd.to_numeric(links_df["tmdbId"], errors="coerce").astype("Int64")
    return links_df


def _serialize_candidates(candidates_df: pd.DataFrame) -> list[dict[str, object]]:
    candidates: list[dict[str, object]] = []
    for row in candidates_df.itertuples(index=False):
        tmdb_id = None if pd.isna(row.tmdbId) else int(row.tmdbId)
        imdb_id = None if pd.isna(row.imdbId) else str(row.imdbId)
        year = None if pd.isna(row.year) else int(row.year)
        candidates.append(
            {
                "movieId": int(row.movieId),
                "title": str(row.title),
                "cleanTitle": str(row.cleanTitle),
                "year": year,
                "genres": [str(genre) for genre in row.genres],
                "ratingCount": int(row.ratingCount),
                "averageRating": float(row.averageRating),
                "tmdbId": tmdb_id,
                "imdbId": imdb_id,
                "userTags": [str(tag) for tag in row.userTags],
                "candidateScore": float(row.candidateScore),
                "dataReliabilityScore": float(row.dataReliabilityScore),
                "recencyScore": float(row.recencyScore),
            }
        )
    return candidates


def _clean_title(title: str) -> str:
    return YEAR_PATTERN.sub("", title).strip()


def _parse_year_from_title(title: str) -> int | None:
    match = YEAR_PATTERN.search(title)
    if not match:
        return None
    return int(match.group(1))


def _parse_genres(raw_genres: str) -> list[str]:
    if raw_genres == "(no genres listed)":
        return []
    return [genre for genre in raw_genres.split("|") if genre]


def _normalize_tag(tag: str) -> str:
    return " ".join(tag.strip().lower().split())


if __name__ == "__main__":
    main()
