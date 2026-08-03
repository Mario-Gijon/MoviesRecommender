"""Top-level interactive navigation for Movies Recommender."""

from __future__ import annotations

import sys

from manager.application import ApplicationManager
from manager.bootstrap import bootstrap_deployment
from manager.compose import DEVELOPMENT, PRODUCTION, DockerCompose, Environment
from manager.config import load_configuration
from manager.console import Console
from manager.dataset import run_existing_interactive_flow
from manager.models import ModelManager
from manager.runtime import Runtime, repository_runtime


class InteractiveManager:
    def __init__(self, console: Console | None = None, runtime: Runtime | None = None) -> None:
        self.console = console or Console()
        self.runtime = runtime or repository_runtime()

    def run(self) -> int:
        if self.runtime.packaged:
            compose_file = self.runtime.root / "compose.yaml"
            if not compose_file.is_file():
                print(f"No se ha encontrado el archivo Compose requerido: {compose_file}")
                return 1
            if not bootstrap_deployment(self.runtime.root, self.console):
                return 0
            configuration = load_configuration(self.runtime.root, require_env=True)
            valid, message = DockerCompose(configuration, PRODUCTION).validate_installation()
            if not valid:
                print(message)
                return 1
        while True:
            choice = self.console.menu(
                "Gestor de Movies Recommender",
                {
                    "1": "Aplicación",
                    "2": "Dataset",
                    "3": "Configuración",
                    "0": "Salir",
                },
            )
            if choice in {None, "0"}:
                return 0
            if choice == "1":
                self.application_menu()
            elif choice == "2":
                if self.runtime.packaged:
                    print("La gestión del dataset mediante la imagen publicada se implementará en la siguiente fase.")
                else:
                    configuration = load_configuration(self.runtime.root)
                    run_existing_interactive_flow(DockerCompose(configuration, PRODUCTION))
            else:
                print("La gestión de Configuración se implementará en la siguiente fase.")

    def application_menu(self) -> None:
        if self.runtime.packaged:
            self.environment_menu(PRODUCTION)
            return
        while True:
            choice = self.console.menu(
                "Selecciona el entorno",
                {"1": "Desarrollo", "2": "Producción", "0": "Volver"},
            )
            if choice in {None, "0"}:
                return
            self.environment_menu(DEVELOPMENT if choice == "1" else PRODUCTION)

    def environment_menu(self, environment: Environment) -> None:
        configuration = load_configuration(self.runtime.root, require_env=self.runtime.packaged)
        compose = DockerCompose(configuration, environment)
        application = ApplicationManager(configuration, environment, compose)
        models = ModelManager(configuration, environment, compose, self.console)
        while True:
            choice = self.console.menu(
                f"Aplicación · {environment.label}",
                {
                    "1": "Backend",
                    "2": "Frontend",
                    "3": "Backend + Frontend",
                    "4": "Modelos de recomendación",
                    "5": "Estado general",
                    "0": "Volver",
                },
            )
            if choice in {None, "0"}:
                return
            if choice == "4":
                self.models_menu(environment, models)
            elif choice == "5":
                application.show_status()
            else:
                self.service_menu(
                    application,
                    {"1": "backend", "2": "frontend", "3": "both"}[choice],
                )

    def service_menu(self, application: ApplicationManager, target: str) -> None:
        label = {
            "backend": "Backend",
            "frontend": "Frontend",
            "both": "Backend + Frontend",
        }[target]
        actions = {
            "1": "Iniciar",
            "2": "Detener",
            "3": "Reiniciar",
            "4": "Actualizar",
            "5": "Ver estado",
            "6": "Ver registros",
            "0": "Volver",
        }
        action_names = {
            "1": "start",
            "2": "stop",
            "3": "restart",
            "4": "update",
            "5": "status",
            "6": "logs",
        }
        while True:
            choice = self.console.menu(label, actions)
            if choice in {None, "0"}:
                return
            application.execute(target, action_names[choice])

    def models_menu(self, environment: Environment, models: ModelManager) -> None:
        actions = {
            "1": "Ver modelos existentes",
            "2": "Validar modelos y compatibilidad",
            "3": "Reconstruir y entrenar modelos",
            "4": "Ejecutar auditoría",
            "5": "Ver logs de la última ejecución",
            "0": "Volver",
        }
        while True:
            choice = self.console.menu(
                f"Modelos de recomendación · {environment.label}", actions
            )
            if choice in {None, "0"}:
                return
            if choice == "1":
                models.show_existing()
            elif choice == "2":
                models.validate()
            elif choice == "3":
                models.rebuild()
            elif choice == "4":
                models.audit()
            else:
                models.show_last_log()


def main(argv: list[str] | None = None, *, runtime: Runtime | None = None) -> int:
    supplied = sys.argv[1:] if argv is None else argv
    if supplied:
        print(
            "Esta versión se usa de forma interactiva: ejecuta `python manage.py`.",
            file=sys.stderr,
        )
        return 2
    try:
        return InteractiveManager(runtime=runtime).run()
    except KeyboardInterrupt:
        print("\nOperación cancelada.")
        return 0
