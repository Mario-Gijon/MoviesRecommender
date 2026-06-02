import csv
import json
import re
from collections import defaultdict

from app.infrastructure.datasets.movielens_paths import (
    LINKS_CSV_PATH,
    ML_LATEST_SMALL_SUMMARY_PATH,
    MOVIES_CSV_PATH,
    RATINGS_CSV_PATH,
    TAGS_CSV_PATH,
)


YEAR_PATTERN = re.compile(r"\((\d{4})\)\s*$")


def main() -> None:
    _ensure_required_files()

    movies = _load_movies()
    ratings_summary, unique_users = _load_ratings_summary()
    tags_count = _count_rows(TAGS_CSV_PATH)
    links_by_movie_id, movies_with_tmdb_id, movies_with_imdb_id = _load_links()

    years = [movie["year"] for movie in movies.values() if movie["year"] is not None]
    movies_without_year = sum(1 for movie in movies.values() if movie["year"] is None)

    top_movies = []
    for movie_id, stats in sorted(
        ratings_summary.items(),
        key=lambda item: (-item[1]["count"], item[0]),
    )[:10]:
        movie = movies.get(movie_id, {"title": "Unknown title", "year": None})
        links = links_by_movie_id.get(movie_id, {})
        top_movies.append(
            {
                "movieId": movie_id,
                "title": movie["title"],
                "ratingCount": stats["count"],
                "averageRating": round(stats["sum"] / stats["count"], 3),
                "tmdbId": links.get("tmdbId"),
                "imdbId": links.get("imdbId"),
            }
        )

    summary = {
        "moviesCount": len(movies),
        "ratingsCount": sum(stats["count"] for stats in ratings_summary.values()),
        "tagsCount": tags_count,
        "linksCount": len(links_by_movie_id),
        "uniqueUsersCount": len(unique_users),
        "moviesWithTmdbId": movies_with_tmdb_id,
        "moviesWithImdbId": movies_with_imdb_id,
        "yearCoverage": {
            "earliestYear": min(years) if years else None,
            "latestYear": max(years) if years else None,
            "moviesWithoutParsedYear": movies_without_year,
        },
        "topMoviesByRatingCount": top_movies,
    }

    ML_LATEST_SMALL_SUMMARY_PATH.parent.mkdir(parents=True, exist_ok=True)
    ML_LATEST_SMALL_SUMMARY_PATH.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print(f"Movies: {summary['moviesCount']}")
    print(f"Ratings: {summary['ratingsCount']}")
    print(f"Tags: {summary['tagsCount']}")
    print(f"Links: {summary['linksCount']}")
    print(f"Unique users: {summary['uniqueUsersCount']}")
    print(f"Movies with tmdbId: {summary['moviesWithTmdbId']}")
    print(f"Movies with imdbId: {summary['moviesWithImdbId']}")
    print(
        f"Year coverage: earliest={summary['yearCoverage']['earliestYear']}, "
        f"latest={summary['yearCoverage']['latestYear']}, "
        f"without_year={summary['yearCoverage']['moviesWithoutParsedYear']}"
    )
    print("Top 10 movies by rating count:")
    for item in top_movies:
        print(
            f"- movieId={item['movieId']}, title={item['title']}, "
            f"rating_count={item['ratingCount']}, average_rating={item['averageRating']}, "
            f"tmdbId={item['tmdbId']}, imdbId={item['imdbId']}"
        )
    print(f"Summary written to: {ML_LATEST_SMALL_SUMMARY_PATH}")


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
                "year": _parse_year_from_title(title),
            }
    return movies


def _load_ratings_summary() -> tuple[dict[int, dict[str, float]], set[int]]:
    ratings_summary: dict[int, dict[str, float]] = defaultdict(lambda: {"count": 0, "sum": 0.0})
    unique_users: set[int] = set()
    with RATINGS_CSV_PATH.open("r", encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)
        for row in reader:
            movie_id = int(row["movieId"])
            user_id = int(row["userId"])
            rating = float(row["rating"])
            ratings_summary[movie_id]["count"] += 1
            ratings_summary[movie_id]["sum"] += rating
            unique_users.add(user_id)
    return ratings_summary, unique_users


def _load_links() -> tuple[dict[int, dict[str, int | str | None]], int, int]:
    links_by_movie_id: dict[int, dict[str, int | str | None]] = {}
    movies_with_tmdb_id = 0
    movies_with_imdb_id = 0

    with LINKS_CSV_PATH.open("r", encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)
        for row in reader:
            movie_id = int(row["movieId"])
            imdb_id = row["imdbId"] or None
            tmdb_id = int(row["tmdbId"]) if row["tmdbId"] else None
            links_by_movie_id[movie_id] = {
                "imdbId": imdb_id,
                "tmdbId": tmdb_id,
            }
            if imdb_id is not None:
                movies_with_imdb_id += 1
            if tmdb_id is not None:
                movies_with_tmdb_id += 1

    return links_by_movie_id, movies_with_tmdb_id, movies_with_imdb_id


def _count_rows(path) -> int:
    with path.open("r", encoding="utf-8", newline="") as file:
        reader = csv.reader(file)
        next(reader, None)
        return sum(1 for _ in reader)


def _parse_year_from_title(title: str) -> int | None:
    match = YEAR_PATTERN.search(title)
    if not match:
        return None
    return int(match.group(1))


if __name__ == "__main__":
    main()

