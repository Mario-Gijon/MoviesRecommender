"""Interactive dataset operations backed exclusively by the dataset container."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path

from manager.compose import DEVELOPMENT, PRODUCTION, DockerCompose, Environment
from manager.config import Configuration
from manager.console import Console
from manager.models import dataset_fingerprint, validate_dataset
from manager.runtime import Runtime


STAGES = ("candidates", "enrich", "catalog", "ratings", "export", "posters", "audit")
RECOMMENDED_VALUES = {
    "candidate_limit": 15000, "candidate_min_ratings": 100, "candidate_min_year": 1990,
    "candidate_max_year": None, "candidate_min_tags": 0, "max_tags_per_movie": 35,
    "public_limit": None, "collaborative_core_limit": 15000, "catalog_min_ratings": 100,
    "public_min_year": 2000, "collaborative_min_year": 1990, "display_language": "es-ES",
    "public_audience_policy": "family_and_teen",
}
POLICIES = ("family_only", "family_and_teen", "all_classified")
POLICY_LABELS = {"family_only": "Solo público familiar", "family_and_teen": "Público familiar y adolescente", "all_classified": "Todas las categorías clasificadas"}
CONFIG_LABELS = {
    "candidate_limit": "Máximo de películas candidatas",
    "candidate_min_ratings": "Mínimo de valoraciones por película candidata",
    "candidate_min_year": "Año mínimo de las películas candidatas",
    "candidate_max_year": "Año máximo de las películas candidatas",
    "candidate_min_tags": "Mínimo de etiquetas distintas",
    "max_tags_per_movie": "Máximo de etiquetas por película",
    "public_limit": "Límite de películas públicas",
    "collaborative_core_limit": "Límite del núcleo colaborativo",
    "catalog_min_ratings": "Mínimo de valoraciones del catálogo",
    "public_min_year": "Año mínimo del catálogo público",
    "collaborative_min_year": "Año mínimo del catálogo colaborativo",
    "display_language": "Idioma de visualización",
}


@dataclass(frozen=True)
class DatasetOptions:
    candidate_limit: int = 15000
    candidate_min_ratings: int = 100
    candidate_min_year: int = 1990
    candidate_max_year: int | None = None
    candidate_min_tags: int = 0
    max_tags_per_movie: int = 35
    public_limit: int | None = None
    collaborative_core_limit: int = 15000
    catalog_min_ratings: int = 100
    public_min_year: int = 2000
    collaborative_min_year: int = 1990
    display_language: str = "es-ES"
    public_audience_policy: str = "family_and_teen"


class DatasetManager:
    def __init__(self, configuration: Configuration, runtime: Runtime, console: Console) -> None:
        self.configuration, self.runtime, self.console = configuration, runtime, console

    @property
    def data_dir(self) -> Path:
        return self.configuration.data_dir

    @property
    def log_path(self) -> Path:
        return self.data_dir / "logs" / "dataset-last-run.log"

    def menu(self) -> None:
        actions = {"1": "Generar o reconstruir dataset offline", "2": "Reconfigurar dataset offline existente", "3": "Validar dataset offline", "4": "Ver información del dataset", "5": "Limpiar archivos temporales", "0": "Volver"}
        while True:
            choice = self.console.menu("Dataset", actions)
            if choice in {None, "0"}: return
            if choice == "1": self.generate_menu()
            elif choice == "2": self.reconfigure()
            elif choice == "3": self.validate()
            elif choice == "4": self.show_information()
            else: self.cleanup()

    def _implementation(self) -> tuple[Environment, str] | None:
        if self.runtime.packaged:
            return PRODUCTION, "Imagen publicada"
        choice = self.console.menu("Implementación del generador", {"1": "Código local", "2": "Imagen publicada", "0": "Volver"})
        if choice in {None, "0"}: return None
        return (DEVELOPMENT, "Código local") if choice == "1" else (PRODUCTION, "Imagen publicada")

    def generate_menu(self) -> None:
        choice = self.console.menu("Generar o reconstruir dataset offline", {"1": "Generar un dataset nuevo", "2": "Reconstruir usando datos existentes", "3": "Reanudar una generación interrumpida", "0": "Volver"})
        if choice in {None, "0"}: return
        implementation = self._implementation()
        if implementation is None: return
        source = self._source() if choice in {"1", "2"} else "existing"
        if source is None: return
        if choice == "1" and (self.data_dir / "offline_dataset" / "manifest.json").exists() and not self.console.confirm("Ya existe un dataset final. ¿Reemplazarlo sin crear copia de seguridad?"):
            return
        if source == "existing" and not self._has_extracted_source():
            print("No se han encontrado los archivos extraídos obligatorios de MovieLens en DATA_DIR.")
            return
        options = self._configuration()
        if options is None: return
        start_at = "candidates" if choice == "1" else (self._resume_point() if choice == "3" else "candidates")
        if choice == "3":
            print(f"Punto de continuación detectado: {start_at}")
        if self._includes(start_at, "enrich") and not self._has_tmdb_token():
            print("El enriquecimiento de TMDB requiere un token configurado en .env.")
            return
        tmdb = self._tmdb_behavior(start_at)
        if tmdb is None: return
        posters = self.console.confirm("¿Descargar los pósteres que falten?") if self._includes(start_at, "posters") else False
        audit = self.console.confirm("¿Ejecutar la auditoría del dataset?")
        cleanup = self.console.confirm("¿Limpiar los archivos temporales tras una ejecución correcta?")
        zip_path = self._zip_path() if source == "zip" else None
        if source == "zip" and zip_path is None: return
        command = self._generation_command(source, options, start_at, tmdb, posters, audit, cleanup, zip_path)
        self._execute(implementation, command, "generación" if choice == "1" else "reconstrucción", source, options, start_at, zip_path)

    def _source(self) -> str | None:
        choice = self.console.menu("Origen de los datos de MovieLens", {"1": "Descargar MovieLens automáticamente", "2": "Usar archivos de MovieLens ya extraídos", "3": "Usar un archivo ZIP de MovieLens", "0": "Volver"})
        return {"1": "download", "2": "existing", "3": "zip"}.get(choice)

    def _configuration(self) -> DatasetOptions | None:
        mode = self.console.menu("Configuración del dataset", {"1": "Recomendada", "2": "Personalizada", "3": "Avanzada", "0": "Volver"})
        if mode in {None, "0"}: return None
        values = dict(RECOMMENDED_VALUES)
        if mode == "2":
            for key, label, none in (("candidate_limit", "Máximo de películas a procesar", False), ("candidate_min_ratings", "Mínimo de valoraciones por película", False), ("candidate_min_year", "Año mínimo de estreno", False), ("candidate_max_year", "Año máximo", True), ("candidate_min_tags", "Mínimo de etiquetas distintas", False)):
                value = self._number(label, values[key], optional=none, zero=key == "candidate_min_tags")
                if value is None and not none: return None
                values[key] = value
            policy = self._policy()
            if policy is None: return None
            values["public_audience_policy"] = policy
            values["catalog_min_ratings"] = values["candidate_min_ratings"]
            values["public_min_year"] = values["candidate_min_year"]
            values["collaborative_min_year"] = values["candidate_min_year"]
        elif mode == "3":
            for key in RECOMMENDED_VALUES:
                if key in {"display_language", "public_audience_policy"}: continue
                value = self._number(key.replace("_", " "), values[key], optional=key in {"candidate_max_year", "public_limit"}, zero=key == "candidate_min_tags")
                if value is None and key not in {"candidate_max_year", "public_limit"}: return None
                values[key] = value
            language = self._text("Idioma de visualización", values["display_language"])
            if language is None: return None
            values["display_language"] = language
            policy = self._policy()
            if policy is None: return None
            values["public_audience_policy"] = policy
        options = DatasetOptions(**values)
        if not self._valid_options(options): return None
        self._print_configuration_summary(options)
        print("Reglas fijas: duración pública mínima 70 minutos; documentales y audiencia desconocida excluidos.")
        return options

    def _policy(self) -> str | None:
        choice = self.console.menu("Política de audiencia", {"1": POLICY_LABELS["family_only"], "2": POLICY_LABELS["family_and_teen"], "3": POLICY_LABELS["all_classified"], "0": "Volver"})
        return {"1": "family_only", "2": "family_and_teen", "3": "all_classified"}.get(choice)

    def _generation_command(self, source: str, options: DatasetOptions, start: str, tmdb: str, posters: bool, audit: bool, cleanup: bool, zip_path: Path | None) -> list[str]:
        command = ["run", "--rm"]
        if zip_path: command += ["-v", f"{zip_path}:/input/ml-32m.zip:ro"]
        command += ["dataset", "--non-interactive", "--yes", "--action", "generate", "--source", source, "--start-at", start, "--preset", "recommended"]
        if zip_path: command += ["--zip-path", "/input/ml-32m.zip"]
        for key, value in asdict(options).items():
            if key == "public_audience_policy": continue
            if value is not None: command += ["--" + key.replace("_", "-"), str(value)]
        command += ["--resume-tmdb" if tmdb == "reuse" else "--force-tmdb"]
        if not posters: command.append("--skip-posters")
        if audit: command.append("--audit")
        command += ["--cleanup", "standard" if cleanup else "none"]
        return command

    def _execute(self, implementation: tuple[Environment, str], command: list[str], operation: str, source: str, options: DatasetOptions, start: str, zip_path: Path | None = None) -> int:
        environment, label = implementation
        print(f"\nResumen: {operation}; implementación: {label}; origen: {source}; DATA_DIR: {self.data_dir}; etapas: {', '.join(STAGES[STAGES.index(start):])}")
        if zip_path: print(f"ZIP: {zip_path}")
        print(f"Audiencia: {POLICY_LABELS[options.public_audience_policy]}")
        if not self.console.confirm("¿Iniciar la operación?"): return 0
        compose = DockerCompose(self.configuration, environment)
        before = self._fingerprint()
        if environment is PRODUCTION and compose.run(["pull", "dataset"], profiles=("dataset",)):
            print("No se pudo obtener la imagen publicada del dataset."); return 1
        result = compose.run_with_log(command, self.log_path, profiles=("dataset",))
        print(f"Registro de ejecución: {self.log_path}")
        if result: print("La operación del dataset ha finalizado con errores."); return result
        self._report_dataset_change(before)
        return 0

    def reconfigure(self) -> None:
        implementation = self._implementation()
        if implementation is None: return
        valid, reason = validate_dataset(self.data_dir)
        if not valid: print(reason); return
        policy = self._policy()
        if policy is None: return
        print(f"Se aplicará la política: {POLICY_LABELS[policy]}. Se obtendrá una vista previa sin modificar archivos.")
        options = DatasetOptions(public_audience_policy=policy)
        command = ["run", "--rm", "dataset", "--non-interactive", "--yes", "--action", "reconfigure", "--source", "reconfigure", "--public-audience-policy", policy]
        environment, _ = implementation
        compose = DockerCompose(self.configuration, environment)
        preview = [item for item in command if item != "--yes"] + ["--dry-run"]
        if environment is PRODUCTION and compose.run(["pull", "dataset"], profiles=("dataset",)):
            print("No se pudo obtener la imagen publicada del dataset."); return
        if compose.run_with_log(preview, self.log_path, profiles=("dataset",)):
            print("No se pudo generar la vista previa de la reconfiguración."); return
        self._execute(implementation, command, "reconfiguración", "dataset existente", options, "export")

    def validate(self) -> None:
        implementation = self._implementation()
        if implementation is None: return
        self._execute(implementation, ["run", "--rm", "dataset", "--non-interactive", "--action", "validate"], "validación", "no aplicable", DatasetOptions(), "audit")

    def cleanup(self) -> None:
        candidates = tuple(path for path in (self.data_dir / "pipeline_cache", self.data_dir / "tmp") if path.exists())
        if not candidates: print("No hay archivos temporales conocidos que limpiar."); return
        size = sum((file.stat().st_size for path in candidates for file in path.rglob("*") if file.is_file()), 0)
        print("Se eliminarán únicamente: " + ", ".join(str(path) for path in candidates) + f" ({size} bytes).")
        if not self.console.confirm("¿Limpiar estos archivos temporales?"): return
        implementation = self._implementation()
        if implementation is None: return
        self._execute(implementation, ["run", "--rm", "dataset", "--non-interactive", "--yes", "--action", "cleanup", "--cleanup", "standard"], "limpieza", "no aplicable", DatasetOptions(), "audit")

    def show_information(self) -> None:
        manifest = self.data_dir / "offline_dataset" / "manifest.json"
        if not manifest.is_file(): print("No hay un dataset offline completo para mostrar."); return
        try: payload = json.loads(manifest.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError): print("El manifiesto del dataset no es válido."); return
        print(f"Directorio de datos: {self.data_dir}")
        for key in ("generatedAt", "sourceDataset", "publicAudiencePolicy", "datasetFingerprint"): print(f"{key}: {payload.get(key, 'no disponible')}")
        print("Recuentos: " + json.dumps(payload.get("counts", {}), ensure_ascii=False))
        compatible = self._models_compatible()
        print("Compatibilidad de modelos: " + ("compatible" if compatible else "requiere reconstrucción"))

    def _resume_point(self) -> str:
        cache = self.data_dir / "pipeline_cache" / "movielens_32m"
        expected = {"candidates": "candidate_movies.json", "enrich": "tmdb_enriched_movies.json", "catalog": "partitioned_demo_catalog.json", "ratings": "filtered_collaborative_ratings.csv", "export": "../offline_dataset/manifest.json", "posters": "../offline_dataset/images/posters", "audit": "../offline_dataset/audit"}
        for stage, relative in expected.items():
            path = cache / relative
            if not path.exists(): return stage
        return "audit"

    def _zip_path(self) -> Path | None:
        value = self._text("Ruta del ZIP de MovieLens", "")
        if value is None: return None
        path = Path(value).expanduser().resolve()
        if not path.is_file() or path.suffix.lower() != ".zip": print("El ZIP debe ser un archivo .zip legible."); return None
        try:
            with path.open("rb"): pass
        except OSError: print("No se puede leer el ZIP indicado."); return None
        return path

    def _tmdb_behavior(self, start: str) -> str | None:
        if not self._includes(start, "enrich"): return "reuse"
        choice = self.console.menu("Enriquecimiento de TMDB", {"1": "Reanudar y reutilizar datos existentes", "2": "Repetir el enriquecimiento", "0": "Volver"})
        return {"1": "reuse", "2": "force"}.get(choice)

    def _includes(self, start: str, stage: str) -> bool: return STAGES.index(start) <= STAGES.index(stage)
    def _has_tmdb_token(self) -> bool: return bool(self.configuration.values.get("MOVIES_RECOMMENDER_TMDB_BEARER_TOKEN"))
    def _fingerprint(self) -> str | None:
        try: return dataset_fingerprint(self.data_dir)
        except OSError: return None
    def _models_compatible(self) -> bool:
        state = self.data_dir / "recommender_models" / "dataset_compatibility.json"
        try: return json.loads(state.read_text(encoding="utf-8")).get("datasetFingerprint") == self._fingerprint()
        except (OSError, json.JSONDecodeError): return False
    def _report_dataset_change(self, before: str | None) -> None:
        after = self._fingerprint()
        if after and before != after:
            print("El dataset ha cambiado.\nLos modelos existentes deben reconstruirse y entrenarse antes de reiniciar el Backend.")
    def _valid_options(self, values: DatasetOptions) -> bool:
        numbers = asdict(values)
        for key, value in numbers.items():
            if key in {"display_language", "public_audience_policy", "candidate_max_year", "public_limit", "candidate_min_tags"}: continue
            if not isinstance(value, int) or value <= 0:
                print(f"{key} debe ser mayor que cero."); return False
        if values.candidate_min_tags < 0 or (values.candidate_max_year and values.candidate_max_year < values.candidate_min_year): print("La configuración de años o etiquetas no es válida."); return False
        return True

    def _print_configuration_summary(self, options: DatasetOptions) -> None:
        print("\nResumen de configuración")
        for key, value in asdict(options).items():
            if key == "public_audience_policy":
                shown = POLICY_LABELS[value]
                label = "Política de audiencia"
            else:
                label = CONFIG_LABELS[key]
                shown = "sin límite" if value is None else str(value)
            print(f"{label}: {shown}")
    def _number(self, label: str, default: int | None, *, optional: bool, zero: bool) -> int | None:
        while True:
            value = self._text(label, "sin límite" if default is None else str(default))
            if value is None: return None
            if optional and value.lower() in {"", "sin límite", "none"}: return None
            try: result = int(value)
            except ValueError: print("Introduce un número entero válido."); continue
            if result > 0 or (zero and result == 0): return result
            print("El valor no es válido.")
    def _text(self, label: str, default: str) -> str | None:
        try: return input(f"{label} [{default}]: ").strip() or default
        except (EOFError, KeyboardInterrupt): print("\nOperación cancelada."); return None

    def _has_extracted_source(self) -> bool:
        root = self.data_dir / "raw" / "movielens" / "ml-32m" / "ml-32m"
        return all((root / name).is_file() for name in ("movies.csv", "ratings.csv", "tags.csv", "links.csv"))


def run_existing_interactive_flow(compose: DockerCompose) -> int:
    """Backward-compatible repository bridge retained for integrations."""
    return compose.run(["run", "--rm", "dataset"], profiles=("dataset",))
