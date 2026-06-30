import argparse
import subprocess
import sys
from pathlib import Path

from app.project_paths.dataset_paths import RECOMMENDER_AUDIT_DIR
from pipelines.recommender_evaluation.collaborative_audit_cases import (
    ModelEvaluationConfig,
    StandSimulationConfig,
    create_model_evaluation_split,
    create_stand_simulation_split,
    write_evaluation_cases_json,
    write_split_metadata_json,
    write_train_ratings_csv,
)


MODE_CHOICES = ["model", "stand", "production", "all"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=MODE_CHOICES, required=True)
    parser.add_argument("--rebuild-models", action="store_true")
    parser.add_argument("--skip-rebuild-models", action="store_true")
    parser.add_argument("--skip-bmf", action="store_true")
    parser.add_argument("--case-count", type=int, default=100)
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--runtime-repeats", type=int, default=3)
    parser.add_argument("--api-repeats", type=int, default=1)
    parser.add_argument("--skip-api", action="store_true")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--variant", action="append", default=None)

    parser.add_argument("--top-k", type=int, default=200)
    parser.add_argument("--min-support", type=int, default=25)
    parser.add_argument("--factors", type=int, default=64)
    parser.add_argument("--epochs", type=int, default=20)
    parser.add_argument("--learning-rate", type=float, default=0.005)
    parser.add_argument("--regularization", type=float, default=0.05)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    rebuild_models = _resolve_rebuild_models(args)

    if args.mode in ("stand", "all"):
        run_leakage_free_mode(
            mode_name="stand_simulation",
            args=args,
            rebuild_models=rebuild_models,
        )

    if args.mode in ("model", "all"):
        run_leakage_free_mode(
            mode_name="model_evaluation",
            args=args,
            rebuild_models=rebuild_models,
        )

    if args.mode in ("production", "all"):
        run_production_mode(args)


def run_leakage_free_mode(
    *,
    mode_name: str,
    args: argparse.Namespace,
    rebuild_models: bool,
) -> None:
    mode_root = (
        RECOMMENDER_AUDIT_DIR
        / "collaborative_comparison"
        / "current"
        / mode_name
    )
    split_dir = mode_root / "split"
    models_dir = mode_root / "models"
    metrics_dir = mode_root / "metrics"

    split_dir.mkdir(parents=True, exist_ok=True)
    models_dir.mkdir(parents=True, exist_ok=True)

    evaluation_cases_path = split_dir / "evaluation_cases.json"
    split_metadata_path = split_dir / "split_metadata.json"
    train_ratings_path = split_dir / "train_ratings.csv"

    if not _split_files_exist(
        evaluation_cases_path=evaluation_cases_path,
        split_metadata_path=split_metadata_path,
        train_ratings_path=train_ratings_path,
    ):
        result = (
            create_stand_simulation_split(
                config=StandSimulationConfig(
                    case_count=args.case_count,
                    seed=args.seed,
                )
            )
            if mode_name == "stand_simulation"
            else create_model_evaluation_split(
                config=ModelEvaluationConfig(
                    case_count=args.case_count,
                    seed=args.seed,
                )
            )
        )
        write_evaluation_cases_json(evaluation_cases_path, result.evaluation_cases)
        write_split_metadata_json(split_metadata_path, result.metadata)
        write_train_ratings_csv(train_ratings_path, result.train_ratings)
        print(f"Generated leakage-free split for {mode_name}: {split_dir}")
    else:
        print(f"Reusing existing leakage-free split for {mode_name}: {split_dir}")

    if rebuild_models:
        run_build_models(
            args=args,
            ratings_path=train_ratings_path,
            artifact_root=models_dir,
        )
    elif not has_any_collaborative_artifact(models_dir):
        raise RuntimeError(
            f"Leakage-free audit mode {mode_name} requires audit artifacts under {models_dir}. "
            "Pass --rebuild-models or prebuild them explicitly."
        )

    run_compare(
        args=args,
        evaluation_cases_path=evaluation_cases_path,
        artifact_root=models_dir,
        output_dir=metrics_dir,
        candidate_universe=(
            "public_plus_support"
            if mode_name == "model_evaluation"
            else "public_only"
        ),
    )


def run_production_mode(args: argparse.Namespace) -> None:
    output_dir = (
        RECOMMENDER_AUDIT_DIR
        / "collaborative_comparison"
        / "current"
        / "production_diagnostic"
        / "metrics"
    )
    run_compare(
        args=args,
        output_dir=output_dir,
        candidate_universe="public_only",
    )


def run_build_models(
    *,
    args: argparse.Namespace,
    ratings_path: Path,
    artifact_root: Path,
) -> None:
    command = [
        sys.executable,
        "pipelines/recommender_training/build_collaborative_model.py",
        "--model",
        "all" if not args.skip_bmf else "all",
        "--ratings-path",
        str(ratings_path),
        "--artifact-root",
        str(artifact_root),
        "--overwrite",
        "--top-k",
        str(args.top_k),
        "--min-support",
        str(args.min_support),
        "--factors",
        str(args.factors),
        "--epochs",
        str(args.epochs),
        "--learning-rate",
        str(args.learning_rate),
        "--regularization",
        str(args.regularization),
    ]

    if args.skip_bmf:
        for model_name in (
            "popularity_baseline",
            "item_knn_cosine",
            "user_knn_pearson_shrinkage",
        ):
            _run_subprocess(
                command=[
                    sys.executable,
                    "pipelines/recommender_training/build_collaborative_model.py",
                    "--model",
                    model_name,
                    "--ratings-path",
                    str(ratings_path),
                    "--artifact-root",
                    str(artifact_root),
                    "--overwrite",
                    "--top-k",
                    str(args.top_k),
                    "--min-support",
                    str(args.min_support),
                    "--factors",
                    str(args.factors),
                    "--epochs",
                    str(args.epochs),
                    "--learning-rate",
                    str(args.learning_rate),
                    "--regularization",
                    str(args.regularization),
                ],
                description=f"build {model_name} audit artifacts",
            )
        return

    _run_subprocess(
        command=command,
        description="build collaborative audit artifacts",
    )


def run_compare(
    *,
    args: argparse.Namespace,
    output_dir: Path,
    evaluation_cases_path: Path | None = None,
    artifact_root: Path | None = None,
    candidate_universe: str = "public_only",
) -> None:
    command = [
        sys.executable,
        "pipelines/recommender_evaluation/compare_collaborative_recommenders.py",
        "--output-dir",
        str(output_dir),
        "--case-count",
        str(args.case_count),
        "--limit",
        str(args.limit),
        "--runtime-repeats",
        str(args.runtime_repeats),
        "--api-repeats",
        str(args.api_repeats),
        "--candidate-universe",
        candidate_universe,
    ]

    if args.skip_api:
        command.append("--skip-api")

    if evaluation_cases_path is not None:
        command.extend(["--evaluation-cases-path", str(evaluation_cases_path)])

    if artifact_root is not None:
        command.extend(["--artifact-root", str(artifact_root)])

    for variant in args.variant or []:
        command.extend(["--variant", variant])

    _run_subprocess(
        command=command,
        description=f"run collaborative comparison into {output_dir}",
    )


def has_any_collaborative_artifact(artifact_root: Path) -> bool:
    return any(artifact_root.rglob("model_manifest.json"))


def _split_files_exist(
    *,
    evaluation_cases_path: Path,
    split_metadata_path: Path,
    train_ratings_path: Path,
) -> bool:
    return (
        evaluation_cases_path.exists()
        and split_metadata_path.exists()
        and train_ratings_path.exists()
    )


def _resolve_rebuild_models(args: argparse.Namespace) -> bool:
    if args.rebuild_models and args.skip_rebuild_models:
        raise RuntimeError(
            "--rebuild-models and --skip-rebuild-models cannot be used together."
        )
    if args.rebuild_models:
        return True
    if args.skip_rebuild_models:
        return False
    return False


def _run_subprocess(*, command: list[str], description: str) -> None:
    print(f"Running: {description}")
    subprocess.run(command, check=True)


if __name__ == "__main__":
    main()
