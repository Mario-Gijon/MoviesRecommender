from __future__ import annotations

import argparse
import json
from dataclasses import asdict

from .constants import DEFAULT_DIVERSIFIED_LIMIT, MMR_CANDIDATE_POOL_SIZE, MMR_LAMBDA
from .diversification import rank_diversified_recommendations
from .index_loader import load_content_index
from .models import UserMovieRating
from .scoring import rank_by_recommendation_score
from .user_profile import build_user_profile


def main() -> None:
    args = _parse_args()
    ratings = [_parse_rating_argument(value) for value in args.rating]

    content_index = load_content_index()
    profile = build_user_profile(content_index=content_index, ratings=ratings)
    diversified_candidates = rank_diversified_recommendations(
        content_index=content_index,
        user_profile=profile,
        limit=args.limit,
        candidate_pool_size=args.candidate_pool_size,
        lambda_value=args.mmr_lambda,
    )

    if args.json:
        payload = {
            "style": profile.style,
            "positiveSignals": profile.positiveSignals,
            "negativeSignals": profile.negativeSignals,
            "candidates": [asdict(candidate) for candidate in diversified_candidates],
        }
        if args.compare:
            scored_candidates = rank_by_recommendation_score(
                content_index=content_index,
                user_profile=profile,
                limit=args.limit,
            )
            payload["scoredCandidates"] = [asdict(candidate) for candidate in scored_candidates]
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return

    print(f"Profile style: {profile.style}")
    print(f"Positive signals: {', '.join(profile.positiveSignals) or '-'}")
    print(f"Negative signals: {', '.join(profile.negativeSignals) or '-'}")

    if args.compare:
        scored_candidates = rank_by_recommendation_score(
            content_index=content_index,
            user_profile=profile,
            limit=args.limit,
        )
        print("Top scored candidates before MMR:")
        for rank, candidate in enumerate(scored_candidates, start=1):
            print(
                f"{rank}. movieId={candidate.movieId} | "
                f"title={candidate.displayTitle} | "
                f"recommendationScore={candidate.recommendationScore:.6f} | "
                f"contentSimilarity={candidate.contentSimilarity:.6f} | "
                f"standDisplayScore={candidate.standDisplayScore:.4f}"
            )
        print("Top diversified candidates after MMR:")
    else:
        print("Diversified recommendations:")

    for rank, candidate in enumerate(diversified_candidates, start=1):
        print(
            f"{rank}. movieId={candidate.movieId} | "
            f"title={candidate.displayTitle} | "
            f"year={candidate.year if candidate.year is not None else '-'} | "
            f"suitability={candidate.suitabilityCategory} | "
            f"recommendationScore={candidate.recommendationScore:.6f} | "
            f"contentSimilarity={candidate.contentSimilarity:.6f} | "
            f"standDisplayScore={candidate.standDisplayScore:.4f} | "
            f"mmrScore={candidate.mmrScore:.6f} | "
            f"maxSimilarityToSelected={candidate.maxSimilarityToSelected:.6f} | "
            f"matchedSignals={', '.join(candidate.matchedSignals) or '-'}"
        )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Inspect diversified content recommendations from repeated movie ratings.",
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
    parser.add_argument("--compare", action="store_true")
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
