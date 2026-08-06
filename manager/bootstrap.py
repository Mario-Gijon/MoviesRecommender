"""First-run configuration for the self-contained deployment manager."""

from __future__ import annotations

import os
from pathlib import Path
import re
import tempfile

from manager.config import DEFAULT_BIASED_VARIANT, DEFAULT_ITEM_KNN_VARIANT
from manager.console import Console


_PROJECT_NAME = re.compile(r"^[a-z0-9][a-z0-9_-]*$")
_SAFE_VALUE = re.compile(r"^[^\s#'\"$`\\\\]+$")


def bootstrap_deployment(root: Path, console: Console) -> bool:
    """Create .env once.  False means the user cancelled or setup failed."""
    env_file = root / ".env"
    if env_file.exists():
        return True
    print("No se ha encontrado el archivo .env.")
    print("Vamos a configurar la instalación.")
    project = _ask_project(console)
    if project is None:
        return False
    data_dir = _ask_data_dir(root, console)
    if data_dir is None:
        return False
    backend_port = _ask_port(console, "Puerto del Backend", "18014")
    if backend_port is None:
        return False
    frontend_port = _ask_port(console, "Puerto del Frontend", "15173", forbidden=backend_port)
    if frontend_port is None:
        return False
    host = _ask_access_mode(console)
    if host is None:
        return False
    token = _ask_value(console, "Token bearer de TMDB (opcional, pulsa Intro para omitirlo)", "", allow_empty=True)
    if token is None:
        return False
    values = {
        "COMPOSE_PROJECT_NAME": project,
        "DATA_DIR": _data_value(root, data_dir),
        "BACKEND_PORT": backend_port,
        "FRONTEND_PORT": frontend_port,
        "BACKEND_BIND_HOST": host,
        "FRONTEND_BIND_HOST": host,
        "MOVIES_RECOMMENDER_TMDB_BEARER_TOKEN": token,
        "MOVIES_RECOMMENDER_ACTIVE_COLLABORATIVE_MODEL_VARIANT": DEFAULT_ITEM_KNN_VARIANT,
        "MOVIES_RECOMMENDER_BIASED_MATRIX_FACTORIZATION_MODEL_VARIANT": DEFAULT_BIASED_VARIANT,
    }
    print("\nResumen de la configuración")
    for key, value in values.items():
        if key == "MOVIES_RECOMMENDER_TMDB_BEARER_TOKEN":
            print(f"{key}: {'configurado' if value else 'no configurado'}")
        else:
            print(f"{key}: {value}")
    print("El token solo es necesario para el enriquecimiento de TMDB.")
    if not console.confirm("¿Guardar esta configuración?"):
        print("Configuración inicial cancelada.")
        return False
    try:
        _ensure_writable_directory(data_dir)
        _write_env_once(env_file, values)
    except OSError as exc:
        print(f"No se pudo preparar la instalación: {exc}")
        return False
    print("Configuración inicial guardada.")
    return True


def _read(console: Console, prompt: str) -> str | None:
    try:
        return input(f"{prompt}: ").strip()
    except (EOFError, KeyboardInterrupt):
        print("\nOperación cancelada.")
        return None


def _ask_value(console: Console, prompt: str, default: str, *, allow_empty: bool = False) -> str | None:
    while True:
        value = _read(console, f"{prompt} [{default}]" if default else prompt)
        if value is None:
            return None
        value = value or default
        if not value and allow_empty:
            return ""
        if _SAFE_VALUE.fullmatch(value):
            return value
        print("El valor contiene caracteres no compatibles con el archivo .env.")


def _ask_project(console: Console) -> str | None:
    while True:
        value = _ask_value(console, "Nombre del proyecto de Compose", "movies-recommender")
        if value is None or _PROJECT_NAME.fullmatch(value):
            return value
        print("El nombre debe empezar por letra o número minúsculo y usar solo minúsculas, números, guiones o guiones bajos.")


def _ask_data_dir(root: Path, console: Console) -> Path | None:
    while True:
        value = _read(console, "Directorio de datos [./data]")
        if value is None:
            return None
        value = value or "./data"
        if any(character in value for character in ("\n", "\r", "\x00", "#", "$", "'", '\"', "`")):
            print("La ruta contiene caracteres no compatibles con el archivo .env.")
            continue
        candidate = Path(value).expanduser()
        if not candidate.is_absolute() and value != "./data":
            print("Usa ./data o una ruta absoluta para el directorio de datos.")
            continue
        return (candidate if candidate.is_absolute() else root / candidate).resolve()


def _ask_port(console: Console, prompt: str, default: str, *, forbidden: str | None = None) -> str | None:
    while True:
        value = _ask_value(console, prompt, default)
        if value is None:
            return None
        if value.isdigit() and 1 <= int(value) <= 65535:
            if value != forbidden:
                return value
            print("El puerto del Frontend debe ser distinto del puerto del Backend.")
        else:
            print("Introduce un puerto entre 1 y 65535.")


def _ask_access_mode(console: Console) -> str | None:
    print("Acceso de red:\n1. Solo este equipo\n2. Otros equipos de la red")
    while True:
        value = _read(console, "Selecciona una opción")
        if value is None:
            return None
        if value == "1":
            return "127.0.0.1"
        if value == "2":
            return "0.0.0.0"
        print("Opción no válida.")


def _data_value(root: Path, data_dir: Path) -> str:
    try:
        return "./" + data_dir.relative_to(root).as_posix()
    except ValueError:
        return str(data_dir)


def _ensure_writable_directory(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    if not path.is_dir():
        raise OSError(f"{path} no es un directorio")
    with tempfile.NamedTemporaryFile(dir=path, prefix=".movies-recommender-", delete=True):
        pass


def _write_env_once(env_file: Path, values: dict[str, str]) -> None:
    if env_file.exists():
        raise FileExistsError("ya existe .env; no se ha modificado")
    content = "\n".join(f"{key}={value}" for key, value in values.items()) + "\n"
    descriptor, temporary_name = tempfile.mkstemp(prefix=".env-", dir=env_file.parent, text=True)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as file:
            file.write(content)
            file.flush()
            os.fsync(file.fileno())
        os.chmod(temporary, 0o600)
        try:
            os.link(temporary, env_file)
        except FileExistsError:
            raise FileExistsError("ya existe .env; no se ha modificado")
    finally:
        temporary.unlink(missing_ok=True)
