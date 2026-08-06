from __future__ import annotations

import os
import shutil
import tempfile
import urllib.request
import zipfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from app.project_paths.dataset_paths import ML_32M_DATASET_DIR, ML_32M_ZIP_PATH


MOVIELENS_32M_URL = "https://files.grouplens.org/datasets/movielens/ml-32m.zip"
REQUIRED_FILENAMES = ("movies.csv", "ratings.csv", "tags.csv", "links.csv")


class MovieLensSourceError(RuntimeError):
    pass


@dataclass(frozen=True)
class MovieLensSourcePaths:
    dataset_dir: Path
    zip_path: Path


def default_paths() -> MovieLensSourcePaths:
    return MovieLensSourcePaths(ML_32M_DATASET_DIR, ML_32M_ZIP_PATH)


def validate_extracted_files(dataset_dir: Path) -> tuple[Path, ...]:
    try:
        paths = tuple(dataset_dir / name for name in REQUIRED_FILENAMES)
        missing = [path.name for path in paths if not path.is_file() or path.stat().st_size == 0]
    except OSError as exc:
        raise MovieLensSourceError("MovieLens raw files could not be inspected.") from exc
    if missing:
        raise MovieLensSourceError("MovieLens 32M raw files are incomplete: " + ", ".join(missing))
    return paths


def has_valid_extracted_files(dataset_dir: Path) -> bool:
    try:
        validate_extracted_files(dataset_dir)
    except MovieLensSourceError:
        return False
    return True


def inspect_zip(zip_path: Path) -> dict[str, str]:
    try:
        if not zip_path.is_file():
            raise MovieLensSourceError("MovieLens ZIP path is not a readable file.")
        with zipfile.ZipFile(zip_path) as archive:
            members = archive.infolist()
    except MovieLensSourceError:
        raise
    except (OSError, zipfile.BadZipFile) as exc:
        raise MovieLensSourceError("MovieLens ZIP could not be read.") from exc
    candidates: dict[tuple[str, ...], dict[str, list[str]]] = {}
    for member in members:
        path = PurePosixPath(member.filename)
        if path.is_absolute() or ".." in path.parts:
            raise MovieLensSourceError("MovieLens ZIP contains an unsafe archive path.")
        if not member.is_dir() and path.name in REQUIRED_FILENAMES:
            candidates.setdefault(path.parts[:-1], {}).setdefault(path.name, []).append(member.filename)
    complete = [entries for entries in candidates.values() if set(entries) == set(REQUIRED_FILENAMES)]
    if len(complete) != 1:
        raise MovieLensSourceError("MovieLens ZIP must contain exactly one complete MovieLens 32M file set.")
    selected = complete[0]
    if any(len(selected[name]) != 1 for name in REQUIRED_FILENAMES):
        raise MovieLensSourceError("MovieLens ZIP contains duplicate required files.")
    return {name: selected[name][0] for name in REQUIRED_FILENAMES}


def import_zip(zip_path: Path, *, paths: MovieLensSourcePaths | None = None) -> None:
    paths = paths or default_paths()
    members = inspect_zip(zip_path)
    try:
        paths.dataset_dir.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="movielens-import-", dir=paths.dataset_dir.parent) as temporary:
            staging = Path(temporary) / "ml-32m"
            staging.mkdir()
            with zipfile.ZipFile(zip_path) as archive:
                for filename, member in members.items():
                    with archive.open(member) as source, (staging / filename).open("wb") as target:
                        shutil.copyfileobj(source, target)
            validate_extracted_files(staging)
            _replace_raw_files(staging, paths.dataset_dir)
    except MovieLensSourceError:
        raise
    except (OSError, zipfile.BadZipFile) as exc:
        raise MovieLensSourceError("MovieLens ZIP could not be imported safely.") from exc


def prepare_source(
    source: str, *, paths: MovieLensSourcePaths | None = None, zip_path: Path | None = None,
    force: bool = False, download: Callable[[str, Path], object] | None = None,
) -> str:
    paths = paths or default_paths()
    if source == "existing":
        validate_extracted_files(paths.dataset_dir)
        return "reused existing raw files"
    if source == "zip":
        if zip_path is None:
            raise MovieLensSourceError("--source zip requires --zip-path.")
        import_zip(zip_path, paths=paths)
        return "imported custom MovieLens ZIP"
    if source != "download":
        raise MovieLensSourceError(f"Unsupported MovieLens source: {source}")
    if not force and has_valid_extracted_files(paths.dataset_dir):
        return "reused existing raw files"
    outcome = "reused cached ZIP"
    if force or not _is_valid_zip(paths.zip_path):
        _download_validated_zip(paths.zip_path, download=download)
        outcome = "downloaded official MovieLens ZIP"
    import_zip(paths.zip_path, paths=paths)
    return outcome


def _is_valid_zip(path: Path) -> bool:
    try:
        inspect_zip(path)
    except MovieLensSourceError:
        return False
    return True


def _download_validated_zip(path: Path, *, download: Callable[[str, Path], object] | None) -> None:
    temporary = path.with_suffix(path.suffix + ".part")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        (download or urllib.request.urlretrieve)(MOVIELENS_32M_URL, temporary)
        inspect_zip(temporary)
        os.replace(temporary, path)
    except MovieLensSourceError:
        _discard_temporary(temporary)
        raise
    except OSError as exc:
        _discard_temporary(temporary)
        raise MovieLensSourceError("MovieLens official ZIP download or replacement failed.") from exc


def _discard_temporary(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass


def _replace_raw_files(staging: Path, destination: Path) -> None:
    try:
        destination.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="movielens-backup-", dir=destination.parent) as temporary:
            backup = Path(temporary)
            moved: list[str] = []
            try:
                for name in REQUIRED_FILENAMES:
                    target = destination / name
                    if target.exists():
                        os.replace(target, backup / name)
                    os.replace(staging / name, target)
                    moved.append(name)
            except OSError:
                for name in moved:
                    (destination / name).unlink(missing_ok=True)
                for name in REQUIRED_FILENAMES:
                    saved = backup / name
                    if saved.exists():
                        os.replace(saved, destination / name)
                raise
    except OSError as exc:
        raise MovieLensSourceError("MovieLens raw files could not be replaced safely.") from exc
