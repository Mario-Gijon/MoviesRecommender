"""Build the standalone production manager using only the standard library."""

from __future__ import annotations

import shutil
from pathlib import Path
import sys
import zipapp


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "dist" / "MoviesRecommender"
MANAGER_FILES = (
    "__init__.py",
    "application.py",
    "bootstrap.py",
    "cli.py",
    "compose.py",
    "config.py",
    "console.py",
    "dataset.py",
    "models.py",
    "runtime.py",
)


def main() -> int:
    required = [ROOT / "compose.yaml", *(ROOT / "manager" / name for name in MANAGER_FILES)]
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        print("No se puede crear el paquete; faltan: " + ", ".join(missing), file=sys.stderr)
        return 1
    if OUTPUT.exists():
        shutil.rmtree(OUTPUT)
    staging = OUTPUT / ".staging"
    package = staging / "manager"
    package.mkdir(parents=True)
    for name in MANAGER_FILES:
        shutil.copyfile(ROOT / "manager" / name, package / name)
    (staging / "__main__.py").write_text(
        "from manager.cli import main\n"
        "from manager.runtime import deployment_runtime\n"
        "import sys\n"
        "raise SystemExit(main(runtime=deployment_runtime(sys.argv[0])))\n",
        encoding="utf-8",
    )
    archive = OUTPUT / "manage.pyz"
    zipapp.create_archive(staging, archive, interpreter="/usr/bin/env python3", compressed=True)
    shutil.copyfile(ROOT / "compose.yaml", OUTPUT / "compose.yaml")
    shutil.rmtree(staging)
    for path in (archive, OUTPUT / "compose.yaml"):
        print(f"{path} ({path.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
