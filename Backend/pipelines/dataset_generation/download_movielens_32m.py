import argparse
from pathlib import Path
import urllib.request
import zipfile

from app.project_paths.dataset_paths import ML_32M_EXTRACT_DIR, ML_32M_ZIP_PATH


MOVIELENS_32M_URL = "https://files.grouplens.org/datasets/movielens/ml-32m.zip"


def main() -> None:
    args = _parse_args()

    ML_32M_ZIP_PATH.parent.mkdir(parents=True, exist_ok=True)

    downloaded = False
    extracted = False

    if args.force or not ML_32M_ZIP_PATH.exists():
        urllib.request.urlretrieve(MOVIELENS_32M_URL, ML_32M_ZIP_PATH)
        downloaded = True

    if args.force or not _has_extracted_files(ML_32M_EXTRACT_DIR):
        ML_32M_EXTRACT_DIR.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(ML_32M_ZIP_PATH, "r") as zip_file:
            zip_file.extractall(ML_32M_EXTRACT_DIR)
        extracted = True

    print(f"Dataset URL: {MOVIELENS_32M_URL}")
    print(f"Zip path: {ML_32M_ZIP_PATH}")
    print(f"Extract dir: {ML_32M_EXTRACT_DIR}")
    print(f"Downloaded zip: {'yes' if downloaded else 'no'}")
    print(f"Extracted files: {'yes' if extracted else 'no'}")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Download and extract the MovieLens 32M development dataset.",
    )
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def _has_extracted_files(extract_dir: Path) -> bool:
    dataset_dir = extract_dir / "ml-32m"
    return dataset_dir.exists() and any(dataset_dir.iterdir())


if __name__ == "__main__":
    main()

