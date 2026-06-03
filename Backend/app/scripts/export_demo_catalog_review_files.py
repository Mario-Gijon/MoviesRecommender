import csv
import json

from app.infrastructure.datasets.movielens_paths import (
    ML_LATEST_SMALL_DEMO_CATALOG_COLLABORATIVE_CORE_CSV_PATH,
    ML_LATEST_SMALL_DEMO_CATALOG_EXCLUDED_CSV_PATH,
    ML_LATEST_SMALL_DEMO_CATALOG_PATH,
    ML_LATEST_SMALL_DEMO_CATALOG_RECOMMENDATION_POOL_CSV_PATH,
    ML_LATEST_SMALL_DEMO_CATALOG_VISIBLE_CSV_PATH,
)


CSV_COLUMNS = [
    "movieId",
    "tmdbId",
    "imdbId",
    "title",
    "cleanTitle",
    "year",
    "demoSuitability",
    "catalogRoles",
    "genres",
    "keywords",
    "userTags",
    "directors",
    "topCast",
    "certificationES",
    "certificationUS",
    "certificationGB",
    "runtime",
    "originalLanguage",
    "ratingCount",
    "averageRating",
    "candidateScore",
    "tmdbPopularity",
    "tmdbVoteAverage",
    "tmdbVoteCount",
    "hasPoster",
    "posterPath",
    "backdropPath",
    "overview",
]


def main() -> None:
    if not ML_LATEST_SMALL_DEMO_CATALOG_PATH.exists():
        raise RuntimeError(
            "Demo catalog JSON is missing. "
            "Run `python -m app.scripts.build_demo_catalog_from_movielens_small` first."
        )

    catalog = json.loads(ML_LATEST_SMALL_DEMO_CATALOG_PATH.read_text(encoding="utf-8"))

    exports = [
        ("visibleMovies", ML_LATEST_SMALL_DEMO_CATALOG_VISIBLE_CSV_PATH),
        ("recommendationPool", ML_LATEST_SMALL_DEMO_CATALOG_RECOMMENDATION_POOL_CSV_PATH),
        ("collaborativeCore", ML_LATEST_SMALL_DEMO_CATALOG_COLLABORATIVE_CORE_CSV_PATH),
        ("excludedOrSensitive", ML_LATEST_SMALL_DEMO_CATALOG_EXCLUDED_CSV_PATH),
    ]

    print(f"Input JSON path: {ML_LATEST_SMALL_DEMO_CATALOG_PATH}")
    for key, path in exports:
        rows = [_flatten_item(item) for item in catalog.get(key, [])]
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=CSV_COLUMNS)
            writer.writeheader()
            writer.writerows(rows)
        print(f"Output CSV path: {path}")
        print(f"Rows written: {len(rows)}")


def _flatten_item(item: dict) -> dict:
    certifications = item.get("certifications", {})
    return {
        "movieId": item.get("movieId"),
        "tmdbId": item.get("tmdbId"),
        "imdbId": item.get("imdbId"),
        "title": item.get("title"),
        "cleanTitle": item.get("cleanTitle"),
        "year": item.get("year"),
        "demoSuitability": item.get("demoSuitability"),
        "catalogRoles": _join_values(item.get("catalogRoles", [])),
        "genres": _join_values(item.get("genres", [])),
        "keywords": _join_values(item.get("keywords", [])),
        "userTags": _join_values(item.get("userTags", [])),
        "directors": _join_values([director.get("name", "") for director in item.get("directors", [])]),
        "topCast": _join_values([member.get("name", "") for member in item.get("topCast", [])[:5]]),
        "certificationES": certifications.get("ES", ""),
        "certificationUS": certifications.get("US", ""),
        "certificationGB": certifications.get("GB", ""),
        "runtime": item.get("runtime"),
        "originalLanguage": item.get("originalLanguage"),
        "ratingCount": item.get("ratingCount"),
        "averageRating": item.get("averageRating"),
        "candidateScore": item.get("candidateScore"),
        "tmdbPopularity": item.get("tmdbPopularity"),
        "tmdbVoteAverage": item.get("tmdbVoteAverage"),
        "tmdbVoteCount": item.get("tmdbVoteCount"),
        "hasPoster": "true" if item.get("posterPath") else "false",
        "posterPath": item.get("posterPath", ""),
        "backdropPath": item.get("backdropPath", ""),
        "overview": item.get("overview", ""),
    }


def _join_values(values: list[str]) -> str:
    filtered_values = [value for value in values if value]
    return " | ".join(filtered_values)


if __name__ == "__main__":
    main()
