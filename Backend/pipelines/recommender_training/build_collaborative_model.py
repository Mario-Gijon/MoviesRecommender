import argparse
from pathlib import Path

from app.recommenders.collaborative.algorithms.biased_matrix_factorization.builder import (
    build_biased_matrix_factorization_model,
)
from app.recommenders.collaborative.algorithms.biased_matrix_factorization.models import (
    BiasedMatrixFactorizationBuildConfig,
)
from app.recommenders.collaborative.algorithms.item_knn_cosine.builder import (
    build_item_knn_cosine_model,
)
from app.recommenders.collaborative.algorithms.item_knn_cosine.models import (
    ItemKnnCosineBuildConfig,
)
from app.recommenders.collaborative.algorithms.popularity_baseline.builder import (
    build_popularity_baseline_model,
)
from app.recommenders.collaborative.algorithms.popularity_baseline.models import (
    PopularityBaselineBuildConfig,
)
from app.recommenders.collaborative.algorithms.user_knn_pearson_shrinkage.builder import (
    build_user_knn_pearson_shrinkage_model,
)
from app.recommenders.collaborative.algorithms.user_knn_pearson_shrinkage.models import (
    UserKnnPearsonShrinkageBuildConfig,
)
from app.recommenders.collaborative.common.offline_context import (
    CollaborativeOfflineContext,
    build_collaborative_offline_context,
)


MODEL_CHOICES = [
    "popularity_baseline",
    "item_knn_cosine",
    "user_knn_pearson_shrinkage",
    "biased_matrix_factorization",
    "all",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", choices=MODEL_CHOICES, required=True)
    parser.add_argument("--ratings-path", type=Path, default=None)
    parser.add_argument("--artifact-root", type=Path, default=None)
    parser.add_argument("--overwrite", action="store_true")

    parser.add_argument("--top-k", type=int, default=200)
    parser.add_argument("--min-support", type=int, default=25)
    parser.add_argument("--item-chunk-size", type=int, default=256)

    parser.add_argument("--user-chunksize", type=int, default=500_000)

    parser.add_argument("--factors", type=int, default=64)
    parser.add_argument("--epochs", type=int, default=20)
    parser.add_argument("--learning-rate", type=float, default=0.005)
    parser.add_argument("--regularization", type=float, default=0.05)
    parser.add_argument("--validation-ratio", type=float, default=0.1)
    parser.add_argument("--random-seed", type=int, default=42)
    parser.add_argument("--bmf-chunksize", type=int, default=500_000)
    parser.add_argument("--init-std", type=float, default=0.05)
    parser.add_argument("--early-stopping-patience", type=int, default=None)
    parser.add_argument("--min-validation-improvement", type=float, default=0.0)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    context = build_context_from_args(args)

    if args.model in ("popularity_baseline", "all"):
        build_popularity_baseline_model(
            PopularityBaselineBuildConfig(overwrite=args.overwrite),
            offline_context=context,
        )

    if args.model in ("item_knn_cosine", "all"):
        build_item_knn_cosine_model(
            ItemKnnCosineBuildConfig(
                top_k=args.top_k,
                min_support=args.min_support,
                chunk_size=args.item_chunk_size,
                overwrite=args.overwrite,
            ),
            offline_context=context,
        )

    if args.model in ("user_knn_pearson_shrinkage", "all"):
        build_user_knn_pearson_shrinkage_model(
            UserKnnPearsonShrinkageBuildConfig(
                overwrite=args.overwrite,
                chunksize=args.user_chunksize,
            ),
            offline_context=context,
        )

    if args.model in ("biased_matrix_factorization", "all"):
        build_biased_matrix_factorization_model(
            BiasedMatrixFactorizationBuildConfig(
                factor_count=args.factors,
                epochs=args.epochs,
                learning_rate=args.learning_rate,
                regularization=args.regularization,
                validation_ratio=args.validation_ratio,
                random_seed=args.random_seed,
                overwrite=args.overwrite,
                chunksize=args.bmf_chunksize,
                init_std=args.init_std,
                early_stopping_patience=args.early_stopping_patience,
                min_validation_improvement=args.min_validation_improvement,
            ),
            offline_context=context,
        )


def build_context_from_args(args: argparse.Namespace) -> CollaborativeOfflineContext:
    if args.ratings_path is not None and args.artifact_root is None:
        raise RuntimeError(
            "--ratings-path requires --artifact-root to avoid writing audit builds "
            "into the production artifact root."
        )

    return build_collaborative_offline_context(
        ratings_csv_path=args.ratings_path,
        collaborative_model_artifact_root=args.artifact_root,
        candidate_universe_name=(
            "audit_train_ratings" if args.ratings_path is not None else None
        ),
    )


if __name__ == "__main__":
    main()
