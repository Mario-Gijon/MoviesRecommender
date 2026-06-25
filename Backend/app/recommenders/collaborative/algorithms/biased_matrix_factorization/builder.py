import argparse
import json
import time
from typing import Any

import numpy as np
import pandas as pd

from app.project_paths.dataset_paths import OFFLINE_DATASET_COLLABORATIVE_RATINGS_CSV_PATH
from app.recommenders.collaborative.algorithms.biased_matrix_factorization.models import (
    BiasedMatrixFactorizationBuildConfig,
)
from app.recommenders.collaborative.algorithms.biased_matrix_factorization.storage import (
    file_size_mb,
    prepare_biased_matrix_factorization_artifacts,
    write_model_manifest,
)
from app.recommenders.collaborative.algorithms.biased_matrix_factorization.training_core import (
    compute_rmse_mae,
    train_epoch_sgd,
)


def build_biased_matrix_factorization_model(
    config: BiasedMatrixFactorizationBuildConfig,
) -> None:
    _validate_config(config)

    started_at = time.perf_counter()
    artifacts = prepare_biased_matrix_factorization_artifacts(config)

    print("Building Biased Matrix Factorization model.")
    print(f"Variant: {config.variant_id}")
    print(f"Output directory: {artifacts.variant_dir}")

    ratings_df = _load_ratings_dataframe(chunksize=config.chunksize)
    indexed_ratings = _build_indexed_ratings(ratings_df)

    del ratings_df

    split = _split_train_validation(
        user_indices=indexed_ratings["user_indices"],
        movie_indices=indexed_ratings["movie_indices"],
        ratings=indexed_ratings["ratings"],
        validation_ratio=config.validation_ratio,
        random_seed=config.random_seed,
    )

    train_rating_count = int(split["train_ratings"].shape[0])
    validation_rating_count = int(split["validation_ratings"].shape[0])

    global_mean = float(np.mean(split["train_ratings"], dtype=np.float64))

    print(f"Users: {indexed_ratings['user_ids'].shape[0]}")
    print(f"Movies: {indexed_ratings['movie_ids'].shape[0]}")
    print(f"Ratings: {indexed_ratings['ratings'].shape[0]}")
    print(f"Train ratings: {train_rating_count}")
    print(f"Validation ratings: {validation_rating_count}")
    print(f"Global mean: {global_mean:.6f}")

    rng = np.random.default_rng(config.random_seed)

    user_count = int(indexed_ratings["user_ids"].shape[0])
    movie_count = int(indexed_ratings["movie_ids"].shape[0])

    user_biases = np.zeros(user_count, dtype=np.float32)
    movie_biases = np.zeros(movie_count, dtype=np.float32)

    user_factors = rng.normal(
        loc=0.0,
        scale=config.init_std,
        size=(user_count, config.factor_count),
    ).astype(np.float32)
    movie_factors = rng.normal(
        loc=0.0,
        scale=config.init_std,
        size=(movie_count, config.factor_count),
    ).astype(np.float32)

    epoch_metrics: list[dict[str, Any]] = []
    best_epoch = 0
    best_validation_rmse = float("inf")
    best_validation_mae = float("inf")
    best_user_biases: np.ndarray | None = None
    best_movie_biases: np.ndarray | None = None
    best_user_factors: np.ndarray | None = None
    best_movie_factors: np.ndarray | None = None
    best_validation_improved_at_epoch = 0
    stopped_early = False
    stopped_at_epoch: int | None = None

    for epoch in range(1, config.epochs + 1):
        epoch_started_at = time.perf_counter()
        order = rng.permutation(train_rating_count).astype(np.int32)

        train_epoch_sgd(
            user_indices=split["train_user_indices"],
            movie_indices=split["train_movie_indices"],
            ratings=split["train_ratings"],
            order=order,
            global_mean=global_mean,
            user_biases=user_biases,
            movie_biases=movie_biases,
            user_factors=user_factors,
            movie_factors=movie_factors,
            learning_rate=config.learning_rate,
            regularization=config.regularization,
        )

        train_rmse, train_mae = compute_rmse_mae(
            user_indices=split["train_user_indices"],
            movie_indices=split["train_movie_indices"],
            ratings=split["train_ratings"],
            global_mean=global_mean,
            user_biases=user_biases,
            movie_biases=movie_biases,
            user_factors=user_factors,
            movie_factors=movie_factors,
            min_rating=config.min_rating,
            max_rating=config.max_rating,
        )

        validation_rmse, validation_mae = compute_rmse_mae(
            user_indices=split["validation_user_indices"],
            movie_indices=split["validation_movie_indices"],
            ratings=split["validation_ratings"],
            global_mean=global_mean,
            user_biases=user_biases,
            movie_biases=movie_biases,
            user_factors=user_factors,
            movie_factors=movie_factors,
            min_rating=config.min_rating,
            max_rating=config.max_rating,
        )

        epoch_elapsed_seconds = round(time.perf_counter() - epoch_started_at, 3)

        epoch_metric = {
            "epoch": epoch,
            "trainRmse": round(float(train_rmse), 6),
            "trainMae": round(float(train_mae), 6),
            "validationRmse": round(float(validation_rmse), 6),
            "validationMae": round(float(validation_mae), 6),
            "elapsedSeconds": epoch_elapsed_seconds,
        }
        epoch_metrics.append(epoch_metric)

        validation_improvement = best_validation_rmse - float(validation_rmse)
        if validation_improvement > config.min_validation_improvement:
            best_epoch = epoch
            best_validation_rmse = float(validation_rmse)
            best_validation_mae = float(validation_mae)
            best_user_biases = user_biases.copy()
            best_movie_biases = movie_biases.copy()
            best_user_factors = user_factors.copy()
            best_movie_factors = movie_factors.copy()
            best_validation_improved_at_epoch = epoch

        print(
            "Epoch",
            epoch,
            f"train_rmse={train_rmse:.6f}",
            f"train_mae={train_mae:.6f}",
            f"validation_rmse={validation_rmse:.6f}",
            f"validation_mae={validation_mae:.6f}",
            f"seconds={epoch_elapsed_seconds}",
        )

        if (
            config.early_stopping_patience is not None
            and epoch - best_validation_improved_at_epoch
            >= config.early_stopping_patience
        ):
            stopped_early = True
            stopped_at_epoch = epoch
            print(
                "Early stopping triggered at epoch",
                epoch,
                "best_epoch=",
                best_epoch,
                "best_validation_rmse=",
                f"{best_validation_rmse:.6f}",
            )
            break

    if (
        best_user_biases is None
        or best_movie_biases is None
        or best_user_factors is None
        or best_movie_factors is None
    ):
        raise RuntimeError("Best checkpoint was not captured during training.")

    elapsed_seconds = round(time.perf_counter() - started_at, 3)
    completed_epochs = len(epoch_metrics)
    final_epoch_metrics = epoch_metrics[-1]
    saved_user_biases = best_user_biases
    saved_movie_biases = best_movie_biases
    saved_user_factors = best_user_factors
    saved_movie_factors = best_movie_factors

    _write_artifacts(
        artifacts=artifacts,
        config=config,
        user_ids=indexed_ratings["user_ids"],
        movie_ids=indexed_ratings["movie_ids"],
        user_biases=saved_user_biases,
        movie_biases=saved_movie_biases,
        user_factors=saved_user_factors,
        movie_factors=saved_movie_factors,
        global_stats={
            "globalMean": round(global_mean, 9),
            "ratingMin": config.min_rating,
            "ratingMax": config.max_rating,
            "userCount": user_count,
            "movieCount": movie_count,
            "ratingCount": int(indexed_ratings["ratings"].shape[0]),
            "trainRatingCount": train_rating_count,
            "validationRatingCount": validation_rating_count,
        },
        training_metrics={
            "config": _config_to_dict(config),
            "savedModelSelection": "best_validation_rmse",
            "savedEpoch": best_epoch,
            "epochMetrics": epoch_metrics,
            "bestEpoch": best_epoch,
            "bestValidationRmse": round(best_validation_rmse, 6),
            "bestValidationMae": round(best_validation_mae, 6),
            "finalTrainRmse": final_epoch_metrics["trainRmse"],
            "finalTrainMae": final_epoch_metrics["trainMae"],
            "finalValidationRmse": final_epoch_metrics["validationRmse"],
            "finalValidationMae": final_epoch_metrics["validationMae"],
            "earlyStoppingEnabled": config.early_stopping_patience is not None,
            "earlyStoppingPatience": config.early_stopping_patience,
            "minValidationImprovement": config.min_validation_improvement,
            "stoppedEarly": stopped_early,
            "stoppedAtEpoch": stopped_at_epoch,
            "completedEpochs": completed_epochs,
            "elapsedSeconds": elapsed_seconds,
        },
    )

    counts = _build_manifest_counts(
        artifacts=artifacts,
        rating_count=int(indexed_ratings["ratings"].shape[0]),
        user_count=user_count,
        movie_count=movie_count,
        train_rating_count=train_rating_count,
        validation_rating_count=validation_rating_count,
        build_time_seconds=int(elapsed_seconds),
    )

    training_metrics_summary = {
        "bestEpoch": best_epoch,
        "savedEpoch": best_epoch,
        "savedModelSelection": "best_validation_rmse",
        "bestValidationRmse": round(best_validation_rmse, 6),
        "bestValidationMae": round(best_validation_mae, 6),
        "finalValidationRmse": final_epoch_metrics["validationRmse"],
        "finalValidationMae": final_epoch_metrics["validationMae"],
    }

    write_model_manifest(
        artifacts=artifacts,
        config=config,
        status="trained",
        runtime_status="not_implemented",
        counts=counts,
        training_metrics=training_metrics_summary,
    )

    print("Biased Matrix Factorization training completed.")
    print(f"Status: trained")
    print(f"Runtime status: not_implemented")
    print(f"Best epoch: {best_epoch}")
    print(f"Best validation RMSE: {best_validation_rmse:.6f}")
    print(f"Best validation MAE: {best_validation_mae:.6f}")
    print(f"Elapsed seconds: {elapsed_seconds}")
    print(f"Manifest: {artifacts.manifest_path}")


def _validate_config(config: BiasedMatrixFactorizationBuildConfig) -> None:
    if config.factor_count <= 0:
        raise ValueError("factor_count must be greater than 0.")
    if config.epochs <= 0:
        raise ValueError("epochs must be greater than 0.")
    if config.learning_rate <= 0:
        raise ValueError("learning_rate must be greater than 0.")
    if config.regularization < 0:
        raise ValueError("regularization must be greater than or equal to 0.")
    if not 0 < config.validation_ratio < 1:
        raise ValueError("validation_ratio must be between 0 and 1.")
    if config.chunksize <= 0:
        raise ValueError("chunksize must be greater than 0.")
    if config.batch_size <= 0:
        raise ValueError("batch_size must be greater than 0.")
    if config.init_std <= 0:
        raise ValueError("init_std must be greater than 0.")
    if config.min_rating >= config.max_rating:
        raise ValueError("min_rating must be lower than max_rating.")
    if config.early_stopping_patience is not None and config.early_stopping_patience <= 0:
        raise ValueError("early_stopping_patience must be greater than 0.")
    if config.min_validation_improvement < 0:
        raise ValueError("min_validation_improvement must be greater than or equal to 0.")


def _load_ratings_dataframe(*, chunksize: int) -> pd.DataFrame:
    chunks = []

    for chunk_index, chunk in enumerate(
        pd.read_csv(
            OFFLINE_DATASET_COLLABORATIVE_RATINGS_CSV_PATH,
            usecols=["userId", "movieId", "rating"],
            dtype={
                "userId": "int32",
                "movieId": "int32",
                "rating": "float32",
            },
            chunksize=chunksize,
        ),
        start=1,
    ):
        chunks.append(chunk)
        print("Loaded ratings chunk", chunk_index, "rows:", len(chunk))

    if not chunks:
        raise RuntimeError("No collaborative ratings were found.")

    ratings = pd.concat(chunks, ignore_index=True)
    return ratings.drop_duplicates(
        subset=["userId", "movieId"],
        keep="last",
    )


def _build_indexed_ratings(ratings_df: pd.DataFrame) -> dict[str, np.ndarray]:
    user_ids = np.sort(ratings_df["userId"].unique()).astype(np.int32)
    movie_ids = np.sort(ratings_df["movieId"].unique()).astype(np.int32)

    user_values = ratings_df["userId"].to_numpy(dtype=np.int32, copy=False)
    movie_values = ratings_df["movieId"].to_numpy(dtype=np.int32, copy=False)

    user_indices = np.searchsorted(user_ids, user_values).astype(np.int32)
    movie_indices = np.searchsorted(movie_ids, movie_values).astype(np.int32)
    ratings = ratings_df["rating"].to_numpy(dtype=np.float32, copy=True)

    return {
        "user_ids": np.ascontiguousarray(user_ids),
        "movie_ids": np.ascontiguousarray(movie_ids),
        "user_indices": np.ascontiguousarray(user_indices),
        "movie_indices": np.ascontiguousarray(movie_indices),
        "ratings": np.ascontiguousarray(ratings),
    }


def _split_train_validation(
    *,
    user_indices: np.ndarray,
    movie_indices: np.ndarray,
    ratings: np.ndarray,
    validation_ratio: float,
    random_seed: int,
) -> dict[str, np.ndarray]:
    rng = np.random.default_rng(random_seed)
    validation_mask = rng.random(ratings.shape[0]) < validation_ratio

    if not np.any(validation_mask):
        validation_mask[0] = True

    if np.all(validation_mask):
        validation_mask[0] = False

    train_mask = ~validation_mask

    return {
        "train_user_indices": np.ascontiguousarray(user_indices[train_mask]),
        "train_movie_indices": np.ascontiguousarray(movie_indices[train_mask]),
        "train_ratings": np.ascontiguousarray(ratings[train_mask]),
        "validation_user_indices": np.ascontiguousarray(user_indices[validation_mask]),
        "validation_movie_indices": np.ascontiguousarray(movie_indices[validation_mask]),
        "validation_ratings": np.ascontiguousarray(ratings[validation_mask]),
    }


def _write_artifacts(
    *,
    artifacts,
    config: BiasedMatrixFactorizationBuildConfig,
    user_ids: np.ndarray,
    movie_ids: np.ndarray,
    user_biases: np.ndarray,
    movie_biases: np.ndarray,
    user_factors: np.ndarray,
    movie_factors: np.ndarray,
    global_stats: dict[str, Any],
    training_metrics: dict[str, Any],
) -> None:
    np.save(artifacts.user_factors_path, user_factors)
    np.save(artifacts.movie_factors_path, movie_factors)

    pd.DataFrame(
        {
            "userId": user_ids,
            "userIndex": np.arange(user_ids.shape[0], dtype=np.int32),
        }
    ).to_csv(
        artifacts.user_index_path,
        index=False,
        encoding="utf-8",
    )

    pd.DataFrame(
        {
            "movieId": movie_ids,
            "movieIndex": np.arange(movie_ids.shape[0], dtype=np.int32),
        }
    ).to_csv(
        artifacts.movie_index_path,
        index=False,
        encoding="utf-8",
    )

    pd.DataFrame(
        {
            "userId": user_ids,
            "userIndex": np.arange(user_ids.shape[0], dtype=np.int32),
            "userBias": user_biases,
        }
    ).to_csv(
        artifacts.user_biases_path,
        index=False,
        encoding="utf-8",
    )

    pd.DataFrame(
        {
            "movieId": movie_ids,
            "movieIndex": np.arange(movie_ids.shape[0], dtype=np.int32),
            "movieBias": movie_biases,
        }
    ).to_csv(
        artifacts.movie_biases_path,
        index=False,
        encoding="utf-8",
    )

    artifacts.global_stats_path.write_text(
        json.dumps(global_stats, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    artifacts.training_metrics_path.write_text(
        json.dumps(training_metrics, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _build_manifest_counts(
    *,
    artifacts,
    rating_count: int,
    user_count: int,
    movie_count: int,
    train_rating_count: int,
    validation_rating_count: int,
    build_time_seconds: int,
) -> dict[str, Any]:
    artifact_paths = [
        artifacts.movie_factors_path,
        artifacts.movie_biases_path,
        artifacts.movie_index_path,
        artifacts.global_stats_path,
        artifacts.training_metrics_path,
        artifacts.user_factors_path,
        artifacts.user_biases_path,
        artifacts.user_index_path,
    ]

    model_artifact_size_mb = round(
        sum(path.stat().st_size for path in artifact_paths if path.exists())
        / 1024
        / 1024,
        3,
    )

    return {
        "ratings": rating_count,
        "users": user_count,
        "modelMovies": movie_count,
        "publicMovies": None,
        "supportMovies": None,
        "trainRatings": train_rating_count,
        "validationRatings": validation_rating_count,
        "buildTimeSeconds": build_time_seconds,
        "modelArtifactSizeMb": model_artifact_size_mb,
        "movieFactorsSizeMb": file_size_mb(artifacts.movie_factors_path),
        "movieBiasesSizeMb": file_size_mb(artifacts.movie_biases_path),
        "movieIndexSizeMb": file_size_mb(artifacts.movie_index_path),
        "userFactorsSizeMb": file_size_mb(artifacts.user_factors_path),
        "userBiasesSizeMb": file_size_mb(artifacts.user_biases_path),
        "userIndexSizeMb": file_size_mb(artifacts.user_index_path),
        "globalStatsSizeMb": file_size_mb(artifacts.global_stats_path),
        "trainingMetricsSizeMb": file_size_mb(artifacts.training_metrics_path),
    }


def _config_to_dict(config: BiasedMatrixFactorizationBuildConfig) -> dict[str, Any]:
    return {
        "factorCount": config.factor_count,
        "epochs": config.epochs,
        "learningRate": config.learning_rate,
        "regularization": config.regularization,
        "validationRatio": config.validation_ratio,
        "randomSeed": config.random_seed,
        "chunksize": config.chunksize,
        "batchSize": config.batch_size,
        "initStd": config.init_std,
        "minRating": config.min_rating,
        "maxRating": config.max_rating,
        "earlyStoppingPatience": config.early_stopping_patience,
        "minValidationImprovement": config.min_validation_improvement,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--factor-count", type=int, default=64)
    parser.add_argument("--epochs", type=int, default=20)
    parser.add_argument("--learning-rate", type=float, default=0.005)
    parser.add_argument("--regularization", type=float, default=0.05)
    parser.add_argument("--validation-ratio", type=float, default=0.1)
    parser.add_argument("--random-seed", type=int, default=42)
    parser.add_argument("--chunksize", type=int, default=500_000)
    parser.add_argument("--batch-size", type=int, default=8192)
    parser.add_argument("--init-std", type=float, default=0.05)
    parser.add_argument("--early-stopping-patience", type=int, default=None)
    parser.add_argument("--min-validation-improvement", type=float, default=0.0)
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
            batch_size=args.batch_size,
            init_std=args.init_std,
            early_stopping_patience=args.early_stopping_patience,
            min_validation_improvement=args.min_validation_improvement,
        )
    )


if __name__ == "__main__":
    main()
