from __future__ import annotations

import argparse
import json
from dataclasses import asdict

from .index_loader import load_content_index
from .models import UserMovieRating
from .similarity import rank_by_content_similarity
from .user_profile import build_user_profile


def main() -> None:
    args = _parse_args()
    ratings = [_parse_rating_argument(value) for value in args.rating]

    content_index = load_content_index()
    profile = build_user_profile(content_index=content_index, ratings=ratings)
    candidates = rank_by_content_similarity(
        content_index=content_index,
        user_profile=profile,
        limit=args.limit,
    )

    if args.json:
        print(
            json.dumps(
                {
                    "style": profile.style,
                    "positiveSignals": profile.positiveSignals,
                    "negativeSignals": profile.negativeSignals,
                    "candidates": [asdict(candidate) for candidate in candidates],
                },
                indent=2,
                ensure_ascii=False,
            )
        )
        return

    print(f"Profile style: {profile.style}")
    print(f"Positive signals: {', '.join(profile.positiveSignals) or '-'}")
    print(f"Negative signals: {', '.join(profile.negativeSignals) or '-'}")
    print("Top candidates:")
    for rank, candidate in enumerate(candidates, start=1):
        print(
            f"{rank}. movieId={candidate.movieId} | "
            f"title={candidate.displayTitle} | "
            f"year={candidate.year if candidate.year is not None else '-'} | "
            f"suitability={candidate.suitabilityCategory} | "
            f"contentSimilarity={candidate.contentSimilarity:.6f} | "
            f"standDisplayScore={candidate.standDisplayScore:.4f} | "
            f"matchedSignals={', '.join(candidate.matchedSignals) or '-'}"
        )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Inspect pure content-similarity ranking from repeated movie ratings.",
    )
    parser.add_argument(
        "--rating",
        action="append",
        required=True,
        help="Repeated rating in movieId:rating format, for example --rating 115617:5",
    )
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--json", action="store_true")
    return parser.parse_args()


def _parse_rating_argument(value: str) -> UserMovieRating:
    movie_id_text, separator, rating_text = value.partition(":")
    if separator != ":" or not movie_id_text.strip() or not rating_text.strip():
        raise RuntimeError(
            f"Invalid --rating value: {value}. Expected movieId:rating, for example 115617:5."
        )
    return UserMovieRating(movieId=int(movie_id_text), rating=int(rating_text))


if __name__ == "__main__":
    main()
