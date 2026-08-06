"""Interactive entry point for Movies Recommender."""

from manager.cli import main
from manager.runtime import repository_runtime


if __name__ == "__main__":
    raise SystemExit(main(runtime=repository_runtime()))
