from app.catalog.catalog_repository import catalog_repository
from app.recommenders.collaborative.algorithms.item_knn_cosine.explanation import (
    ItemKnnExplanationContribution,
    build_item_knn_explanation,
)


def main() -> None:
    candidates = catalog_repository.get_recommendation_candidates()
    if len(candidates) < 4:
        raise RuntimeError("Need at least 4 public catalog movies for ItemKNN explanation smoke.")

    source_movies = candidates[:3]
    candidate_movie = candidates[3]

    rendered = build_item_knn_explanation(
        candidate_movie_id=int(candidate_movie["movieId"]),
        rank=1,
        variant_id="smoke_variant",
        template_session_id="item-knn-smoke",
        contributions=[
            ItemKnnExplanationContribution(
                source_movie_id=int(source_movies[0]["movieId"]),
                source_rating=5,
                contribution=1.4,
            ),
            ItemKnnExplanationContribution(
                source_movie_id=int(source_movies[1]["movieId"]),
                source_rating=5,
                contribution=1.1,
            ),
            ItemKnnExplanationContribution(
                source_movie_id=int(source_movies[2]["movieId"]),
                source_rating=4,
                contribution=0.7,
            ),
        ],
    )

    print("candidateMovieId:", candidate_movie["movieId"])
    print(
        "candidateTitle:",
        candidate_movie.get("displayTitle") or candidate_movie.get("title"),
    )
    print("headline:", rendered.response_explanation.headline)
    print("evidenceTitles:", rendered.response_explanation.evidence)
    print("templateId:", rendered.structured_explanation.templateId)


if __name__ == "__main__":
    main()
