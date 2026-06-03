import argparse
import csv
import json
import re
from collections import Counter, defaultdict

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

    movies = _load_movies()
    ratings_summary, movies_with_ratings = _load_ratings_summary()
    tags_by_movie_id = _load_tags(max_tags_per_movie=args.max_tags_per_movie)
    links_by_movie_id = _load_links()

    max_rating_count = max(
        (stats["ratingCount"] for stats in ratings_summary.values()),
        default=1,
    )

    passed_min_ratings = 0
    passed_year_filter = 0
    candidates = []

    for movie_id, movie in movies.items():
        rating_stats = ratings_summary.get(movie_id)
        if rating_stats is None:
            continue

        if rating_stats["ratingCount"] < args.min_ratings:
            continue
        passed_min_ratings += 1

        year = movie["year"]
        if year is None or year < args.min_year:
            continue
        if args.max_year is not None and year > args.max_year:
            continue
        passed_year_filter += 1

        links = links_by_movie_id.get(movie_id, {"tmdbId": None, "imdbId": None})
        user_tags = tags_by_movie_id.get(movie_id, [])
        data_reliability_score = _compute_data_reliability_score(
            rating_count=rating_stats["ratingCount"],
            average_rating=rating_stats["averageRating"],
            max_rating_count=max_rating_count,
            tmdb_id=links["tmdbId"],
            imdb_id=links["imdbId"],
        )
        recency_score = _compute_recency_score(year)
        tag_availability_signal = 1.0 if user_tags else 0.0
        candidate_score = round(
            0.55 * data_reliability_score
            + 0.30 * recency_score
            + 0.15 * tag_availability_signal,
            4,
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
                "dataReliabilityScore": data_reliability_score,
                "recencyScore": recency_score,
            }
        )

    candidates.sort(
        key=lambda item: (
            -item["candidateScore"],
            -item["recencyScore"],
            -item["dataReliabilityScore"],
            -item["ratingCount"],
            -item["averageRating"],
            item["cleanTitle"],
        )
    )
    candidates = candidates[: args.limit]

    ML_32M_CANDIDATES_PATH.parent.mkdir(parents=True, exist_ok=True)
    ML_32M_CANDIDATES_PATH.write_text(json.dumps(candidates, indent=2), encoding="utf-8")

    print(f"Total movies read: {len(movies)}")
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


def _load_movies() -> dict[int, dict]:
    movies: dict[int, dict] = {}
    with ML_32M_MOVIES_CSV_PATH.open("r", encoding="utf-8", newline="") as file:
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


def _load_ratings_summary() -> tuple[dict[int, dict[str, int | float]], set[int]]:
    ratings_summary: dict[int, dict[str, int | float]] = defaultdict(
        lambda: {"ratingCount": 0, "ratingSum": 0.0}
    )
    movies_with_ratings: set[int] = set()
    with ML_32M_RATINGS_CSV_PATH.open("r", encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)
        for row in reader:
            movie_id = int(row["movieId"])
            rating = float(row["rating"])
            ratings_summary[movie_id]["ratingCount"] += 1
            ratings_summary[movie_id]["ratingSum"] += rating
            movies_with_ratings.add(movie_id)

    finalized_summary: dict[int, dict[str, int | float]] = {}
    for movie_id, stats in ratings_summary.items():
        rating_count = int(stats["ratingCount"])
        rating_sum = float(stats["ratingSum"])
        finalized_summary[movie_id] = {
            "ratingCount": rating_count,
            "averageRating": round(rating_sum / rating_count, 3),
        }
    return finalized_summary, movies_with_ratings


def _load_tags(*, max_tags_per_movie: int) -> dict[int, list[str]]:
    tag_counters: dict[int, Counter[str]] = defaultdict(Counter)
    with ML_32M_TAGS_CSV_PATH.open("r", encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)
        for row in reader:
            movie_id = int(row["movieId"])
            normalized_tag = _normalize_tag(row["tag"])
            if normalized_tag:
                tag_counters[movie_id][normalized_tag] += 1

    tags_by_movie_id: dict[int, list[str]] = {}
    for movie_id, counter in tag_counters.items():
        ordered_tags = sorted(counter.items(), key=lambda item: (-item[1], item[0]))
        tags_by_movie_id[movie_id] = [tag for tag, _count in ordered_tags[:max_tags_per_movie]]
    return tags_by_movie_id


def _load_links() -> dict[int, dict[str, int | str | None]]:
    links_by_movie_id: dict[int, dict[str, int | str | None]] = {}
    with ML_32M_LINKS_CSV_PATH.open("r", encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)
        for row in reader:
            movie_id = int(row["movieId"])
            links_by_movie_id[movie_id] = {
                "tmdbId": int(row["tmdbId"]) if row["tmdbId"] else None,
                "imdbId": row["imdbId"] or None,
            }
    return links_by_movie_id


def _compute_data_reliability_score(
    *,
    rating_count: int,
    average_rating: float,
    max_rating_count: int,
    tmdb_id: int | None,
    imdb_id: str | None,
) -> float:
    rating_count_signal = min(rating_count / max_rating_count, 1.0) if max_rating_count else 0.0
    average_rating_signal = average_rating / 5
    metadata_signal = 1.0 if tmdb_id is not None and imdb_id is not None else 0.5 if tmdb_id is not None or imdb_id is not None else 0.0
    return round(
        0.55 * rating_count_signal
        + 0.30 * average_rating_signal
        + 0.15 * metadata_signal,
        4,
    )


def _compute_recency_score(year: int | None) -> float:
    if year is None:
        return 0.0
    if year >= 2020:
        return 1.0
    if year >= 2015:
        return 0.9
    if year >= 2010:
        return 0.8
    if year >= 2000:
        return 0.7
    if year >= 1995:
        return 0.55
    if year >= 1990:
        return 0.45
    return 0.25


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
