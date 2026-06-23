from __future__ import annotations

import argparse
import json
from dataclasses import asdict

from .index_loader import load_content_index
from .models import UserMovieRating
from .user_profile import build_user_profile, build_user_profile_summary


def main() -> None:
    args = _parse_args()
    ratings = [_parse_rating_argument(value) for value in args.rating]

    content_index = load_content_index()
    profile = build_user_profile(content_index=content_index, ratings=ratings)
    summary = build_user_profile_summary(
        content_index=content_index,
        ratings=ratings,
        profile=profile,
    )

    if args.json:
        print(json.dumps(asdict(summary), indent=2, ensure_ascii=False))
        return

    print(f"Style: {summary.style}")
    print(f"Headline: {summary.headline}")
    print(
        "Rated counts: "
        f"total={summary.ratedMovieCount}, "
        f"positive={summary.positiveRatingCount}, "
        f"negative={summary.negativeRatingCount}, "
        f"neutral={summary.neutralRatingCount}"
    )
    print(f"Positive rated movies: {', '.join(summary.positiveRatedMovies) or '-'}")
    print(f"Negative rated movies: {', '.join(summary.negativeRatedMovies) or '-'}")
    print(f"Neutral rated movies: {', '.join(summary.neutralRatedMovies) or '-'}")
    print(f"Positive signals: {', '.join(summary.positiveSignals) or '-'}")
    print(f"Negative signals: {', '.join(summary.negativeSignals) or '-'}")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Inspect a temporary content-based user profile from repeated movie ratings.",
    )
    parser.add_argument(
        "--rating",
        action="append",
        required=True,
        help="Repeated rating in movieId:rating format, for example --rating 115617:5",
    )
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
