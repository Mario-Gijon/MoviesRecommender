import argparse
import csv
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.project_paths.dataset_paths import RECOMMENDER_AUDIT_DIR
from app.recommenders.collaborative.algorithms.biased_matrix_factorization.builder import (
    build_biased_matrix_factorization_model,
)
from app.recommenders.collaborative.algorithms.biased_matrix_factorization.models import (
    ALGORITHM_ID,
    BiasedMatrixFactorizationBuildConfig,
)
from app.recommenders.collaborative.algorithms.biased_matrix_factorization.storage import (
    get_biased_matrix_factorization_variant_artifacts,
    load_biased_matrix_factorization_manifest,
)


def main() -> None:
    args = parse_args()
    output_dir = (
        RECOMMENDER_AUDIT_DIR
        / "biased_matrix_factorization_training"
        / "current"
    )
    prepare_output_dir(output_dir)

    rows: list[dict[str, Any]] = []
    factor_counts = parse_int_list(args.factor_counts)
    learning_rates = parse_float_list(args.learning_rates)
    regularizations = parse_float_list(args.regularizations)

    for factor_count in factor_counts:
        for learning_rate in learning_rates:
            for regularization in regularizations:
                config = BiasedMatrixFactorizationBuildConfig(
                    factor_count=factor_count,
                    epochs=args.epochs,
                    learning_rate=learning_rate,
                    regularization=regularization,
                    validation_ratio=args.validation_ratio,
                    random_seed=args.random_seed,
                    overwrite=args.overwrite,
                    init_std=args.init_std,
                    early_stopping_patience=args.early_stopping_patience,
                    min_validation_improvement=args.min_validation_improvement,
                )
                rows.append(run_variant(config=config, overwrite=args.overwrite))

    write_json(output_dir / "training_search_results.json", rows)
    write_csv(output_dir / "training_search_results.csv", rows)
    write_json(
        output_dir / "training_search_summary.json",
        {
            "algorithmId": ALGORITHM_ID,
            "generatedAt": datetime.now(timezone.utc).isoformat(),
            "variantCount": len(rows),
            "rows": rows,
        },
    )

    print(f"Training search completed: {output_dir}")
    print(f"Variants evaluated: {len(rows)}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--factor-counts", type=str, default="32,64")
    parser.add_argument("--epochs", type=int, default=100)
    parser.add_argument("--learning-rates", type=str, default="0.005")
    parser.add_argument("--regularizations", type=str, default="0.05")
    parser.add_argument("--validation-ratio", type=float, default=0.01)
    parser.add_argument("--random-seed", type=int, default=42)
    parser.add_argument("--init-std", type=float, default=0.05)
    parser.add_argument("--early-stopping-patience", type=int, default=None)
    parser.add_argument("--min-validation-improvement", type=float, default=0.0)
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


def parse_int_list(raw_value: str) -> list[int]:
    return [int(value.strip()) for value in raw_value.split(",") if value.strip()]


def parse_float_list(raw_value: str) -> list[float]:
    return [float(value.strip()) for value in raw_value.split(",") if value.strip()]


def prepare_output_dir(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=False)


def run_variant(
    *,
    config: BiasedMatrixFactorizationBuildConfig,
    overwrite: bool,
) -> dict[str, Any]:
    artifacts = get_biased_matrix_factorization_variant_artifacts(config.variant_id)

    if overwrite or not artifacts.manifest_path.exists():
        print(f"Training variant {config.variant_id}")
        build_biased_matrix_factorization_model(config)
    else:
        print(f"Skipping existing variant {config.variant_id}")

    manifest = load_biased_matrix_factorization_manifest(config.variant_id)
    training_metrics = json.loads(
        artifacts.training_metrics_path.read_text(encoding="utf-8")
    )
    counts = manifest.get("counts", {})

    return {
        "variantId": config.variant_id,
        "factorCount": config.factor_count,
        "epochs": config.epochs,
        "learningRate": config.learning_rate,
        "regularization": config.regularization,
        "validationRatio": config.validation_ratio,
        "randomSeed": config.random_seed,
        "initStd": config.init_std,
        "earlyStoppingPatience": config.early_stopping_patience,
        "minValidationImprovement": config.min_validation_improvement,
        "completedEpochs": training_metrics.get("completedEpochs"),
        "stoppedEarly": training_metrics.get("stoppedEarly"),
        "bestEpoch": training_metrics.get("bestEpoch"),
        "savedEpoch": training_metrics.get("savedEpoch"),
        "bestValidationRmse": training_metrics.get("bestValidationRmse"),
        "bestValidationMae": training_metrics.get("bestValidationMae"),
        "finalValidationRmse": training_metrics.get("finalValidationRmse"),
        "finalValidationMae": training_metrics.get("finalValidationMae"),
        "elapsedSeconds": training_metrics.get("elapsedSeconds"),
        "modelArtifactSizeMb": counts.get("modelArtifactSizeMb"),
        "status": manifest.get("status"),
        "runtimeStatus": manifest.get("runtimeStatus"),
    }


def write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return

    fieldnames = list(rows[0].keys())
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    main()
