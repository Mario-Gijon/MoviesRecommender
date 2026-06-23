import argparse
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request

from app.core.config import settings
from app.project_paths.dataset_paths import (
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
            "Run `python -m pipelines.dataset_generation.build_movielens_32m_candidates` first."
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
    fully_enriched_count = 0
    display_backfilled_count = 0
    already_complete_count = 0
    base_fields_refreshed_count = 0
    failed_count = 0
    updated_by_movie_id = dict(existing_by_movie_id)

    for candidate in selected_candidates:
        movie_id = candidate["movieId"]
        existing_candidate = updated_by_movie_id.get(movie_id)
        refreshed_candidate = None
        if existing_candidate is not None:
            refreshed_candidate = _refresh_candidate_base_fields(
                existing_item=existing_candidate,
                candidate=candidate,
            )
            base_fields_refreshed_count += 1

        if args.resume and existing_candidate is not None:
            existing_tmdb = refreshed_candidate.get("tmdb", {}) if refreshed_candidate is not None else {}
            if _has_complete_display_metadata(existing_tmdb):
                updated_by_movie_id[movie_id] = refreshed_candidate
                already_complete_count += 1
                continue

        tmdb_id = candidate.get("tmdbId")
        enriched_candidate = dict(refreshed_candidate or candidate)

        if tmdb_id is None:
            if "tmdb" not in enriched_candidate:
                enriched_candidate["tmdb"] = _empty_tmdb_payload()
            if "enrichmentError" not in enriched_candidate:
                enriched_candidate["enrichmentError"] = "Missing tmdbId"
            failed_count += 1
        else:
            attempted += 1
            try:
                if refreshed_candidate is not None and _has_canonical_tmdb_metadata(
                    refreshed_candidate.get("tmdb", {})
                ):
                    display_payload = _fetch_tmdb_movie(
                        tmdb_id=tmdb_id,
                        token=token,
                        language=args.display_language,
                        include_extended_payload=False,
                    )
                    enriched_candidate["tmdb"] = _backfill_display_metadata(
                        existing_tmdb=refreshed_candidate.get("tmdb", {}),
                        display_payload=display_payload,
                    )
                    display_backfilled_count += 1
                else:
                    canonical_payload = _fetch_tmdb_movie(
                        tmdb_id=tmdb_id,
                        token=token,
                        language="en-US",
                        include_extended_payload=True,
                    )
                    display_payload = _fetch_tmdb_movie(
                        tmdb_id=tmdb_id,
                        token=token,
                        language=args.display_language,
                        include_extended_payload=False,
                    )
                    enriched_candidate["tmdb"] = _build_tmdb_payload(
                        canonical_payload=canonical_payload,
                        display_payload=display_payload,
                    )
                    fully_enriched_count += 1
                enriched_candidate.pop("enrichmentError", None)
            except (urllib.error.HTTPError, urllib.error.URLError, json.JSONDecodeError) as exc:
                if existing_candidate is None:
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
    print(f"Already complete: {already_complete_count}")
    print(f"Base fields refreshed: {base_fields_refreshed_count}")
    print(f"Display-backfilled: {display_backfilled_count}")
    print(f"Fully enriched: {fully_enriched_count}")
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
    parser.add_argument("--display-language", default="es-ES")
    return parser.parse_args()


def _fetch_tmdb_movie(
    *,
    tmdb_id: int,
    token: str,
    language: str,
    include_extended_payload: bool,
) -> dict:
    query_params = {"language": language}
    if include_extended_payload:
        query_params["append_to_response"] = "keywords,credits,release_dates"
    query = urllib.parse.urlencode(query_params)
    request = urllib.request.Request(
        f"{TMDB_BASE_URL}/{tmdb_id}?{query}",
        headers={
            "Authorization": f"Bearer {token}",
            "accept": "application/json",
        },
    )
    with urllib.request.urlopen(request) as response:
        return json.loads(response.read().decode("utf-8"))


def _build_tmdb_payload(*, canonical_payload: dict, display_payload: dict) -> dict:
    keywords_payload = canonical_payload.get("keywords", {})
    credits_payload = canonical_payload.get("credits", {})
    release_dates_payload = canonical_payload.get("release_dates", {})
    canonical_genres = [
        genre.get("name")
        for genre in canonical_payload.get("genres", [])
        if genre.get("name")
    ]
    display_genres = [
        genre.get("name")
        for genre in display_payload.get("genres", [])
        if genre.get("name")
    ]
    canonical_title = canonical_payload.get("title")
    canonical_overview = canonical_payload.get("overview")

    return {
        "id": canonical_payload.get("id"),
        "title": canonical_title,
        "originalTitle": canonical_payload.get("original_title"),
        "overview": canonical_overview,
        "releaseDate": canonical_payload.get("release_date"),
        "runtime": canonical_payload.get("runtime"),
        "originalLanguage": canonical_payload.get("original_language"),
        "popularity": canonical_payload.get("popularity"),
        "voteAverage": canonical_payload.get("vote_average"),
        "voteCount": canonical_payload.get("vote_count"),
        "posterPath": canonical_payload.get("poster_path"),
        "backdropPath": canonical_payload.get("backdrop_path"),
        "genres": canonical_genres,
        "displayTitle": _coalesce_text(display_payload.get("title"), canonical_title),
        "displayOverview": _coalesce_text(display_payload.get("overview"), canonical_overview),
        "displayGenres": display_genres or canonical_genres,
        "keywords": _extract_keywords(keywords_payload),
        "topCast": _extract_top_cast(credits_payload),
        "directors": _extract_directors(credits_payload),
        "certifications": _extract_certifications(release_dates_payload),
    }


def _backfill_display_metadata(*, existing_tmdb: dict, display_payload: dict) -> dict:
    canonical_title = existing_tmdb.get("title")
    canonical_overview = existing_tmdb.get("overview")
    canonical_genres = list(existing_tmdb.get("genres", []))
    display_genres = [
        genre.get("name")
        for genre in display_payload.get("genres", [])
        if genre.get("name")
    ]

    updated_tmdb = dict(existing_tmdb)
    updated_tmdb["displayTitle"] = _coalesce_text(display_payload.get("title"), canonical_title)
    updated_tmdb["displayOverview"] = _coalesce_text(
        display_payload.get("overview"),
        canonical_overview,
    )
    updated_tmdb["displayGenres"] = display_genres or canonical_genres
    return updated_tmdb


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
        "displayTitle": None,
        "displayOverview": None,
        "releaseDate": None,
        "runtime": None,
        "originalLanguage": None,
        "popularity": None,
        "voteAverage": None,
        "voteCount": None,
        "posterPath": None,
        "backdropPath": None,
        "genres": [],
        "displayGenres": [],
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


def _coalesce_text(primary: str | None, fallback: str | None) -> str | None:
    normalized_primary = (primary or "").strip()
    if normalized_primary:
        return normalized_primary
    normalized_fallback = (fallback or "").strip()
    return normalized_fallback or None


def _refresh_candidate_base_fields(*, existing_item: dict, candidate: dict) -> dict:
    refreshed_item = dict(existing_item)
    for field in (
        "movieId",
        "title",
        "cleanTitle",
        "year",
        "genres",
        "ratingCount",
        "averageRating",
        "tmdbId",
        "imdbId",
        "userTags",
        "candidateScore",
        "dataReliabilityScore",
        "recencyScore",
    ):
        if field in candidate:
            refreshed_item[field] = candidate[field]

    if candidate.get("tmdbId") is not None and _has_complete_display_metadata(
        refreshed_item.get("tmdb", {})
    ):
        refreshed_item.pop("enrichmentError", None)

    return refreshed_item


def _has_complete_display_metadata(tmdb_payload: dict) -> bool:
    return all(
        key in tmdb_payload
        for key in ("displayTitle", "displayOverview", "displayGenres")
    )


def _has_canonical_tmdb_metadata(tmdb_payload: dict) -> bool:
    return any(
        tmdb_payload.get(key)
        for key in (
            "title",
            "overview",
            "genres",
            "keywords",
            "topCast",
            "directors",
            "certifications",
        )
    )


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
