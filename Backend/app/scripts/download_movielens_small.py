from pathlib import Path
import sys
import urllib.request
import zipfile

from app.infrastructure.datasets.movielens_paths import (
    ML_LATEST_SMALL_EXTRACT_DIR,
    ML_LATEST_SMALL_ZIP_PATH,
)


MOVIELENS_SMALL_URL = "https://files.grouplens.org/datasets/movielens/ml-latest-small.zip"


def main() -> None:
    force = "--force" in sys.argv[1:]

    ML_LATEST_SMALL_ZIP_PATH.parent.mkdir(parents=True, exist_ok=True)

    downloaded = False
    extracted = False

    if force or not ML_LATEST_SMALL_ZIP_PATH.exists():
        urllib.request.urlretrieve(MOVIELENS_SMALL_URL, ML_LATEST_SMALL_ZIP_PATH)
        downloaded = True

    if force or not _has_extracted_files(ML_LATEST_SMALL_EXTRACT_DIR):
        ML_LATEST_SMALL_EXTRACT_DIR.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(ML_LATEST_SMALL_ZIP_PATH, "r") as zip_file:
            zip_file.extractall(ML_LATEST_SMALL_EXTRACT_DIR)
        extracted = True

    print(f"Dataset URL: {MOVIELENS_SMALL_URL}")
    print(f"Zip path: {ML_LATEST_SMALL_ZIP_PATH}")
    print(f"Extract dir: {ML_LATEST_SMALL_EXTRACT_DIR}")
    print(f"Downloaded zip: {'yes' if downloaded else 'no'}")
    print(f"Extracted files: {'yes' if extracted else 'no'}")


def _has_extracted_files(extract_dir: Path) -> bool:
    dataset_dir = extract_dir / "ml-latest-small"
    return dataset_dir.exists() and any(dataset_dir.iterdir())


if __name__ == "__main__":
    main()

