import argparse

from app.recommenders.collaborative.algorithms.biased_matrix_factorization.models import (
    BiasedMatrixFactorizationBuildConfig,
)
from app.recommenders.collaborative.algorithms.biased_matrix_factorization.storage import (
    prepare_biased_matrix_factorization_artifacts,
    write_model_manifest,
)


def build_biased_matrix_factorization_model(
    config: BiasedMatrixFactorizationBuildConfig,
) -> None:
    artifacts = prepare_biased_matrix_factorization_artifacts(config)

    write_model_manifest(
        artifacts=artifacts,
        config=config,
        status="scaffold_only",
        counts={},
        training_metrics={},
    )

    print("Biased Matrix Factorization scaffold prepared.")
    print(f"Variant: {config.variant_id}")
    print(f"Output directory: {artifacts.variant_dir}")
    print(f"Manifest: {artifacts.manifest_path}")
    print("No training artifacts were created.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--factor-count", type=int, default=64)
    parser.add_argument("--epochs", type=int, default=20)
    parser.add_argument("--learning-rate", type=float, default=0.005)
    parser.add_argument("--regularization", type=float, default=0.05)
    parser.add_argument("--validation-ratio", type=float, default=0.1)
    parser.add_argument("--random-seed", type=int, default=42)
    parser.add_argument("--chunksize", type=int, default=500_000)
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    build_biased_matrix_factorization_model(
        BiasedMatrixFactorizationBuildConfig(
            factor_count=args.factor_count,
            epochs=args.epochs,
            learning_rate=args.learning_rate,
            regularization=args.regularization,
            validation_ratio=args.validation_ratio,
            random_seed=args.random_seed,
            overwrite=args.overwrite,
            chunksize=args.chunksize,
        )
    )


if __name__ == "__main__":
    main()
