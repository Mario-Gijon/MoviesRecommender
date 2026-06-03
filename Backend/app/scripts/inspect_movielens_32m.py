import csv
import json
import re
from collections import Counter, defaultdict

from app.infrastructure.datasets.movielens_paths import (
    ML_32M_LINKS_CSV_PATH,
    ML_32M_MOVIES_CSV_PATH,
    ML_32M_RATINGS_CSV_PATH,
    ML_32M_SUMMARY_PATH,
    ML_32M_TAGS_CSV_PATH,
)


YEAR_PATTERN = re.compile(r"\((\d{4})\)\s*$")
YEAR_THRESHOLDS = [1990, 1995, 2000, 2010, 2015, 2020]
RATING_THRESHOLDS = [20, 50, 100, 250]


def main() -> None:
    _ensure_required_files()

    movies = _load_movies()
    ratings_summary, unique_users, ratings_count = _load_ratings_summary()
    tags_count = _count_rows(ML_32M_TAGS_CSV_PATH)
    links_by_movie_id, movies_with_tmdb_id, movies_with_imdb_id = _load_links()

    years = [movie["year"] for movie in movies.values() if movie["year"] is not None]
    movies_without_year = sum(1 for movie in movies.values() if movie["year"] is None)
    decade_distribution = Counter()
    for year in years:
        decade_distribution[f"{(year // 10) * 10}s"] += 1

    top_movies = []
    for movie_id, stats in sorted(
        ratings_summary.items(),
        key=lambda item: (-item[1]["count"], item[0]),
    )[:20]:
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

    recent_diagnostics = {
        f"moviesYearGte{threshold}": sum(
            1 for movie in movies.values() if movie["year"] is not None and movie["year"] >= threshold
        )
        for threshold in YEAR_THRESHOLDS
    }
    rating_sufficiency = _build_rating_sufficiency_diagnostics(movies, ratings_summary)

    summary = {
        "general": {
            "moviesCount": len(movies),
            "ratingsCount": ratings_count,
            "tagsCount": tags_count,
            "linksCount": len(links_by_movie_id),
            "uniqueUsersCount": len(unique_users),
            "moviesWithTmdbId": movies_with_tmdb_id,
            "moviesWithImdbId": movies_with_imdb_id,
        },
        "yearCoverage": {
            "earliestYear": min(years) if years else None,
            "latestYear": max(years) if years else None,
            "moviesWithoutParsedYear": movies_without_year,
        },
        "decadeDistribution": decade_distribution.most_common(),
        "recentMovieDiagnostics": recent_diagnostics,
        "ratingSufficiencyDiagnostics": rating_sufficiency,
        "topMoviesByRatingCount": top_movies,
    }

    ML_32M_SUMMARY_PATH.parent.mkdir(parents=True, exist_ok=True)
    ML_32M_SUMMARY_PATH.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print(f"Movies: {summary['general']['moviesCount']}")
    print(f"Ratings: {summary['general']['ratingsCount']}")
    print(f"Tags: {summary['general']['tagsCount']}")
    print(f"Links: {summary['general']['linksCount']}")
    print(f"Unique users: {summary['general']['uniqueUsersCount']}")
    print(f"Movies with tmdbId: {summary['general']['moviesWithTmdbId']}")
    print(f"Movies with imdbId: {summary['general']['moviesWithImdbId']}")
    print(
        f"Year coverage: earliest={summary['yearCoverage']['earliestYear']}, "
        f"latest={summary['yearCoverage']['latestYear']}, "
        f"without_year={summary['yearCoverage']['moviesWithoutParsedYear']}"
    )
    print("Top 20 movies by rating count:")
    for item in top_movies:
        print(
            f"- movieId={item['movieId']}, title={item['title']}, "
            f"rating_count={item['ratingCount']}, average_rating={item['averageRating']}, "
            f"tmdbId={item['tmdbId']}, imdbId={item['imdbId']}"
        )
    print(f"Summary written to: {ML_32M_SUMMARY_PATH}")


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
            year = _parse_year_from_title(title)
            movies[movie_id] = {"title": title, "year": year}
    return movies


def _load_ratings_summary() -> tuple[dict[int, dict[str, float]], set[int], int]:
    ratings_summary: dict[int, dict[str, float]] = defaultdict(lambda: {"count": 0, "sum": 0.0})
    unique_users: set[int] = set()
    ratings_count = 0
    with ML_32M_RATINGS_CSV_PATH.open("r", encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)
        for row in reader:
            movie_id = int(row["movieId"])
            user_id = int(row["userId"])
            rating = float(row["rating"])
            ratings_summary[movie_id]["count"] += 1
            ratings_summary[movie_id]["sum"] += rating
            unique_users.add(user_id)
            ratings_count += 1
    return ratings_summary, unique_users, ratings_count


def _load_links() -> tuple[dict[int, dict[str, int | str | None]], int, int]:
    links_by_movie_id: dict[int, dict[str, int | str | None]] = {}
    movies_with_tmdb_id = 0
    movies_with_imdb_id = 0
    with ML_32M_LINKS_CSV_PATH.open("r", encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)
        for row in reader:
            movie_id = int(row["movieId"])
            imdb_id = row["imdbId"] or None
            tmdb_id = int(row["tmdbId"]) if row["tmdbId"] else None
            links_by_movie_id[movie_id] = {"imdbId": imdb_id, "tmdbId": tmdb_id}
            if imdb_id is not None:
                movies_with_imdb_id += 1
            if tmdb_id is not None:
                movies_with_tmdb_id += 1
    return links_by_movie_id, movies_with_tmdb_id, movies_with_imdb_id


def _build_rating_sufficiency_diagnostics(
    movies: dict[int, dict],
    ratings_summary: dict[int, dict[str, float]],
) -> dict[str, dict[str, int]]:
    diagnostics: dict[str, dict[str, int]] = {}
    for year_threshold in YEAR_THRESHOLDS:
        eligible_movie_ids = {
            movie_id
            for movie_id, movie in movies.items()
            if movie["year"] is not None and movie["year"] >= year_threshold
        }
        diagnostics[f"yearGte{year_threshold}"] = {
            f"moviesWithAtLeast{rating_threshold}Ratings": sum(
                1
                for movie_id in eligible_movie_ids
                if (ratings_summary.get(movie_id, {}).get("count") or 0) >= rating_threshold
            )
            for rating_threshold in RATING_THRESHOLDS
        }
    return diagnostics


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
