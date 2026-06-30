from app.catalog.catalog_repository import catalog_repository
from app.recommenders.collaborative.algorithms.item_knn_cosine.explanation import (
    ItemKnnExplanationContribution,
    build_item_knn_explanation,
)


def main() -> None:
    candidates = catalog_repository.get_recommendation_candidates()
    if len(candidates) < 8:
        raise RuntimeError("Need at least 8 public catalog movies for ItemKNN explanation smoke.")

    source_movies = candidates[:6]
    candidate_movies = candidates[6:8]
    contributions = [
        ItemKnnExplanationContribution(
            source_movie_id=int(source_movies[0]["movieId"]),
            source_rating=5,
            contribution=1.8,
        ),
        ItemKnnExplanationContribution(
            source_movie_id=int(source_movies[1]["movieId"]),
            source_rating=5,
            contribution=1.4,
        ),
        ItemKnnExplanationContribution(
            source_movie_id=int(source_movies[2]["movieId"]),
            source_rating=5,
            contribution=1.2,
        ),
        ItemKnnExplanationContribution(
            source_movie_id=int(source_movies[3]["movieId"]),
            source_rating=4,
            contribution=0.95,
        ),
        ItemKnnExplanationContribution(
            source_movie_id=int(source_movies[4]["movieId"]),
            source_rating=4,
            contribution=0.8,
        ),
        ItemKnnExplanationContribution(
            source_movie_id=int(source_movies[5]["movieId"]),
            source_rating=5,
            contribution=0.6,
        ),
    ]

    for rank, candidate_movie in enumerate(candidate_movies, start=1):
        rendered = build_item_knn_explanation(
            candidate_movie_id=int(candidate_movie["movieId"]),
            rank=rank,
            variant_id="smoke_variant",
            template_session_id="item-knn-smoke",
            contributions=contributions,
        )
        print("candidateMovieId:", candidate_movie["movieId"])
        print(
            "candidateTitle:",
            candidate_movie.get("displayTitle") or candidate_movie.get("title"),
        )
        print("headline:", rendered.response_explanation.headline)
        print("evidenceTitles:", rendered.response_explanation.evidence)
        print("templateId:", rendered.structured_explanation.templateId)
        print(
            "visibleEvidenceMovieIds:",
            rendered.structured_explanation.debug.get("visibleEvidenceMovieIds"),
        )
        print(
            "fullEvidenceCandidateMovieIds:",
            rendered.structured_explanation.debug.get("fullEvidenceCandidateMovieIds"),
        )
        print()


if __name__ == "__main__":
    main()
