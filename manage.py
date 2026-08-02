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
from types import SimpleNamespace
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
    for name, help_text in (("install", "Build recommender models and start the API"), ("rebuild-models", "Rebuild selected recommender models"), ("backend-install", "Build recommender models and start the API")):
        build = subs.add_parser(name, help=help_text)
        common(build); build.add_argument("--algorithms", default="all"); build.add_argument("--item-knn-variant"); build.add_argument("--bmf-variant"); clean = build.add_mutually_exclusive_group(); clean.add_argument("--clean", action="store_true"); clean.add_argument("--no-clean", action="store_true"); build.add_argument("--audit", action="store_true"); build.add_argument("--yes", action="store_true")
    for name, help_text in (("start", "Start the API using existing recommender artifacts"), ("deploy", "Alias for start"), ("backend-start", "Start only the API using existing artifacts")):
        start = subs.add_parser(name, help=help_text); common(start)
    start_all = subs.add_parser("start-all", help="Explicitly start the API and optional frontend")
    common(start_all)
    audit = subs.add_parser("audit-models", help="Audit existing recommender artifacts without rebuilding")
    common(audit)
    for name in ("restart", "status", "stop", "backend-restart", "backend-stop", "frontend-install", "frontend-start", "frontend-restart", "frontend-stop", "frontend-status"):
        p = subs.add_parser(name); common(p)
    subs.add_parser("dev", help="Start the local development API and frontend")
    subs.add_parser("dev-stop", help="Stop the local development API and frontend")
    subs.add_parser("dev-status", help="Show local development service status")
    dev_logs = subs.add_parser("dev-logs", help="Follow local development logs")
    dev_logs.add_argument("service", nargs="?", choices=("api", "frontend"))
    dev_rebuild = subs.add_parser("dev-rebuild", help="Rebuild a development service after dependency changes")
    dev_rebuild.add_argument("service", choices=("frontend", "backend", "all"))
    subs.add_parser("backend", help=argparse.SUPPRESS); subs.add_parser("frontend", help=argparse.SUPPRESS)
    return root


def compose_args(dev: bool) -> list[str]:
    if dev:
        return ["docker", "compose", "-p", "movies-recommender-dev", "-f", "compose.dev.yaml"]
    return ["docker", "compose", "-p", "movies-recommender-local", "-f", "compose.yaml"]


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
    configured = Path(args.data_dir or read_env().get("DATA_DIR", "./data")).expanduser()
    return (configured if configured.is_absolute() else ROOT / configured).resolve()


def configured_data_env_value(args, data: Path) -> str:
    """Keep deployment-relative DATA_DIR stable unless an external path was supplied."""
    if args.data_dir is not None:
        return absolute_path(data)
    return read_env().get("DATA_DIR", "./data")


def ensure_docker(dev: bool) -> bool:
    return run(compose_args(dev) + ["config", "--quiet"]) == 0


def dev(args) -> int:
    """Start the isolated source-mounted development project."""
    if not ensure_docker(True):
        return 1
    if run(compose_args(True) + ["up", "-d", "api", "frontend"]):
        print("Could not start development services. If a configured port is in use, stop the conflicting published service first.", file=sys.stderr)
        return 1
    ready = wait_ready(read_env().get("BACKEND_PORT", "18014"))
    if not ready:
        print("The development frontend remains running; inspect `python manage.py dev-logs api`.", file=sys.stderr)
        return 1
    print("\nDevelopment environment started")
    print("Frontend: " + _configured_url("FRONTEND_BIND_HOST", "FRONTEND_PORT", "5173"))
    print("Backend:  " + _configured_url("BACKEND_BIND_HOST", "BACKEND_PORT", "18014"))
    print("\nFrontend source changes use Vite HMR.")
    print("Backend source changes use Uvicorn reload.")
    print("No restart is required for normal code changes.")
    return 0


def dev_stop(args) -> int:
    code = run(compose_args(True) + ["stop", "api", "frontend"])
    if code == 0:
        print("Development API and frontend stopped. Persistent data and dependency volumes were preserved.")
    return code


def dev_status(args) -> int:
    run(compose_args(True) + ["ps", "api", "frontend"])
    api_running = service_is_running(SimpleNamespace(dev=True), "api")
    frontend_running = service_is_running(SimpleNamespace(dev=True), "frontend")
    api_ready = api_running and wait_ready(read_env().get("BACKEND_PORT", "18014"))
    print("Development API: " + ("running" if api_ready else "stopped / unhealthy"))
    print("Development frontend: " + ("running" if frontend_running else "stopped"))
    print("Frontend URL: " + _configured_url("FRONTEND_BIND_HOST", "FRONTEND_PORT", "5173"))
    print("Backend URL: " + _configured_url("BACKEND_BIND_HOST", "BACKEND_PORT", "18014"))
    return 0


def dev_logs(args) -> int:
    command = compose_args(True) + ["logs", "--follow"]
    if args.service:
        command.append(args.service)
    return run(command)


def dev_rebuild(args) -> int:
    services = ("api", "frontend") if args.service == "all" else (("api",) if args.service == "backend" else ("frontend",))
    if not ensure_docker(True):
        return 1
    for service in services:
        if run(compose_args(True) + ["build", service]):
            return 1
        if run(compose_args(True) + ["up", "-d", "--force-recreate", service]):
            return 1
    return 0


def dataset(args) -> int:
    data = configured_data_dir(args); updates = {"DATA_DIR": configured_data_env_value(args, data)}
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
    data = configured_data_dir(args); update_env({"DATA_DIR": configured_data_env_value(args, data)}); valid, message = validate_dataset(data)
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
    update_env({"DATA_DIR": configured_data_env_value(args, data), "MOVIES_RECOMMENDER_ACTIVE_COLLABORATIVE_MODEL_VARIANT": item, "MOVIES_RECOMMENDER_BIASED_MATRIX_FACTORIZATION_MODEL_VARIANT": bmf})
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
    update_env({"DATA_DIR": configured_data_env_value(args, data)})
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
    data = configured_data_dir(args); update_env({"DATA_DIR": configured_data_env_value(args, data)})
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


def start_all(args) -> int:
    if start_backend(args): return 1
    return frontend_start(args, pull=False)


def frontend_install(args) -> int:
    if not ensure_docker(args.dev): return 1
    if run(compose_args(args.dev) + ["--profile", "frontend", "pull", "frontend"]): return 1
    return frontend_start(args, pull=False)


def frontend_start(args, *, pull: bool = False) -> int:
    if not ensure_docker(args.dev): return 1
    if pull and run(compose_args(args.dev) + ["--profile", "frontend", "pull", "frontend"]): return 1
    return run(compose_args(args.dev) + ["--profile", "frontend", "up", "-d", "frontend"])


def frontend_restart(args) -> int:
    return run(compose_args(args.dev) + ["--profile", "frontend", "restart", "frontend"])


def frontend_stop(args) -> int:
    return run(compose_args(args.dev) + ["--profile", "frontend", "stop", "frontend"])


def backend_restart(args) -> int:
    if run(compose_args(args.dev) + ["restart", "api"]): return 1
    return 0 if wait_ready(read_env().get("BACKEND_PORT", "18014")) else 1


def backend_stop(args) -> int:
    return run(compose_args(args.dev) + ["stop", "api"])


def service_is_installed(args, service: str) -> bool:
    command = compose_args(args.dev) + (["--profile", "frontend"] if service == "frontend" else []) + ["ps", "-q", "--all", service]
    try:
        result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, shell=False)
    except OSError:
        return False
    return result.returncode == 0 and bool(result.stdout.strip())


def service_is_running(args, service: str) -> bool:
    command = compose_args(args.dev) + (["--profile", "frontend"] if service == "frontend" else []) + ["ps", "-q", service]
    try:
        result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, shell=False)
    except OSError:
        return False
    return result.returncode == 0 and bool(result.stdout.strip())


def restart_installed_services(args) -> int:
    api = service_is_installed(args, "api"); frontend = service_is_installed(args, "frontend")
    if not api and not frontend:
        print("No installed services were found. Start the backend or frontend explicitly.")
        return 0
    if api and backend_restart(args): return 1
    if frontend and frontend_restart(args): return 1
    return 0


def stop_installed_services(args) -> int:
    if not service_is_installed(args, "api") and not service_is_installed(args, "frontend"):
        print("No installed services were found.")
        return 0
    code = run(compose_args(args.dev) + ["--profile", "frontend", "down", "--remove-orphans"])
    if code == 0: print("Persistent DATA_DIR contents were not deleted.")
    return code


def _configured_url(host_key: str, port_key: str, default_port: str) -> str:
    values = read_env(); host = values.get(host_key, "127.0.0.1"); port = values.get(port_key, default_port)
    shown_host = "127.0.0.1" if host == "0.0.0.0" else host
    suffix = " (externally bound)" if host == "0.0.0.0" else ""
    return f"http://{shown_host}:{port}{suffix}"


def frontend_status(args) -> int:
    installed = service_is_installed(args, "frontend")
    api_ready = wait_ready(read_env().get("BACKEND_PORT", "18014"))
    print("Frontend: " + ("running" if installed else "not installed"))
    print("Frontend URL: " + _configured_url("FRONTEND_BIND_HOST", "FRONTEND_PORT", "15173"))
    print("API connectivity: " + ("ready" if api_ready else "unavailable"))
    return 0


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
    return dispatch(args)


def dispatch(args) -> int:
    if not args.command: return menu()
    if getattr(args, "dev", False):
        print("--dev is deprecated; use `python manage.py dev` for normal local development.", file=sys.stderr)
    if args.command == "dev": return dev(args)
    if args.command == "dev-stop": return dev_stop(args)
    if args.command == "dev-status": return dev_status(args)
    if args.command == "dev-logs": return dev_logs(args)
    if args.command == "dev-rebuild": return dev_rebuild(args)
    if args.command == "backend": return backend_management()
    if args.command == "frontend": return frontend_management()
    if args.command == "dataset": return dataset(args)
    if args.command in {"install", "backend-install"}: return install(args)
    if args.command == "rebuild-models": return rebuild_models(args)
    if args.command in {"start", "deploy", "backend-start"}: return start_backend(args)
    if args.command == "start-all": return start_all(args)
    if args.command == "audit-models": return audit_models(args)
    if args.command in {"restart"}: return restart_installed_services(args)
    if args.command == "backend-restart": return backend_restart(args)
    if args.command == "backend-stop": return backend_stop(args)
    if args.command == "frontend-install": return frontend_install(args)
    if args.command == "frontend-start": return frontend_start(args)
    if args.command == "frontend-restart": return frontend_restart(args)
    if args.command == "frontend-stop": return frontend_stop(args)
    if args.command == "frontend-status": return frontend_status(args)
    if args.command == "status":
        run(compose_args(args.dev) + ["ps"])
        data = configured_data_dir(args); dataset_ok, _ = validate_dataset(data); models_ok, _ = validate_active_models(data) if dataset_ok else (False, "dataset missing")
        print("Dataset:   " + ("ready" if dataset_ok else "missing / invalid"))
        print("Models:    " + ("ready" if models_ok else "missing / incompatible"))
        print("API:       " + ("running" if service_is_installed(args, "api") and wait_ready(read_env().get("BACKEND_PORT", "18014")) else "stopped / unhealthy"))
        print("API URL: " + _configured_url("BACKEND_BIND_HOST", "BACKEND_PORT", "18014"))
        print("Frontend:  " + ("running" if service_is_installed(args, "frontend") else "not installed"))
        print("Frontend URL: " + _configured_url("FRONTEND_BIND_HOST", "FRONTEND_PORT", "15173"))
        return 0
    if args.command == "stop": return stop_installed_services(args)
    return 1


def backend_management() -> int:
    print("Backend management\n\n1. Install backend\n   Builds recommender models and starts only the API.\n\n2. Start or update backend\n   Starts only the API using existing compatible model artifacts.\n\n3. Rebuild recommender models\n   Rebuilds selected models and reloads only the API.\n\n4. Generate recommender audit\n   Audits existing model artifacts without rebuilding them.\n\n5. Restart backend\n   Restarts only the API container.\n\n6. Stop backend\n   Stops only the API container.\n\n0. Back")
    try: choice = input("Select an option: ").strip()
    except (EOFError, KeyboardInterrupt): return 0
    command = {"1": "backend-install", "2": "backend-start", "3": "rebuild-models", "4": "audit-models", "5": "backend-restart", "6": "backend-stop"}.get(choice)
    return 0 if choice == "0" else dispatch(parser().parse_args([command])) if command else 1


def frontend_management() -> int:
    print("Frontend management\n\n1. Install frontend\n   Pulls and starts the published frontend.\n\n2. Start frontend\n   Starts the published frontend service.\n\n3. Restart frontend\n   Restarts only the published frontend container.\n\n4. Stop frontend\n   Stops only the published frontend container.\n\n5. Show frontend status\n   Shows container state and configured URL.\n\n0. Back")
    try: choice = input("Select an option: ").strip()
    except (EOFError, KeyboardInterrupt): return 0
    command = {"1": "frontend-install", "2": "frontend-start", "3": "frontend-restart", "4": "frontend-stop", "5": "frontend-status"}.get(choice)
    return 0 if choice == "0" else dispatch(parser().parse_args([command])) if command else 1


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
    mapping = {"1": "dataset", "2": "backend", "3": "frontend"}
    while True:
        print("Movies Recommender\n\n1. Generate or update dataset\n2. Backend management\n3. Frontend management\n0. Exit")
        try: choice = input("Select an option: ").strip()
        except (EOFError, KeyboardInterrupt): print("Cancelled."); return 0
        if choice == "0": return 0
        if choice in mapping:
            dispatch(parser().parse_args([mapping[choice]]))
            continue
        print("Invalid option.", file=sys.stderr)


if __name__ == "__main__": raise SystemExit(main())
