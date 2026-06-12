from __future__ import annotations

import argparse
import json
from dataclasses import asdict

from .constants import (
    DEFAULT_DIVERSIFIED_LIMIT,
    DEFAULT_TEMPLATE_SESSION_ID,
    MMR_CANDIDATE_POOL_SIZE,
    MMR_LAMBDA,
)
from .diversification import rank_diversified_recommendations
from .explanations import explain_diversified_recommendations
from .index_loader import load_content_index
from .schemas import UserMovieRating
from .user_profile import build_user_profile, build_user_profile_summary


def main() -> None:
    args = _parse_args()
    ratings = [_parse_rating_argument(value) for value in args.rating]

    content_index = load_content_index()
    profile = build_user_profile(content_index=content_index, ratings=ratings)
    profile_summary = build_user_profile_summary(
        content_index=content_index,
        ratings=ratings,
        profile=profile,
    )
    diversified_candidates = rank_diversified_recommendations(
        content_index=content_index,
        user_profile=profile,
        limit=args.limit,
        candidate_pool_size=args.candidate_pool_size,
        lambda_value=args.mmr_lambda,
    )
    explained_recommendations = explain_diversified_recommendations(
        content_index=content_index,
        user_profile=profile,
        diversified_candidates=diversified_candidates,
        limit=args.limit,
        template_session_id=args.template_session,
    )

    if args.json:
        print(
            json.dumps(
                {
                    "profileStyle": profile.style,
                    "profileHeadline": profile_summary.headline,
                    "templateSessionId": args.template_session,
                    "positiveSignals": profile.positiveSignals,
                    "negativeSignals": profile.negativeSignals,
                    "recommendations": [asdict(item) for item in explained_recommendations],
                },
                indent=2,
                ensure_ascii=False,
            )
        )
        return

    print(f"Profile style: {profile.style}")
    print(f"Profile headline: {profile_summary.headline}")
    print(f"Template session: {args.template_session}")
    print(f"Positive signals: {', '.join(profile.positiveSignals) or '-'}")
    print(f"Negative signals: {', '.join(profile.negativeSignals) or '-'}")
    print("Explained recommendations:")

    for rank, recommendation in enumerate(explained_recommendations, start=1):
        explanation = recommendation.explanation
        print(
            f"{rank}. title={recommendation.displayTitle} | "
            f"year={recommendation.year if recommendation.year is not None else '-'} | "
            f"suitability={recommendation.suitabilityCategory}"
        )
        print(f"   Headline: {explanation.headline}")
        print(f"   Reasons: {' | '.join(explanation.reasons) or '-'}")
        print(f"   Matched signals: {', '.join(explanation.matchedSignals) or '-'}")
        print(f"   Avoided signals: {', '.join(explanation.avoidedSignals) or '-'}")
        print(f"   Similar rated movies: {', '.join(explanation.similarRatedMovies) or '-'}")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Inspect evidence-based explanations for diversified content recommendations.",
    )
    parser.add_argument(
        "--rating",
        action="append",
        required=True,
        help="Repeated rating in movieId:rating format, for example --rating 115617:5",
    )
    parser.add_argument("--limit", type=int, default=DEFAULT_DIVERSIFIED_LIMIT)
    parser.add_argument("--candidate-pool-size", type=int, default=MMR_CANDIDATE_POOL_SIZE)
    parser.add_argument("--mmr-lambda", type=float, default=MMR_LAMBDA)
    parser.add_argument("--template-session", default=DEFAULT_TEMPLATE_SESSION_ID)
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
