from app.catalog.catalog_repository import catalog_repository
from app.recommenders.collaborative.algorithms.user_knn_pearson_shrinkage.explanation import (
    UserKnnExplanationContribution,
    build_user_knn_explanation,
)


def main() -> None:
    candidates = catalog_repository.get_recommendation_candidates()
    if len(candidates) < 8:
        raise RuntimeError(
            "Need at least 8 public catalog movies for UserKNN explanation smoke."
        )

    shared_movies = candidates[:6]
    candidate_movies = candidates[6:8]

    shared_positive_movie_ids_by_neighbor_user_id = {
        101: [int(shared_movies[0]["movieId"]), int(shared_movies[1]["movieId"])],
        205: [int(shared_movies[2]["movieId"]), int(shared_movies[3]["movieId"])],
        309: [int(shared_movies[4]["movieId"]), int(shared_movies[5]["movieId"])],
    }
    contributions = [
        UserKnnExplanationContribution(
            neighbor_user_id=101,
            neighbor_rank=1,
            contribution=1.35,
        ),
        UserKnnExplanationContribution(
            neighbor_user_id=205,
            neighbor_rank=2,
            contribution=1.1,
        ),
        UserKnnExplanationContribution(
            neighbor_user_id=309,
            neighbor_rank=3,
            contribution=0.85,
        ),
    ]

    for rank, candidate_movie in enumerate(candidate_movies, start=1):
        rendered = build_user_knn_explanation(
            candidate_movie_id=int(candidate_movie["movieId"]),
            rank=rank,
            variant_id="default",
            template_seed="user-knn-smoke",
            contributions=contributions,
            shared_positive_movie_ids_by_neighbor_user_id=(
                shared_positive_movie_ids_by_neighbor_user_id
            ),
        )
        print("candidateMovieId:", candidate_movie["movieId"])
        print(
            "candidateTitle:",
            candidate_movie.get("displayTitle") or candidate_movie.get("title"),
        )
        print("headline:", rendered.response_explanation.headline)
        print("sharedEvidenceTitles:", rendered.response_explanation.evidence)
        print("templateId:", rendered.structured_explanation.templateId)
        print("evidenceStrength:", rendered.structured_explanation.evidenceStrength)
        print()


if __name__ == "__main__":
    main()
