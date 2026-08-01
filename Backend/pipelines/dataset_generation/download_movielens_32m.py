import argparse

from .movielens_source import MovieLensSourceError, default_paths, prepare_source


def main() -> None:
    args = _parse_args()
    paths = default_paths()
    if args.force:
        paths.zip_path.unlink(missing_ok=True)
    try:
        summary = prepare_source("download", paths=paths)
    except MovieLensSourceError as exc:
        raise SystemExit(f"MovieLens source preparation failed: {exc}") from exc
    print(f"MovieLens source: {summary}")
    print(f"Zip path: {paths.zip_path}")
    print(f"Dataset dir: {paths.dataset_dir}")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Download or reuse the official MovieLens 32M source dataset.",
    )
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


if __name__ == "__main__":
    main()
