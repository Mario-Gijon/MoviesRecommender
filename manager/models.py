"""Recommendation-model lifecycle operations, independent from the frontend."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from manager.compose import DockerCompose, Environment
from manager.config import Configuration
from manager.console import Console


ALGORITHMS = ("tfidf", "popularity", "item_knn", "user_knn", "biased")


class ModelManager:
    def __init__(
        self,
        configuration: Configuration,
        environment: Environment,
        compose: DockerCompose,
        console: Console,
    ) -> None:
        self.configuration = configuration
        self.environment = environment
        self.compose = compose
        self.console = console

    @property
    def data_dir(self) -> Path:
        return self.configuration.data_dir

    @property
    def models_dir(self) -> Path:
        return self.data_dir / "recommender_models"

    @property
    def log_path(self) -> Path:
        return self.models_dir / "last_execution.log"

    def show_existing(self) -> int:
        print(f"Directorio de modelos: {self.models_dir}")
        print(f"Variante activa Item KNN: {self.configuration.item_knn_variant}")
        print(f"Variante activa Biased: {self.configuration.biased_variant}")
        for label, path in self._required_artifacts():
            state = "encontrado" if path.is_file() and path.stat().st_size else "ausente"
            print(f"{label}: {state}")
        compatible, reason = self.validate_compatibility()
        print("Compatibilidad con el dataset: " + ("compatible" if compatible else reason))
        return 0

    def validate_compatibility(self) -> tuple[bool, str]:
        dataset_ok, reason = validate_dataset(self.data_dir)
        if not dataset_ok:
            return False, reason
        state = self.models_dir / "dataset_compatibility.json"
        if not state.is_file():
            return False, "falta dataset_compatibility.json"
        try:
            payload = json.loads(state.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return False, "dataset_compatibility.json no se puede leer"
        if payload.get("datasetFingerprint") != dataset_fingerprint(self.data_dir):
            return False, "los artefactos no corresponden al dataset actual"
        missing = [
            label
            for label, path in self._required_artifacts()
            if not path.is_file() or path.stat().st_size == 0
        ]
        if missing:
            return False, "faltan artefactos obligatorios: " + ", ".join(missing)
        return True, "compatible"

    def validate(self) -> int:
        compatible, reason = self.validate_compatibility()
        print("Modelos: " + ("compatibles" if compatible else "no compatibles"))
        print(reason)
        return 0 if compatible else 1

    def rebuild(self) -> int:
        dataset_ok, reason = validate_dataset(self.data_dir)
        if not dataset_ok:
            print(f"No se pueden reconstruir modelos: {reason}")
            return 1
        print("\nResumen de reconstrucción")
        print(f"Entorno: {self.environment.label}")
        print(f"Dataset: {self.data_dir / 'offline_dataset'}")
        print("Algoritmos: " + ", ".join(ALGORITHMS))
        print(f"Variante Item KNN: {self.configuration.item_knn_variant}")
        print(f"Variante Biased: {self.configuration.biased_variant}")
        print("No se iniciará el frontend ni se reiniciará el backend automáticamente.")
        if not self.console.confirm("¿Reconstruir y entrenar todos los modelos?"):
            return 0
        command = ["run", "--rm", "recommender-build"]
        for algorithm in ALGORITHMS:
            command.extend(["--algorithm", algorithm])
        command.append("--yes")
        if self.compose.run_with_log(
            command,
            self.log_path,
            profiles=("maintenance",),
        ):
            return 1
        write_dataset_compatibility(self.data_dir)
        api_status = self.compose.service_status("api")
        if api_status.is_running and self.console.confirm(
            "El backend está ejecutándose. ¿Reiniciarlo para cargar los artefactos?"
        ):
            return self.compose.run(["restart", "api"])
        return 0

    def audit(self) -> int:
        compatible, reason = self.validate_compatibility()
        if not compatible:
            print(f"No se puede ejecutar la auditoría: {reason}")
            return 1
        print(f"Auditoría de modelos · {self.environment.label}")
        if not self.console.confirm("¿Ejecutar auditoría de los modelos compatibles?"):
            return 0
        return self.compose.run(
            ["run", "--rm", "recommender-audit"],
            profiles=("maintenance",),
        )

    def show_last_log(self) -> int:
        if not self.log_path.is_file():
            print("No hay registro de una reconstrucción de modelos anterior.")
            return 0
        print(self.log_path.read_text(encoding="utf-8"), end="")
        return 0

    def _required_artifacts(self) -> tuple[tuple[str, Path], ...]:
        collaborative = self.models_dir / "collaborative"
        return (
            (
                "TF-IDF",
                self.models_dir / "content_based" / "content_feature_metadata.json",
            ),
            (
                "Popularity",
                collaborative / "popularity_baseline" / "default" / "model_manifest.json",
            ),
            (
                "Item KNN",
                collaborative
                / "item_knn_cosine"
                / self.configuration.item_knn_variant
                / "model_manifest.json",
            ),
            (
                "User KNN",
                collaborative
                / "user_knn_pearson_shrinkage"
                / "default"
                / "model_manifest.json",
            ),
            (
                "Biased",
                collaborative
                / "biased_matrix_factorization"
                / self.configuration.biased_variant
                / "model_manifest.json",
            ),
        )


def validate_dataset(data_dir: Path) -> tuple[bool, str]:
    dataset = data_dir / "offline_dataset"
    required = (
        dataset / "manifest.json",
        dataset / "csv" / "public_movies.csv",
        dataset / "csv" / "collaborative_support_movies.csv",
        dataset / "csv" / "collaborative_ratings.csv",
        dataset / "images" / "posters",
    )
    missing = [str(path) for path in required if not path.exists()]
    empty = [str(path) for path in required[:-1] if path.is_file() and path.stat().st_size == 0]
    if missing or empty:
        return False, "dataset offline ausente o inválido: " + ", ".join(missing + empty)
    return True, "dataset válido"


def dataset_fingerprint(data_dir: Path) -> str:
    dataset = data_dir / "offline_dataset"
    digest = hashlib.sha256()
    for path in (
        dataset / "manifest.json",
        dataset / "csv" / "public_movies.csv",
        dataset / "csv" / "collaborative_support_movies.csv",
        dataset / "csv" / "collaborative_ratings.csv",
    ):
        with path.open("rb") as file:
            for block in iter(lambda: file.read(1024 * 1024), b""):
                digest.update(block)
    return digest.hexdigest()


def write_dataset_compatibility(data_dir: Path) -> None:
    state = data_dir / "recommender_models" / "dataset_compatibility.json"
    state.parent.mkdir(parents=True, exist_ok=True)
    state.write_text(
        json.dumps(
            {
                "datasetFingerprint": dataset_fingerprint(data_dir),
                "datasetManifest": "offline_dataset/manifest.json",
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
