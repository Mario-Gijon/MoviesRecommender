"""Explicit, conservative cleanup for generated dataset workspaces."""

from dataclasses import dataclass
from pathlib import Path
import shutil


class DatasetCleanupError(RuntimeError):
    pass


@dataclass(frozen=True)
class DatasetPaths:
    data_dir: Path

    @property
    def offline(self) -> Path:
        return self.data_dir / "offline_dataset"

    @property
    def required_files(self) -> tuple[Path, ...]:
        csv = self.offline / "csv"
        return (self.offline / "manifest.json", csv / "public_movies.csv", csv / "collaborative_support_movies.csv", csv / "collaborative_ratings.csv")

    @property
    def posters(self) -> Path:
        return self.offline / "images" / "posters"

    def removable(self, mode: str) -> tuple[Path, ...]:
        if mode == "none":
            return ()
        paths = (self.data_dir / "pipeline_cache", self.data_dir / "raw")
        if mode == "standard":
            return paths
        if mode == "minimal":
            return paths + (self.offline / "audit",)
        return ()

    @property
    def preserved(self) -> tuple[Path, ...]:
        return (self.offline / "csv", self.posters, self.offline / "manifest.json", self.data_dir / "recommender_models")


def validate_final_dataset(paths: DatasetPaths, *, skip_posters: bool = False) -> None:
    invalid = [str(path) for path in paths.required_files if not path.is_file() or path.stat().st_size == 0]
    if not paths.posters.is_dir():
        invalid.append(str(paths.posters))
    elif not skip_posters and not any(paths.posters.iterdir()):
        invalid.append(f"{paths.posters} (empty; use --skip-posters only when generation skipped posters)")
    if invalid:
        raise DatasetCleanupError("Final offline dataset is incomplete: " + ", ".join(invalid))


def apply_cleanup(mode: str, paths: DatasetPaths, *, skip_posters: bool = False, dry_run: bool = False) -> tuple[tuple[Path, ...], tuple[Path, ...]]:
    if mode not in {"none", "standard", "minimal"}:
        raise ValueError(f"Unsupported cleanup mode: {mode}")
    if mode != "none":
        validate_final_dataset(paths, skip_posters=skip_posters)
    removed: list[Path] = []
    skipped: list[Path] = []
    for path in paths.removable(mode):
        if not path.exists():
            skipped.append(path)
        elif dry_run:
            removed.append(path)
        else:
            try:
                shutil.rmtree(path)
                removed.append(path)
            except OSError as exc:
                raise DatasetCleanupError(f"Could not remove known cleanup path: {path}") from exc
    return tuple(removed), tuple(skipped)
