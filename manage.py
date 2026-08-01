"""Small cross-platform Docker Compose manager for Movies Recommender."""
from __future__ import annotations

import argparse
import getpass
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from urllib.error import URLError
from urllib.request import urlopen


ROOT = Path(__file__).resolve().parent
ENV_FILE = ROOT / ".env"
EXAMPLE_ENV = ROOT / ".env.example"
MANAGED_KEYS = ("DATA_DIR", "MOVIES_RECOMMENDER_TMDB_BEARER_TOKEN", "MOVIES_RECOMMENDER_ACTIVE_COLLABORATIVE_MODEL_VARIANT", "MOVIES_RECOMMENDER_BIASED_MATRIX_FACTORIZATION_MODEL_VARIANT", "BACKEND_PORT", "FRONTEND_PORT", "BACKEND_BIND_HOST", "FRONTEND_BIND_HOST")
ALGORITHMS = ("tfidf", "popularity", "item_knn", "user_knn", "biased")


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description="Manage the local Movies Recommender Docker installation.")
    subs = root.add_subparsers(dest="command")
    def common(p):
        p.add_argument("--dev", action="store_true", help="Use compose.dev.yaml and local source builds.")
        p.add_argument("--data-dir", type=Path)
        p.add_argument("--non-interactive", action="store_true")
    dataset = subs.add_parser("dataset", help="Generate an offline dataset")
    common(dataset); dataset.add_argument("--source", choices=("existing", "download", "zip")); dataset.add_argument("--zip-path", type=Path); dataset.add_argument("--preset", choices=("recommended", "defaults", "custom"), default="recommended"); dataset.add_argument("--cleanup", choices=("none", "standard", "minimal"), default="none"); dataset.add_argument("--skip-posters", action="store_true"); dataset.add_argument("--audit", action="store_true"); dataset.add_argument("--yes", action="store_true")
    deploy = subs.add_parser("deploy", help="Build recommenders and start the API")
    common(deploy); deploy.add_argument("--algorithms", default="all"); deploy.add_argument("--item-knn-variant"); deploy.add_argument("--bmf-variant"); clean = deploy.add_mutually_exclusive_group(); clean.add_argument("--clean", action="store_true"); clean.add_argument("--no-clean", action="store_true"); front = deploy.add_mutually_exclusive_group(); front.add_argument("--frontend", action="store_true"); front.add_argument("--no-frontend", action="store_true"); deploy.add_argument("--yes", action="store_true")
    for name in ("restart", "status", "stop"):
        p = subs.add_parser(name); common(p)
        if name == "restart": p.add_argument("--frontend", action="store_true")
    return root


def compose_args(dev: bool) -> list[str]:
    args = ["docker", "compose", "-f", "compose.yaml"]
    return args + (["-f", "compose.dev.yaml"] if dev else [])


def run(args: list[str], *, env: dict[str, str] | None = None) -> int:
    try: return subprocess.run(args, cwd=ROOT, env=env, shell=False).returncode
    except OSError as exc: print(f"Could not run Docker Compose: {exc}", file=sys.stderr); return 1


def absolute_path(path: Path) -> str:
    return Path(path).expanduser().resolve().as_posix()


def read_env() -> dict[str, str]:
    source = ENV_FILE if ENV_FILE.exists() else EXAMPLE_ENV
    values: dict[str, str] = {}
    for line in source.read_text(encoding="utf-8").splitlines() if source.exists() else []:
        if "=" in line and not line.lstrip().startswith("#"):
            key, value = line.split("=", 1); values[key] = value
    return values


def update_env(updates: dict[str, str]) -> None:
    if any("\n" in value or "\r" in value for value in updates.values()): raise ValueError("Environment values cannot contain line breaks.")
    original = ENV_FILE.read_text(encoding="utf-8").splitlines() if ENV_FILE.exists() else EXAMPLE_ENV.read_text(encoding="utf-8").splitlines()
    pending = dict(updates); lines = []
    for line in original:
        key = line.split("=", 1)[0] if "=" in line and not line.lstrip().startswith("#") else None
        lines.append(f"{key}={pending.pop(key)}" if key in pending else line)
    lines.extend(f"{key}={value}" for key, value in pending.items())
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=ENV_FILE.parent, delete=False) as file:
        file.write("\n".join(lines) + "\n"); temporary = Path(file.name)
    os.replace(temporary, ENV_FILE)


def validate_dataset(data_dir: Path) -> tuple[bool, str]:
    root = data_dir / "offline_dataset"; required = (root / "manifest.json", root / "csv" / "public_movies.csv", root / "csv" / "collaborative_support_movies.csv", root / "csv" / "collaborative_ratings.csv")
    missing = [str(p) for p in required if not p.is_file() or p.stat().st_size == 0]
    posters = root / "images" / "posters"
    if not posters.is_dir(): missing.append(str(posters))
    if missing: return False, "Missing required dataset paths: " + ", ".join(missing)
    return True, f"Dataset found\nPublic catalogue CSV: {required[1]}\nCollaborative ratings CSV: {required[3]}\nPoster count: {sum(1 for _ in posters.iterdir())}"


def configured_data_dir(args) -> Path:
    return Path(args.data_dir or read_env().get("DATA_DIR", ROOT / "Backend" / "data")).expanduser().resolve()


def ensure_docker(dev: bool) -> bool:
    return run(compose_args(dev) + ["config", "--quiet"]) == 0


def dataset(args) -> int:
    data = configured_data_dir(args); updates = {"DATA_DIR": absolute_path(data)}
    if not args.non_interactive and not read_env().get("MOVIES_RECOMMENDER_TMDB_BEARER_TOKEN"):
        token = getpass.getpass("TMDB bearer token (leave blank to use existing/no enrichment): ").strip()
        if token: updates["MOVIES_RECOMMENDER_TMDB_BEARER_TOKEN"] = token
    update_env(updates)
    if not ensure_docker(args.dev): return 1
    command = compose_args(args.dev) + ["--profile", "dataset", "run", "--rm", "dataset", "--non-interactive", "--source", args.source or "existing", "--preset", args.preset, "--cleanup", args.cleanup]
    if args.zip_path: command += ["--zip-path", str(args.zip_path)]
    if args.skip_posters: command.append("--skip-posters")
    if args.audit: command.append("--audit")
    if args.yes: command.append("--yes")
    code = run(command); print(f"Dataset location: {data / 'offline_dataset'}") if code == 0 else None; return code


def profiles(args) -> dict:
    command = compose_args(args.dev) + ["--profile", "maintenance", "run", "--rm", "recommender-build", "--list-profiles", "--format", "json"]
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, shell=False)
    if result.returncode: raise RuntimeError("Could not read recommender profile catalogue.")
    return json.loads(result.stdout)


def deploy(args) -> int:
    data = configured_data_dir(args); valid, message = validate_dataset(data)
    if not valid: print(message, file=sys.stderr); return 1
    print(message)
    if not ensure_docker(args.dev): return 1
    catalogue = profiles(args); item = args.item_knn_variant or next(p["variantId"] for p in catalogue["itemKnn"] if p["recommended"]); bmf = args.bmf_variant or catalogue["biasedMatrixFactorization"][0]["variantId"]
    selected = ALGORITHMS if args.algorithms == "all" else tuple(a for a in args.algorithms.split(",") if a in ALGORITHMS)
    if not selected: print("No valid algorithms selected.", file=sys.stderr); return 1
    update_env({"DATA_DIR": absolute_path(data), "MOVIES_RECOMMENDER_ACTIVE_COLLABORATIVE_MODEL_VARIANT": item, "MOVIES_RECOMMENDER_BIASED_MATRIX_FACTORIZATION_MODEL_VARIANT": bmf})
    command = compose_args(args.dev) + ["--profile", "maintenance", "run", "--rm", "recommender-build"]
    for algorithm in selected: command += ["--algorithm", algorithm]
    if not args.no_clean: command.append("--clean")
    command.append("--yes")
    if run(command): return 1
    if run(compose_args(args.dev) + ["up", "-d", "--force-recreate", "api"]): return 1
    if not wait_ready(read_env().get("BACKEND_PORT", "8014")): return 1
    if args.frontend and run(compose_args(args.dev) + ["--profile", "frontend", "up", "-d", "frontend"]): return 1
    return 0


def wait_ready(port: str) -> bool:
    latest = "no response"
    for _ in range(30):
        try:
            with urlopen(f"http://127.0.0.1:{port}/ready", timeout=1) as response:
                if response.status == 200: print("Backend is ready."); return True
                latest = f"HTTP {response.status}"
        except (URLError, OSError) as exc: latest = str(exc)
        time.sleep(1)
    print(f"Backend is not ready: {latest}. Run python manage.py status.", file=sys.stderr); return False


def main(argv=None) -> int:
    args = parser().parse_args(argv)
    if not args.command: parser().print_help(); return 0
    if args.command == "dataset": return dataset(args)
    if args.command == "deploy": return deploy(args)
    if args.command == "restart":
        return 0 if run(compose_args(args.dev) + ["restart", "api"]) == 0 and wait_ready(read_env().get("BACKEND_PORT", "8014")) else 1
    if args.command == "status":
        run(compose_args(args.dev) + ["ps"])
        for endpoint in ("health", "ready"):
            try:
                with urlopen(f"http://127.0.0.1:{read_env().get('BACKEND_PORT', '8014')}/{endpoint}", timeout=2) as response: print(f"/{endpoint}: HTTP {response.status}")
            except (URLError, OSError) as exc: print(f"/{endpoint}: unavailable ({exc})")
        return 0
    if args.command == "stop":
        code = run(compose_args(args.dev) + ["down"]); print("Persistent DATA_DIR contents were not deleted."); return code
    return 1


if __name__ == "__main__": raise SystemExit(main())
