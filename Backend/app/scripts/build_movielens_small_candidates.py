import argparse
import csv
import json
import re
from collections import Counter, defaultdict

from app.infrastructure.datasets.movielens_paths import (
    LINKS_CSV_PATH,
    ML_LATEST_SMALL_CANDIDATES_PATH,
    MOVIES_CSV_PATH,
    RATINGS_CSV_PATH,
    TAGS_CSV_PATH,
)


YEAR_PATTERN = re.compile(r"\((\d{4})\)\s*$")


def main() -> None:
    args = _parse_args()
    _ensure_required_files()

    movies = _load_movies()
    ratings_summary = _load_ratings_summary()
    tags_by_movie_id = _load_tags()
    links_by_movie_id = _load_links()

    top_rating_count = max(
        (stats["ratingCount"] for stats in ratings_summary.values()),
        default=1,
    )

    candidates = []
    for movie_id, movie in movies.items():
        rating_stats = ratings_summary.get(movie_id)
        if rating_stats is None:
            continue

        if rating_stats["ratingCount"] < args.min_ratings:
            continue

        year = movie["year"]
        if args.min_year is not None and (year is None or year < args.min_year):
            continue
        if args.max_year is not None and (year is None or year > args.max_year):
            continue

        links = links_by_movie_id.get(movie_id, {"tmdbId": None, "imdbId": None})
        user_tags = tags_by_movie_id.get(movie_id, [])
        candidate_score = _compute_candidate_score(
            rating_count=rating_stats["ratingCount"],
            average_rating=rating_stats["averageRating"],
            top_rating_count=top_rating_count,
            tmdb_id=links["tmdbId"],
            imdb_id=links["imdbId"],
            user_tags=user_tags,
        )

        candidates.append(
            {
                "movieId": movie_id,
                "title": movie["title"],
                "cleanTitle": movie["cleanTitle"],
                "year": year,
                "genres": movie["genres"],
                "ratingCount": rating_stats["ratingCount"],
                "averageRating": rating_stats["averageRating"],
                "tmdbId": links["tmdbId"],
                "imdbId": links["imdbId"],
                "userTags": user_tags,
                "candidateScore": candidate_score,
            }
        )

    candidates.sort(
        key=lambda item: (
            -item["candidateScore"],
            -item["ratingCount"],
            -item["averageRating"],
            item["title"],
        )
    )
    candidates = candidates[: args.limit]

    ML_LATEST_SMALL_CANDIDATES_PATH.parent.mkdir(parents=True, exist_ok=True)
    ML_LATEST_SMALL_CANDIDATES_PATH.write_text(
        json.dumps(candidates, indent=2),
        encoding="utf-8",
    )

    print(f"Total movies read: {len(movies)}")
    print(f"Total movies with ratings: {len(ratings_summary)}")
    print(f"Candidates written: {len(candidates)}")
    print(f"Min ratings used: {args.min_ratings}")
    print(f"Output path: {ML_LATEST_SMALL_CANDIDATES_PATH}")
    print("Top 10 candidates:")
    for item in candidates[:10]:
        print(
            f"- {item['title']} | score={item['candidateScore']} | "
            f"ratingCount={item['ratingCount']} | averageRating={item['averageRating']}"
        )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a processed MovieLens latest-small candidate list.",
    )
    parser.add_argument("--limit", type=int, default=500)
    parser.add_argument("--min-ratings", type=int, default=20)
    parser.add_argument("--min-year", type=int)
    parser.add_argument("--max-year", type=int)
    return parser.parse_args()


def _ensure_required_files() -> None:
    required_files = [MOVIES_CSV_PATH, RATINGS_CSV_PATH, TAGS_CSV_PATH, LINKS_CSV_PATH]
    missing_files = [path for path in required_files if not path.exists()]
    if missing_files:
        missing_text = ", ".join(str(path) for path in missing_files)
        raise RuntimeError(
            "MovieLens latest-small files are missing. "
            "Run `python -m app.scripts.download_movielens_small` first. "
            f"Missing: {missing_text}"
        )


def _load_movies() -> dict[int, dict]:
    movies: dict[int, dict] = {}
    with MOVIES_CSV_PATH.open("r", encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)
        for row in reader:
            movie_id = int(row["movieId"])
            title = row["title"]
            movies[movie_id] = {
                "title": title,
                "cleanTitle": _clean_title(title),
                "year": _parse_year_from_title(title),
                "genres": _parse_genres(row["genres"]),
            }
    return movies


def _load_ratings_summary() -> dict[int, dict[str, int | float]]:
    ratings_summary: dict[int, dict[str, int | float]] = defaultdict(
        lambda: {"ratingCount": 0, "ratingSum": 0.0}
    )
    with RATINGS_CSV_PATH.open("r", encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)
        for row in reader:
            movie_id = int(row["movieId"])
            rating = float(row["rating"])
            ratings_summary[movie_id]["ratingCount"] += 1
            ratings_summary[movie_id]["ratingSum"] += rating

    finalized_summary: dict[int, dict[str, int | float]] = {}
    for movie_id, stats in ratings_summary.items():
        rating_count = int(stats["ratingCount"])
        rating_sum = float(stats["ratingSum"])
        finalized_summary[movie_id] = {
            "ratingCount": rating_count,
            "averageRating": round(rating_sum / rating_count, 3),
        }
    return finalized_summary


def _load_tags() -> dict[int, list[str]]:
    tag_counters: dict[int, Counter[str]] = defaultdict(Counter)
    with TAGS_CSV_PATH.open("r", encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)
        for row in reader:
            movie_id = int(row["movieId"])
            normalized_tag = _normalize_tag(row["tag"])
            if normalized_tag:
                tag_counters[movie_id][normalized_tag] += 1

    tags_by_movie_id: dict[int, list[str]] = {}
    for movie_id, counter in tag_counters.items():
        ordered_tags = sorted(counter.items(), key=lambda item: (-item[1], item[0]))
        tags_by_movie_id[movie_id] = [tag for tag, _count in ordered_tags[:8]]
    return tags_by_movie_id


def _load_links() -> dict[int, dict[str, int | str | None]]:
    links_by_movie_id: dict[int, dict[str, int | str | None]] = {}
    with LINKS_CSV_PATH.open("r", encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)
        for row in reader:
            movie_id = int(row["movieId"])
            links_by_movie_id[movie_id] = {
                "tmdbId": int(row["tmdbId"]) if row["tmdbId"] else None,
                "imdbId": row["imdbId"] or None,
            }
    return links_by_movie_id


def _compute_candidate_score(
    *,
    rating_count: int,
    average_rating: float,
    top_rating_count: int,
    tmdb_id: int | None,
    imdb_id: str | None,
    user_tags: list[str],
) -> float:
    rating_count_signal = min(rating_count, top_rating_count) / top_rating_count if top_rating_count else 0.0
    average_rating_signal = average_rating / 5
    metadata_signal = 1.0 if tmdb_id is not None and imdb_id is not None else 0.5 if tmdb_id is not None or imdb_id is not None else 0.0
    tag_signal = 1.0 if user_tags else 0.0

    score = (
        0.45 * rating_count_signal
        + 0.35 * average_rating_signal
        + 0.15 * metadata_signal
        + 0.05 * tag_signal
    )
    return round(score, 4)


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
