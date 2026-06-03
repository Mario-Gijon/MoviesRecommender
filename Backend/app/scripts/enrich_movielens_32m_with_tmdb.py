import argparse
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request

from app.core.config import settings
from app.infrastructure.datasets.movielens_paths import (
    ML_32M_CANDIDATES_PATH,
    ML_32M_TMDB_ENRICHED_PATH,
)


TMDB_BASE_URL = "https://api.themoviedb.org/3/movie"


def main() -> None:
    args = _parse_args()
    token = settings.tmdb_bearer_token or os.environ.get("MOVIES_RECOMMENDER_TMDB_BEARER_TOKEN")
    if not token:
        raise RuntimeError(
            "TMDB bearer token is missing. "
            "Set MOVIES_RECOMMENDER_TMDB_BEARER_TOKEN in Backend/.env or the shell environment."
        )

    if not ML_32M_CANDIDATES_PATH.exists():
        raise RuntimeError(
            "MovieLens 32M candidate file is missing. "
            "Run `python -m app.scripts.build_movielens_32m_candidates` first."
        )

    if ML_32M_TMDB_ENRICHED_PATH.exists() and not args.force and not args.resume:
        raise RuntimeError(
            "Enriched output already exists. Pass `--force` to rebuild or `--resume` to continue."
        )

    candidates = json.loads(ML_32M_CANDIDATES_PATH.read_text(encoding="utf-8"))
    selected_candidates = candidates[: args.limit] if args.limit is not None else candidates

    existing_by_movie_id: dict[int, dict] = {}
    already_enriched_count = 0
    if args.resume and ML_32M_TMDB_ENRICHED_PATH.exists():
        existing_items = json.loads(ML_32M_TMDB_ENRICHED_PATH.read_text(encoding="utf-8"))
        existing_by_movie_id = {item["movieId"]: item for item in existing_items}
        already_enriched_count = len(existing_by_movie_id)

    print(f"Candidates read: {len(candidates)}")
    print(f"Already enriched count: {already_enriched_count}")

    attempted = 0
    success_count = 0
    failed_count = 0
    updated_by_movie_id = dict(existing_by_movie_id)

    for candidate in selected_candidates:
        movie_id = candidate["movieId"]
        if args.resume and movie_id in updated_by_movie_id:
            continue

        tmdb_id = candidate.get("tmdbId")
        enriched_candidate = dict(candidate)

        if tmdb_id is None:
            enriched_candidate["tmdb"] = _empty_tmdb_payload()
            enriched_candidate["enrichmentError"] = "Missing tmdbId"
            failed_count += 1
        else:
            attempted += 1
            try:
                tmdb_payload = _fetch_tmdb_movie(tmdb_id=tmdb_id, token=token)
                enriched_candidate["tmdb"] = _build_tmdb_payload(tmdb_payload)
                success_count += 1
            except (urllib.error.HTTPError, urllib.error.URLError, json.JSONDecodeError) as exc:
                enriched_candidate["tmdb"] = _empty_tmdb_payload()
                enriched_candidate["enrichmentError"] = _format_request_error(exc)
                failed_count += 1

            if attempted % 50 == 0:
                print(f"Attempted {attempted}/{len(selected_candidates)}...")

            if args.sleep > 0:
                time.sleep(args.sleep)

        updated_by_movie_id[movie_id] = enriched_candidate

        if (attempted + failed_count) % 25 == 0:
            _write_output(candidates=candidates, enriched_by_movie_id=updated_by_movie_id)

    _write_output(candidates=candidates, enriched_by_movie_id=updated_by_movie_id)

    print(f"Candidates attempted this run: {attempted}")
    print(f"Successfully enriched: {success_count}")
    print(f"Failed enrichments: {failed_count}")
    print(f"Output path: {ML_32M_TMDB_ENRICHED_PATH}")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Enrich processed MovieLens 32M candidates with TMDB metadata.",
    )
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--sleep", type=float, default=0.25)
    return parser.parse_args()


def _fetch_tmdb_movie(*, tmdb_id: int, token: str) -> dict:
    query = urllib.parse.urlencode(
        {
            "language": "en-US",
            "append_to_response": "keywords,credits,release_dates",
        }
    )
    request = urllib.request.Request(
        f"{TMDB_BASE_URL}/{tmdb_id}?{query}",
        headers={
            "Authorization": f"Bearer {token}",
            "accept": "application/json",
        },
    )
    with urllib.request.urlopen(request) as response:
        return json.loads(response.read().decode("utf-8"))


def _build_tmdb_payload(payload: dict) -> dict:
    keywords_payload = payload.get("keywords", {})
    credits_payload = payload.get("credits", {})
    release_dates_payload = payload.get("release_dates", {})

    return {
        "id": payload.get("id"),
        "title": payload.get("title"),
        "originalTitle": payload.get("original_title"),
        "overview": payload.get("overview"),
        "releaseDate": payload.get("release_date"),
        "runtime": payload.get("runtime"),
        "originalLanguage": payload.get("original_language"),
        "popularity": payload.get("popularity"),
        "voteAverage": payload.get("vote_average"),
        "voteCount": payload.get("vote_count"),
        "posterPath": payload.get("poster_path"),
        "backdropPath": payload.get("backdrop_path"),
        "genres": [genre.get("name") for genre in payload.get("genres", []) if genre.get("name")],
        "keywords": _extract_keywords(keywords_payload),
        "topCast": _extract_top_cast(credits_payload),
        "directors": _extract_directors(credits_payload),
        "certifications": _extract_certifications(release_dates_payload),
    }


def _extract_keywords(keywords_payload: dict) -> list[str]:
    raw_keywords = keywords_payload.get("keywords") or keywords_payload.get("results") or []
    return [item.get("name") for item in raw_keywords if item.get("name")]


def _extract_top_cast(credits_payload: dict) -> list[dict]:
    cast_members = credits_payload.get("cast", [])[:8]
    return [
        {
            "id": member.get("id"),
            "name": member.get("name"),
            "character": member.get("character"),
            "order": member.get("order"),
        }
        for member in cast_members
    ]


def _extract_directors(credits_payload: dict) -> list[dict]:
    return [
        {
            "id": member.get("id"),
            "name": member.get("name"),
        }
        for member in credits_payload.get("crew", [])
        if member.get("job") == "Director"
    ]


def _extract_certifications(release_dates_payload: dict) -> dict[str, str]:
    certifications: dict[str, str] = {}
    for entry in release_dates_payload.get("results", []):
        country_code = entry.get("iso_3166_1")
        if not country_code or country_code in certifications:
            continue
        for release in entry.get("release_dates", []):
            certification = (release.get("certification") or "").strip()
            if certification:
                certifications[country_code] = certification
                break
    return certifications


def _empty_tmdb_payload() -> dict:
    return {
        "id": None,
        "title": None,
        "originalTitle": None,
        "overview": None,
        "releaseDate": None,
        "runtime": None,
        "originalLanguage": None,
        "popularity": None,
        "voteAverage": None,
        "voteCount": None,
        "posterPath": None,
        "backdropPath": None,
        "genres": [],
        "keywords": [],
        "topCast": [],
        "directors": [],
        "certifications": {},
    }


def _format_request_error(exc: Exception) -> str:
    if isinstance(exc, urllib.error.HTTPError):
        return f"TMDB HTTP error {exc.code}"
    if isinstance(exc, urllib.error.URLError):
        return f"TMDB request failed: {exc.reason}"
    return "TMDB response could not be parsed"


def _write_output(*, candidates: list[dict], enriched_by_movie_id: dict[int, dict]) -> None:
    ordered_items = [
        enriched_by_movie_id[candidate["movieId"]]
        for candidate in candidates
        if candidate["movieId"] in enriched_by_movie_id
    ]
    ML_32M_TMDB_ENRICHED_PATH.parent.mkdir(parents=True, exist_ok=True)
    ML_32M_TMDB_ENRICHED_PATH.write_text(
        json.dumps(ordered_items, indent=2),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
