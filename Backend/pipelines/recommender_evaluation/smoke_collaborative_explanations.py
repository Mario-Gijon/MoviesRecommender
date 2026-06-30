from app.recommenders.collaborative.common.explanations import (
    EvidenceMovie,
    EvidenceProfile,
    render_collaborative_explanation,
)


def main() -> None:
    item_knn = render_collaborative_explanation(
        explanation_type="item_knn_similar_movies",
        algorithm_id="item_knn_cosine",
        variant_id="top_k_50_min_support_25",
        movie_id=10,
        rank=1,
        evidence_movies=[
            EvidenceMovie(movieId=1, title="Toy Story", userRating=5, role="liked_source"),
            EvidenceMovie(movieId=2, title="Shrek", userRating=5, role="liked_source"),
            EvidenceMovie(movieId=3, title="Monstruos S.A.", userRating=4, role="liked_source"),
        ],
        evidence_strength="strong",
        template_session_id="smoke-session",
    )
    _print_case("ItemKNN", item_knn)

    user_knn = render_collaborative_explanation(
        explanation_type="user_knn_similar_profiles",
        algorithm_id="user_knn_pearson_shrinkage",
        variant_id="default",
        movie_id=20,
        rank=2,
        evidence_profiles=[
            EvidenceProfile(
                profileLabel="otros perfiles parecidos al tuyo",
                sharedMovies=[
                    EvidenceMovie(movieId=4, title="Harry Potter y la piedra filosofal"),
                    EvidenceMovie(movieId=5, title="Matilda"),
                ],
            )
        ],
        evidence_strength="strong",
        template_session_id="smoke-session",
    )
    _print_case("UserKNN", user_knn)

    bmf = render_collaborative_explanation(
        explanation_type="bmf_profile_pattern",
        algorithm_id="biased_matrix_factorization",
        variant_id="factors_8_epochs_2_lr_0_005_reg_0_05",
        movie_id=30,
        rank=3,
        evidence_movies=[
            EvidenceMovie(movieId=6, title="Los Increibles", userRating=5),
            EvidenceMovie(movieId=7, title="Kung Fu Panda", userRating=4),
        ],
        evidence_strength="medium",
        template_session_id="smoke-session",
    )
    _print_case("BMF", bmf)

    popularity = render_collaborative_explanation(
        explanation_type="popularity_general",
        algorithm_id="popularity_baseline",
        variant_id="default",
        movie_id=40,
        rank=4,
        evidence_movies=[],
        evidence_strength="fallback",
        template_session_id="smoke-session",
    )
    _print_case("Popularity/Fallback", popularity)


def _print_case(label: str, explanation) -> None:
    print(f"[{label}]")
    print("explanationType:", explanation.explanationType)
    print("templateId:", explanation.templateId)
    print("explanationText:", explanation.explanationText)
    print(
        "evidenceMovies:",
        [movie.title for movie in explanation.evidenceMovies],
    )
    print()


if __name__ == "__main__":
    main()
