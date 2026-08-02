"""Small cross-platform Docker Compose manager for Movies Recommender."""
from __future__ import annotations

import argparse
import hashlib
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
    for name in ("candidate-limit", "candidate-min-ratings", "candidate-min-year", "candidate-max-year", "candidate-min-tags", "max-tags-per-movie", "public-limit", "collaborative-core-limit", "catalog-min-ratings", "public-min-year", "collaborative-min-year"): dataset.add_argument("--" + name, type=int)
    for name, help_text in (("install", "Build recommender models and start the API"), ("rebuild-models", "Rebuild selected recommender models")):
        build = subs.add_parser(name, help=help_text)
        common(build); build.add_argument("--algorithms", default="all"); build.add_argument("--item-knn-variant"); build.add_argument("--bmf-variant"); clean = build.add_mutually_exclusive_group(); clean.add_argument("--clean", action="store_true"); clean.add_argument("--no-clean", action="store_true"); build.add_argument("--audit", action="store_true"); build.add_argument("--yes", action="store_true")
    for name, help_text in (("start", "Start the API using existing recommender artifacts"), ("deploy", "Alias for start")):
        start = subs.add_parser(name, help=help_text); common(start)
    audit = subs.add_parser("audit-models", help="Audit existing recommender artifacts without rebuilding")
    common(audit)
    for name in ("restart", "status", "stop"):
        p = subs.add_parser(name); common(p)
        if name == "restart": p.add_argument("--frontend", action="store_true")
    subs.add_parser("backend", help=argparse.SUPPRESS)
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
    return True, f"Dataset found\nPublic catalogue CSV: {required[1]}\nCollaborative ratings CSV: {required[3]}\nPoster count: {sum(1 for path in posters.iterdir() if path.is_file())}"


def configured_data_dir(args) -> Path:
    return Path(args.data_dir or read_env().get("DATA_DIR", ROOT / "Backend" / "data")).expanduser().resolve()


def ensure_docker(dev: bool) -> bool:
    return run(compose_args(dev) + ["config", "--quiet"]) == 0


def dataset(args) -> int:
    data = configured_data_dir(args); updates = {"DATA_DIR": absolute_path(data)}
    if args.source == "zip" and (not args.zip_path or not args.zip_path.is_file()): print("--source zip requires an existing regular --zip-path.", file=sys.stderr); return 1
    if args.source != "zip" and args.zip_path: print("--zip-path is only valid with --source zip.", file=sys.stderr); return 1
    if args.non_interactive and not args.source: print("--non-interactive dataset requires --source.", file=sys.stderr); return 1
    if args.non_interactive and not args.yes: print("--non-interactive dataset requires --yes.", file=sys.stderr); return 1
    if not args.non_interactive and not read_env().get("MOVIES_RECOMMENDER_TMDB_BEARER_TOKEN"):
        token = getpass.getpass("TMDB bearer token (leave blank to use existing/no enrichment): ").strip()
        if token: updates["MOVIES_RECOMMENDER_TMDB_BEARER_TOKEN"] = token
    update_env(updates)
    if not ensure_docker(args.dev): return 1
    command = compose_args(args.dev) + ["--profile", "dataset", "run", "--rm"]
    if args.source == "zip":
        command += ["--volume", f"{absolute_path(args.zip_path)}:/input/ml-32m.zip:ro"]
    command.append("dataset")
    if args.non_interactive: command += ["--non-interactive", "--source", args.source, "--preset", args.preset, "--cleanup", args.cleanup]
    elif args.cleanup != "none": command += ["--cleanup", args.cleanup]
    if args.source == "zip": command += ["--zip-path", "/input/ml-32m.zip"]
    if args.skip_posters: command.append("--skip-posters")
    if args.audit: command.append("--audit")
    for name in ("candidate_limit", "candidate_min_ratings", "candidate_min_year", "candidate_max_year", "candidate_min_tags", "max_tags_per_movie", "public_limit", "collaborative_core_limit", "catalog_min_ratings", "public_min_year", "collaborative_min_year"):
        value = getattr(args, name)
        if value is not None: command += ["--" + name.replace("_", "-"), str(value)]
    if args.yes: command.append("--yes")
    code = run(command); print(f"Dataset location: {data / 'offline_dataset'}") if code == 0 else None; return code


def profiles(args) -> dict:
    command = compose_args(args.dev) + ["--profile", "maintenance", "run", "--rm", "recommender-build", "--list-profiles", "--format", "json"]
    try: result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, shell=False)
    except OSError as exc: raise RuntimeError("Docker Compose is unavailable for profile discovery.") from exc
    if result.returncode or not result.stdout.strip(): raise RuntimeError("Could not read recommender profile catalogue.")
    try: payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc: raise RuntimeError("Recommender profile catalogue returned invalid JSON.") from exc
    if not isinstance(payload.get("itemKnn"), list) or not isinstance(payload.get("biasedMatrixFactorization"), list): raise RuntimeError("Recommender profile catalogue is missing expected profile groups.")
    return payload


def rebuild_models(args) -> int:
    data = configured_data_dir(args); update_env({"DATA_DIR": absolute_path(data)}); valid, message = validate_dataset(data)
    if not valid: print(message, file=sys.stderr); return 1
    print(message)
    if not ensure_docker(args.dev): return 1
    try: catalogue = profiles(args)
    except RuntimeError as exc: print(str(exc), file=sys.stderr); return 1
    item = args.item_knn_variant or next((p["variantId"] for p in catalogue["itemKnn"] if p.get("recommended")), None)
    bmf = args.bmf_variant or (catalogue["biasedMatrixFactorization"][0].get("variantId") if catalogue["biasedMatrixFactorization"] else None)
    clean_enabled = _resolve_clean(args, interactive=not args.non_interactive)
    if not args.non_interactive:
        item = _choose_profile("Select Item KNN variant", catalogue["itemKnn"], item)
        bmf = _choose_profile("Select BMF variant", catalogue["biasedMatrixFactorization"], bmf)
        raw_algorithms = input("Algorithms [all]: ").strip() or "all"
        args.algorithms = raw_algorithms
    requested = ALGORITHMS if args.algorithms == "all" else tuple(args.algorithms.split(","))
    if not requested or any(name not in ALGORITHMS for name in requested): print("Algorithms must be a non-empty comma-separated selection of supported names.", file=sys.stderr); return 1
    if item not in {p.get("variantId") for p in catalogue["itemKnn"]} or bmf not in {p.get("variantId") for p in catalogue["biasedMatrixFactorization"]}: print("Unsupported recommender variant.", file=sys.stderr); return 1
    selected = requested
    if args.non_interactive and not args.yes: print("--non-interactive deploy requires --yes.", file=sys.stderr); return 1
    _print_deploy_summary(data, selected, item, bmf, clean_enabled, False, args.dev)
    if not args.non_interactive and not _ask_yes_no("Build selected recommender models?", True): return 0
    update_env({"DATA_DIR": absolute_path(data), "MOVIES_RECOMMENDER_ACTIVE_COLLABORATIVE_MODEL_VARIANT": item, "MOVIES_RECOMMENDER_BIASED_MATRIX_FACTORIZATION_MODEL_VARIANT": bmf})
    command = compose_args(args.dev) + ["--profile", "maintenance", "run", "--rm", "recommender-build"]
    for algorithm in selected: command += ["--algorithm", algorithm]
    if clean_enabled: command.append("--clean")
    command.append("--yes")
    if run(command): return 1
    _write_model_dataset_state(data)
    if args.audit and audit_models(args): return 1
    if run(compose_args(args.dev) + ["up", "-d", "--force-recreate", "api"]): return 1
    if not wait_ready(read_env().get("BACKEND_PORT", "8014")): return 1
    return 0


def install(args) -> int:
    """Build only when required; otherwise explicitly choose reuse or rebuild."""
    data = configured_data_dir(args)
    update_env({"DATA_DIR": absolute_path(data)})
    valid, message = validate_dataset(data)
    if not valid: print(message, file=sys.stderr); return 1
    compatible, reason = validate_active_models(data)
    if compatible:
        if args.non_interactive or _ask_yes_no("Compatible recommender models exist. Reuse them?", True):
            return start_backend(args)
        if not _ask_yes_no("Rebuild recommender models?", False): return 0
    elif not args.non_interactive:
        print("Model construction is required: " + reason)
    return rebuild_models(args)


def start_backend(args) -> int:
    data = configured_data_dir(args); update_env({"DATA_DIR": absolute_path(data)})
    valid, message = validate_dataset(data)
    if not valid: print(message, file=sys.stderr); return 1
    compatible, reason = validate_active_models(data)
    if not compatible:
        print("Cannot start backend with existing recommender artifacts: " + reason, file=sys.stderr)
        print("Run `python manage.py rebuild-models` to construct compatible artifacts.", file=sys.stderr)
        return 1
    if not ensure_docker(args.dev): return 1
    if run(compose_args(args.dev) + ["up", "-d", "--force-recreate", "api"]): return 1
    return 0 if wait_ready(read_env().get("BACKEND_PORT", "8014")) else 1


def deploy(args) -> int:
    """Backward-compatible explicit alias for a non-rebuilding backend start."""
    return start_backend(args)


def audit_models(args) -> int:
    data = configured_data_dir(args); valid, message = validate_dataset(data)
    if not valid: print(message, file=sys.stderr); return 1
    compatible, reason = validate_active_models(data)
    if not compatible: print("Cannot audit incompatible recommender artifacts: " + reason, file=sys.stderr); return 1
    if not ensure_docker(args.dev): return 1
    command = compose_args(args.dev) + ["--profile", "maintenance", "run", "--rm", "recommender-audit"]
    return run(command)


def validate_active_models(data: Path) -> tuple[bool, str]:
    state = data / "recommender_models" / "dataset_compatibility.json"
    if not state.is_file(): return False, "model compatibility state is missing"
    try: payload = json.loads(state.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError): return False, "model compatibility state is unreadable"
    if payload.get("datasetFingerprint") != _dataset_fingerprint(data): return False, "model artifacts are stale for the current offline dataset"
    variants = read_env()
    required = (
        data / "recommender_models" / "content_based" / "content_feature_metadata.json",
        data / "recommender_models" / "collaborative" / "popularity_baseline" / "default" / "model_manifest.json",
        data / "recommender_models" / "collaborative" / "item_knn_cosine" / variants.get("MOVIES_RECOMMENDER_ACTIVE_COLLABORATIVE_MODEL_VARIANT", "top_k_100_min_support_25") / "model_manifest.json",
        data / "recommender_models" / "collaborative" / "user_knn_pearson_shrinkage" / "default" / "model_manifest.json",
        data / "recommender_models" / "collaborative" / "biased_matrix_factorization" / variants.get("MOVIES_RECOMMENDER_BIASED_MATRIX_FACTORIZATION_MODEL_VARIANT", "factors_128_epochs_100_lr_0_005_reg_0_02") / "model_manifest.json",
    )
    missing = [str(path) for path in required if not path.is_file() or path.stat().st_size == 0]
    return (False, "required active artifacts are missing: " + ", ".join(missing)) if missing else (True, "compatible")


def _dataset_fingerprint(data: Path) -> str:
    dataset = data / "offline_dataset"
    digest = hashlib.sha256()
    for path in (dataset / "manifest.json", dataset / "csv" / "public_movies.csv", dataset / "csv" / "collaborative_support_movies.csv", dataset / "csv" / "collaborative_ratings.csv"):
        with path.open("rb") as file:
            for block in iter(lambda: file.read(1024 * 1024), b""): digest.update(block)
    return digest.hexdigest()


def _write_model_dataset_state(data: Path) -> None:
    state = data / "recommender_models" / "dataset_compatibility.json"; state.parent.mkdir(parents=True, exist_ok=True)
    state.write_text(json.dumps({"datasetFingerprint": _dataset_fingerprint(data), "datasetManifest": "offline_dataset/manifest.json"}, indent=2) + "\n", encoding="utf-8")


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
    if not args.command: return menu()
    if args.command == "backend": return backend_management()
    if args.command == "dataset": return dataset(args)
    if args.command == "install": return install(args)
    if args.command == "rebuild-models": return rebuild_models(args)
    if args.command in {"start", "deploy"}: return start_backend(args)
    if args.command == "audit-models": return audit_models(args)
    if args.command == "restart":
        if run(compose_args(args.dev) + ["restart", "api"]) or not wait_ready(read_env().get("BACKEND_PORT", "8014")): return 1
        if args.frontend:
            if run(compose_args(args.dev) + ["restart", "frontend"]): return 1
            print("Frontend: http://127.0.0.1:" + read_env().get("FRONTEND_PORT", "5173"))
        return 0
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


def backend_management() -> int:
    print("Backend management\n\n1. Install backend\n   Builds recommender models and starts the API.\n\n2. Start or update backend\n   Starts the API using existing compatible model artifacts.\n\n3. Rebuild recommender models\n   Rebuilds selected models and reloads the API.\n\n4. Generate recommender audit\n   Audits existing model artifacts without rebuilding them.\n\n5. Restart backend\n   Restarts the running API container.\n\n0. Back")
    try: choice = input("Select an option: ").strip()
    except (EOFError, KeyboardInterrupt): return 0
    command = {"1": "install", "2": "start", "3": "rebuild-models", "4": "audit-models", "5": "restart"}.get(choice)
    return 0 if choice == "0" else main([command]) if command else 1


def _ask_yes_no(question: str, default: bool) -> bool:
    try: value = input(f"{question} [{'Y/n' if default else 'y/N'}] ").strip().lower()
    except (EOFError, KeyboardInterrupt): return False
    return default if not value else value in {"y", "yes"}


def _resolve_clean(args, *, interactive: bool) -> bool:
    if args.clean:
        return True
    if args.no_clean:
        return False
    return _ask_yes_no("Remove optional recommender exports?", True) if interactive else True


def _print_deploy_summary(data: Path, selected: tuple[str, ...], item: str | None, bmf: str | None, clean: bool, frontend: bool, dev: bool) -> None:
    print("\nDeployment summary")
    print(f"Data directory: {data}")
    print("Selected algorithms: " + ", ".join(selected))
    print(f"Item KNN variant: {item}\nBMF variant: {bmf}")
    print(f"Remove optional exports: {'yes' if clean else 'no'}")
    print(f"Start frontend: {'yes' if frontend else 'no'}")
    print(f"Compose mode: {'development' if dev else 'deployment'}")


def _choose_profile(title: str, values: list[dict], default: str | None) -> str | None:
    print(title)
    for index, value in enumerate(values, start=1): print(f"{index}. {value.get('label', value.get('variantId'))}" + (" [recommended]" if value.get("recommended") else ""))
    try: choice = input(f"Choice [{default}]: ").strip()
    except (EOFError, KeyboardInterrupt): return default
    return values[int(choice) - 1].get("variantId") if choice.isdigit() and 1 <= int(choice) <= len(values) else default


def menu() -> int:
    print("Movies Recommender\n\n1. Generate or update dataset\n2. Backend management\n3. Restart services\n4. Show status\n5. Stop services\n0. Exit")
    try: choice = input("Select an option: ").strip()
    except (EOFError, KeyboardInterrupt): print("Cancelled."); return 0
    mapping = {"1": "dataset", "2": "backend", "3": "restart", "4": "status", "5": "stop"}
    return 0 if choice == "0" else main([mapping[choice]]) if choice in mapping else 1


if __name__ == "__main__": raise SystemExit(main())
