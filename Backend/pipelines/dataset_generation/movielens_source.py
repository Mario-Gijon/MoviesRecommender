from __future__ import annotations

import os
import shutil
import tempfile
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from app.project_paths.dataset_paths import (
    ML_32M_DATASET_DIR,
    ML_32M_ZIP_PATH,
)


MOVIELENS_32M_URL = "https://files.grouplens.org/datasets/movielens/ml-32m.zip"
REQUIRED_FILENAMES = ("movies.csv", "ratings.csv", "tags.csv", "links.csv")


class MovieLensSourceError(RuntimeError):
    pass


@dataclass(frozen=True)
class MovieLensSourcePaths:
    dataset_dir: Path
    zip_path: Path


def default_paths() -> MovieLensSourcePaths:
    return MovieLensSourcePaths(dataset_dir=ML_32M_DATASET_DIR, zip_path=ML_32M_ZIP_PATH)


def validate_extracted_files(dataset_dir: Path) -> tuple[Path, ...]:
    paths = tuple(dataset_dir / filename for filename in REQUIRED_FILENAMES)
    missing = [path.name for path in paths if not path.is_file() or path.stat().st_size == 0]
    if missing:
        raise MovieLensSourceError(
            "MovieLens 32M raw files are incomplete: " + ", ".join(missing)
        )
    return paths


def has_valid_extracted_files(dataset_dir: Path) -> bool:
    try:
        validate_extracted_files(dataset_dir)
    except MovieLensSourceError:
        return False
    return True


def inspect_zip(zip_path: Path) -> dict[str, str]:
    if not zip_path.is_file():
        raise MovieLensSourceError("MovieLens ZIP path is not a readable file.")
    try:
        with zipfile.ZipFile(zip_path) as archive:
            members = archive.infolist()
    except (OSError, zipfile.BadZipFile) as exc:
        raise MovieLensSourceError("MovieLens ZIP could not be read.") from exc

    candidates: dict[tuple[str, ...], dict[str, list[str]]] = {}
    for member in members:
        path = PurePosixPath(member.filename)
        if path.is_absolute() or ".." in path.parts:
            raise MovieLensSourceError("MovieLens ZIP contains an unsafe archive path.")
        if member.is_dir() or path.name not in REQUIRED_FILENAMES:
            continue
        candidates.setdefault(path.parts[:-1], {}).setdefault(path.name, []).append(member.filename)

    complete_sets = [
        entries
        for entries in candidates.values()
        if set(entries) == set(REQUIRED_FILENAMES)
    ]
    if len(complete_sets) != 1:
        raise MovieLensSourceError(
            "MovieLens ZIP must contain exactly one complete MovieLens 32M file set."
        )
    selected = complete_sets[0]
    if any(len(selected[name]) != 1 for name in REQUIRED_FILENAMES):
        raise MovieLensSourceError("MovieLens ZIP contains duplicate required files.")
    return {name: selected[name][0] for name in REQUIRED_FILENAMES}


def import_zip(zip_path: Path, *, paths: MovieLensSourcePaths | None = None) -> str:
    paths = paths or default_paths()
    members = inspect_zip(zip_path)
    paths.dataset_dir.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="movielens-import-", dir=paths.dataset_dir.parent) as temporary:
        staging = Path(temporary) / "ml-32m"
        staging.mkdir()
        try:
            with zipfile.ZipFile(zip_path) as archive:
                for filename, member_name in members.items():
                    with archive.open(member_name) as source, (staging / filename).open("wb") as target:
                        shutil.copyfileobj(source, target)
        except (OSError, zipfile.BadZipFile) as exc:
            raise MovieLensSourceError("MovieLens ZIP could not be imported.") from exc
        validate_extracted_files(staging)
        _replace_raw_files(staging, paths.dataset_dir)
    return "imported"


def prepare_source(
    source: str,
    *,
    paths: MovieLensSourcePaths | None = None,
    zip_path: Path | None = None,
    download: callable | None = None,
) -> str:
    paths = paths or default_paths()
    if source == "existing":
        validate_extracted_files(paths.dataset_dir)
        return "reused existing raw files"
    if source == "zip":
        if zip_path is None:
            raise MovieLensSourceError("--source zip requires --zip-path.")
        return import_zip(zip_path, paths=paths)
    if source != "download":
        raise MovieLensSourceError(f"Unsupported MovieLens source: {source}")
    if has_valid_extracted_files(paths.dataset_dir):
        return "reused existing raw files"
    if not paths.zip_path.exists():
        paths.zip_path.parent.mkdir(parents=True, exist_ok=True)
        downloader = download or urllib.request.urlretrieve
        temporary = paths.zip_path.with_suffix(".zip.part")
        try:
            downloader(MOVIELENS_32M_URL, temporary)
            os.replace(temporary, paths.zip_path)
        except OSError as exc:
            temporary.unlink(missing_ok=True)
            raise MovieLensSourceError("MovieLens 32M download failed.") from exc
    import_zip(paths.zip_path, paths=paths)
    return "reused cached ZIP" if paths.zip_path.exists() else "downloaded MovieLens ZIP"


def _replace_raw_files(staging: Path, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="movielens-backup-", dir=destination.parent) as temporary:
        backup = Path(temporary)
        moved: list[str] = []
        try:
            for filename in REQUIRED_FILENAMES:
                target = destination / filename
                if target.exists():
                    os.replace(target, backup / filename)
                os.replace(staging / filename, target)
                moved.append(filename)
        except OSError as exc:
            for filename in moved:
                target = destination / filename
                if target.exists():
                    target.unlink()
            for filename in REQUIRED_FILENAMES:
                saved = backup / filename
                if saved.exists():
                    os.replace(saved, destination / filename)
            raise MovieLensSourceError("MovieLens raw files could not be replaced safely.") from exc
