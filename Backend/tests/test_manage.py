import json
from contextlib import redirect_stdout
import io
import os
import shutil
import subprocess
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import Mock, patch

from manager.application import ApplicationManager
from manager.bootstrap import bootstrap_deployment
from manager.cli import InteractiveManager
from manager.compose import (
    DEVELOPMENT,
    PRODUCTION,
    DockerCompose,
    PublishedPort,
    ServiceStatus,
    format_service_health,
    format_service_state,
)
from manager.config import Configuration
from manager.console import Console
from manager.dataset import DatasetManager, DatasetOptions, RECOMMENDED_VALUES
from manager.models import ALGORITHMS, ModelManager
from manager.runtime import Runtime, deployment_runtime


ROOT = Path(__file__).parents[2]


class ManageTests(unittest.TestCase):
    def setUp(self) -> None:
        self.configuration = Configuration(
            root=ROOT,
            source=ROOT / ".env.example",
            values={
                "DATA_DIR": "./data",
                "MOVIES_RECOMMENDER_ACTIVE_COLLABORATIVE_MODEL_VARIANT": "item-active",
                "MOVIES_RECOMMENDER_BIASED_MATRIX_FACTORIZATION_MODEL_VARIANT": "biased-active",
            },
        )

    def test_environment_selection_supports_development_and_production(self) -> None:
        for selection, expected in (("1", DEVELOPMENT), ("2", PRODUCTION)):
            with self.subTest(selection=selection):
                manager = InteractiveManager()
                with patch.object(manager, "environment_menu") as menu, patch(
                    "builtins.input", side_effect=["1", selection, "0", "0"]
                ):
                    manager.run()
                menu.assert_called_once_with(expected)

    def test_compose_projects_are_isolated(self) -> None:
        development = DockerCompose(self.configuration, DEVELOPMENT).command(["ps"])
        production = DockerCompose(self.configuration, PRODUCTION).command(["ps"])
        self.assertIn("movies-recommender-dev", development)
        self.assertIn(str(ROOT / "compose.dev.yaml"), development)
        self.assertNotIn("-p", production)
        self.assertIn(str(ROOT / "compose.yaml"), production)
        self.assertIn("--project-directory", production)

    def test_backend_and_frontend_start_independently(self) -> None:
        compose = Mock()
        compose.run.return_value = 0
        development = ApplicationManager(self.configuration, DEVELOPMENT, compose)
        production = ApplicationManager(self.configuration, PRODUCTION, compose)

        development.execute("backend", "start")
        production.execute("frontend", "start")

        backend_call, frontend_call = compose.run.call_args_list
        self.assertEqual(["up", "-d", "api"], backend_call.args[0])
        self.assertNotIn("frontend", backend_call.args[0])
        self.assertEqual(["up", "-d", "frontend"], frontend_call.args[0])
        self.assertNotIn("api", frontend_call.args[0])
        self.assertEqual(("frontend",), frontend_call.kwargs["profiles"])

    def test_combined_operations_target_both_services(self) -> None:
        compose = Mock()
        compose.run.return_value = 0
        manager = ApplicationManager(self.configuration, DEVELOPMENT, compose)

        manager.execute("both", "restart")

        self.assertEqual(
            ["restart", "api", "frontend"], compose.run.call_args.args[0]
        )

    def test_development_update_builds_and_production_update_pulls(self) -> None:
        development_compose = Mock()
        development_compose.run.return_value = 0
        production_compose = Mock()
        production_compose.run.return_value = 0

        ApplicationManager(
            self.configuration, DEVELOPMENT, development_compose
        ).execute("backend", "update")
        ApplicationManager(
            self.configuration, PRODUCTION, production_compose
        ).execute("backend", "update")

        self.assertEqual(
            ["build", "api"], development_compose.run.call_args_list[0].args[0]
        )
        self.assertEqual(
            ["up", "-d", "--force-recreate", "api"],
            development_compose.run.call_args_list[1].args[0],
        )
        self.assertEqual(
            ["pull", "api"], production_compose.run.call_args_list[0].args[0]
        )
        self.assertEqual(
            ["up", "-d", "--force-recreate", "api"],
            production_compose.run.call_args_list[1].args[0],
        )

    def test_rebuild_uses_all_algorithms_and_env_variants(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            data_dir = Path(temporary)
            _write_valid_dataset(data_dir)
            configuration = Configuration(
                root=ROOT,
                source=ROOT / ".env.example",
                values={
                    "DATA_DIR": str(data_dir),
                    "MOVIES_RECOMMENDER_ACTIVE_COLLABORATIVE_MODEL_VARIANT": "item-v2",
                    "MOVIES_RECOMMENDER_BIASED_MATRIX_FACTORIZATION_MODEL_VARIANT": "biased-v3",
                },
            )
            compose = Mock()
            compose.run_with_log.return_value = 0
            compose.service_status.return_value = ServiceStatus("stopped")
            console = Mock(spec=Console)
            console.confirm.return_value = True

            manager = ModelManager(configuration, DEVELOPMENT, compose, console)
            self.assertEqual(0, manager.rebuild())

            command = compose.run_with_log.call_args.args[0]
            self.assertEqual("recommender-build", command[2])
            self.assertEqual(
                list(ALGORITHMS),
                [command[index + 1] for index, value in enumerate(command) if value == "--algorithm"],
            )
            self.assertEqual("item-v2", manager.configuration.item_knn_variant)
            self.assertEqual("biased-v3", manager.configuration.biased_variant)
            self.assertFalse(compose.run.called)

    def test_console_handles_invalid_input_and_interruptions(self) -> None:
        console = Console()
        with patch("builtins.input", side_effect=["x", KeyboardInterrupt]):
            self.assertIsNone(console.menu("Prueba", {"0": "Salir"}))

    def test_service_status_distinguishes_missing_stopped_running_and_unhealthy(self) -> None:
        compose = DockerCompose(self.configuration, PRODUCTION)
        cases = (
            ("", "missing", None),
            ('[{"State": "exited"}]', "exited", None),
            (
                '[{"State": "running", "Health": "healthy", "Publishers": [{"URL": "127.0.0.1:18014->8014/tcp"}]}]',
                "running",
                "healthy",
            ),
            ('[{"State": "running", "Health": "unhealthy"}]', "running", "unhealthy"),
        )
        for payload, state, health in cases:
            with self.subTest(payload=payload):
                result = subprocess.CompletedProcess([], 0, stdout=payload, stderr="")
                with patch("manager.compose.subprocess.run", return_value=result):
                    status = compose.service_status("api")
                self.assertEqual(state, status.state)
                self.assertEqual(health, status.health)

    def test_published_ports_include_external_internal_and_ipv6_formats(self) -> None:
        compose = DockerCompose(self.configuration, PRODUCTION)
        payload = json.dumps(
            [
                {
                    "State": "running",
                    "Publishers": [
                        {
                            "URL": "127.0.0.1",
                            "PublishedPort": 18014,
                            "TargetPort": 8014,
                            "Protocol": "tcp",
                        },
                        {
                            "URL": "0.0.0.0",
                            "PublishedPort": 8013,
                            "TargetPort": 80,
                            "Protocol": "tcp",
                        },
                        {
                            "URL": "::1",
                            "PublishedPort": 5173,
                            "TargetPort": 5173,
                            "Protocol": "tcp",
                        },
                        {
                            "URL": "[::]",
                            "PublishedPort": 8013,
                            "TargetPort": 8013,
                            "Protocol": "tcp",
                        },
                    ],
                }
            ]
        )
        result = subprocess.CompletedProcess([], 0, stdout=payload, stderr="")
        with patch("manager.compose.subprocess.run", return_value=result):
            status = compose.service_status("api")

        self.assertEqual(
            [
                ("127.0.0.1:18014", "8014/tcp"),
                ("0.0.0.0:8013", "80/tcp"),
                ("[::1]:5173", "5173/tcp"),
                ("[::]:8013", "8013/tcp"),
            ],
            [(port.external, port.internal) for port in status.published_ports],
        )

    def test_status_renders_all_published_ports_and_no_publisher_message(self) -> None:
        compose = Mock()
        compose.service_status.side_effect = [
            ServiceStatus(
                "running",
                published_ports=(
                    PublishedPort("127.0.0.1", "18014", "8014", "tcp"),
                    PublishedPort("0.0.0.0", "8013", "80", "tcp"),
                ),
            ),
            ServiceStatus("stopped"),
        ]
        manager = ApplicationManager(self.configuration, PRODUCTION, compose)
        output = io.StringIO()
        with redirect_stdout(output):
            manager.show_status(("api", "frontend"))
        rendered = output.getvalue()
        self.assertIn("Puerto publicado: 127.0.0.1:18014", rendered)
        self.assertIn("Puerto interno: 8014/tcp", rendered)
        self.assertIn("Puerto publicado: 0.0.0.0:8013", rendered)
        self.assertIn("Puerto interno: 80/tcp", rendered)
        self.assertIn("Puerto publicado: no publicado", rendered)

    def test_docker_states_and_health_are_rendered_in_spanish(self) -> None:
        expected_states = {
            "running": "ejecutándose",
            "stopped": "detenido",
            "exited": "detenido",
            "missing": "no creado",
            "created": "creado",
            "restarting": "reiniciándose",
            "paused": "pausado",
            "dead": "finalizado con error",
            "starting": "iniciando",
            "unknown": "desconocido",
        }
        for raw, expected in expected_states.items():
            with self.subTest(raw=raw):
                self.assertEqual(expected, format_service_state(raw))
        self.assertEqual("saludable", format_service_health("healthy"))
        self.assertEqual("no saludable", format_service_health("unhealthy"))
        self.assertEqual("iniciando", format_service_health("starting"))
        self.assertEqual("Estado desconocido: rebooting", format_service_state("rebooting"))

    def test_representative_cli_output_has_no_obsolete_english_labels(self) -> None:
        compose = Mock()
        compose.service_status.return_value = ServiceStatus("running", "healthy")
        manager = ApplicationManager(self.configuration, PRODUCTION, compose)
        output = io.StringIO()
        with redirect_stdout(output), patch("builtins.input", return_value="0"):
            manager.show_status(("api",))
            InteractiveManager().console.menu("Prueba", {"0": "Salir"})
        rendered = output.getvalue()
        for obsolete in (
            "Published port:",
            "Internal port:",
            "Health:",
            "running",
            "stopped",
            "not created",
            "Select an option",
            "Cancelled",
        ):
            self.assertNotIn(obsolete, rendered)

    def test_model_dataset_and_configuration_messages_are_spanish(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            configuration = Configuration(
                root=ROOT,
                source=ROOT / ".env.example",
                values={"DATA_DIR": temporary},
            )
            compose = Mock()
            compose.run.return_value = 0
            console = Mock(spec=Console)
            console.confirm.return_value = False
            models = ModelManager(configuration, DEVELOPMENT, compose, console)
            output = io.StringIO()
            with redirect_stdout(output):
                models.validate()
                with patch("builtins.input", side_effect=["3", "0"]):
                    InteractiveManager().run()
            rendered = output.getvalue()
        self.assertIn("Modelos: no compatibles", rendered)
        self.assertIn("Dataset offline ausente o inválido", rendered)
        self.assertIn("gestión de Configuración se implementará", rendered)
        self.assertNotIn("Models:", rendered)
        self.assertNotIn("Configuration:", rendered)

    def test_no_legacy_command_is_exposed_by_entrypoint(self) -> None:
        with patch("manager.cli.InteractiveManager.run", return_value=0) as run:
            from manager.cli import main

            self.assertEqual(0, main([]))
        run.assert_called_once()

    def test_first_run_writes_safe_default_env_and_data_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            console = Console()
            with patch("builtins.input", side_effect=["", "", "", "", "1", "", "s"]):
                self.assertTrue(bootstrap_deployment(root, console))
            values = _env_values(root / ".env")
            self.assertEqual("movies-recommender", values["COMPOSE_PROJECT_NAME"])
            self.assertEqual("./data", values["DATA_DIR"])
            self.assertEqual("18014", values["BACKEND_PORT"])
            self.assertEqual("15173", values["FRONTEND_PORT"])
            self.assertEqual("127.0.0.1", values["BACKEND_BIND_HOST"])
            self.assertEqual("127.0.0.1", values["FRONTEND_BIND_HOST"])
            self.assertEqual("top_k_100_min_support_25", values["MOVIES_RECOMMENDER_ACTIVE_COLLABORATIVE_MODEL_VARIANT"])
            self.assertTrue((root / "data").is_dir())

    def test_bootstrap_rejects_invalid_values_and_never_overwrites_env(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            existing = root / ".env"
            existing.write_text("KEEP=this\n", encoding="utf-8")
            with patch("builtins.input", side_effect=AssertionError("no debe preguntar")):
                self.assertTrue(bootstrap_deployment(root, Console()))
            self.assertEqual("KEEP=this\n", existing.read_text(encoding="utf-8"))
            existing.unlink()
            output = io.StringIO()
            inputs = ["Malo!", "good-project", "", "0", "18014", "18014", "15173", "2", "secreto", "s"]
            with redirect_stdout(output), patch("builtins.input", side_effect=inputs):
                self.assertTrue(bootstrap_deployment(root, Console()))
            values = _env_values(root / ".env")
            self.assertEqual("0.0.0.0", values["BACKEND_BIND_HOST"])
            self.assertEqual("0.0.0.0", values["FRONTEND_BIND_HOST"])
            self.assertNotIn("secreto", output.getvalue())
            self.assertIn("Introduce un puerto", output.getvalue())

    def test_bootstrap_cancellation_leaves_no_partial_env(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with patch("builtins.input", side_effect=KeyboardInterrupt):
                self.assertFalse(bootstrap_deployment(root, Console()))
            self.assertFalse((root / ".env").exists())

    def test_bootstrap_accepts_absolute_data_paths_with_spaces(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "instalación"
            data = Path(temporary) / "datos persistentes"
            root.mkdir()
            with patch("builtins.input", side_effect=["", str(data), "", "", "1", "", "s"]):
                self.assertTrue(bootstrap_deployment(root, Console()))
            self.assertEqual(str(data), _env_values(root / ".env")["DATA_DIR"])
            self.assertTrue(data.is_dir())

    def test_packaged_mode_is_production_only_and_dataset_is_safe(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "compose.yaml").write_text("services: {}\n", encoding="utf-8")
            (root / ".env").write_text("DATA_DIR=./data\n", encoding="utf-8")
            manager = InteractiveManager(runtime=Runtime(root, packaged=True))
            output = io.StringIO()
            with redirect_stdout(output), patch.object(DockerCompose, "validate_installation", return_value=(True, "")), patch.object(manager, "environment_menu") as environment_menu, patch("builtins.input", side_effect=["1", "2", "0", "0"]):
                self.assertEqual(0, manager.run())
            environment_menu.assert_called_once_with(PRODUCTION)
            self.assertNotIn("Desarrollo", output.getvalue())
            self.assertIn("Validar dataset offline", output.getvalue())

    def test_packaged_missing_compose_reports_absolute_path(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            output = io.StringIO()
            with redirect_stdout(output):
                result = InteractiveManager(runtime=Runtime(root, packaged=True)).run()
            self.assertEqual(1, result)
            self.assertIn(str(root / "compose.yaml"), output.getvalue())

    def test_deployment_runtime_uses_archive_parent_not_working_directory(self) -> None:
        self.assertEqual(Path("/tmp/con espacios").resolve(), deployment_runtime("/tmp/con espacios/manage.pyz").root)

    def test_build_archive_contains_only_manager_runtime_modules(self) -> None:
        result = subprocess.run(["python", "scripts/build_deployment_package.py"], cwd=ROOT, capture_output=True, text=True, check=False)
        self.assertEqual(0, result.returncode, result.stderr)
        archive = ROOT / "dist" / "MoviesRecommender" / "manage.pyz"
        with zipfile.ZipFile(archive) as package:
            names = package.namelist()
        forbidden = ("Backend", "Frontend", "tests", "compose.dev.yaml", ".env.example", "__pycache__", ".pyc")
        self.assertFalse(any(any(item in name for item in forbidden) for name in names), names)

    def test_archive_smoke_starts_from_a_different_directory(self) -> None:
        subprocess.run(["python", "scripts/build_deployment_package.py"], cwd=ROOT, check=True, capture_output=True, text=True)
        with tempfile.TemporaryDirectory(prefix="movies space ") as deployment, tempfile.TemporaryDirectory() as elsewhere:
            target = Path(deployment)
            shutil.copy2(ROOT / "dist" / "MoviesRecommender" / "manage.pyz", target / "manage.pyz")
            shutil.copy2(ROOT / "dist" / "MoviesRecommender" / "compose.yaml", target / "compose.yaml")
            result = subprocess.run(["python", str(target / "manage.pyz")], cwd=elsewhere, input="\n", capture_output=True, text=True, check=False)
            self.assertEqual(0, result.returncode)
            self.assertIn("No se ha encontrado el archivo .env", result.stdout)
            self.assertFalse((target / ".env").exists())

    def test_dataset_recommended_configuration_and_published_command(self) -> None:
        runtime = Runtime(ROOT, packaged=True)
        manager = DatasetManager(self.configuration, runtime, Mock(spec=Console))
        self.assertEqual(15000, RECOMMENDED_VALUES["candidate_limit"])
        self.assertEqual("family_and_teen", RECOMMENDED_VALUES["public_audience_policy"])
        command = manager._generation_command("download", DatasetOptions(), "candidates", "reuse", True, True, False, None)
        self.assertEqual(["run", "--rm", "dataset"], command[:3])
        self.assertIn("--source", command)
        self.assertIn("download", command)
        self.assertIn("--audit", command)
        self.assertNotIn("api", command)
        self.assertNotIn("frontend", command)

    def test_dataset_zip_is_resolved_read_only_and_supports_spaces(self) -> None:
        with tempfile.TemporaryDirectory(prefix="zip con espacios ") as temporary:
            archive = Path(temporary) / "ml 32m.zip"
            archive.write_bytes(b"zip")
            manager = DatasetManager(self.configuration, Runtime(ROOT, packaged=True), Mock(spec=Console))
            with patch("builtins.input", return_value=str(archive)):
                resolved = manager._zip_path()
            self.assertEqual(archive.resolve(), resolved)
            command = manager._generation_command("zip", DatasetOptions(), "candidates", "reuse", False, False, False, resolved)
            self.assertIn(f"{resolved}:/input/ml-32m.zip:ro", command)
            self.assertIn("/input/ml-32m.zip", command)

    def test_dataset_resume_cleanup_and_model_change_detection(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            data = Path(temporary)
            configuration = Configuration(root=ROOT, source=ROOT / ".env.example", values={"DATA_DIR": str(data)})
            console = Mock(spec=Console)
            manager = DatasetManager(configuration, Runtime(ROOT, packaged=True), console)
            self.assertEqual("candidates", manager._resume_point())
            output = io.StringIO()
            with redirect_stdout(output):
                manager.cleanup()
            self.assertIn("No hay archivos", output.getvalue())


def _write_valid_dataset(data_dir: Path) -> None:
    dataset = data_dir / "offline_dataset"
    (dataset / "csv").mkdir(parents=True)
    (dataset / "images" / "posters").mkdir(parents=True)
    for relative in (
        "manifest.json",
        "csv/public_movies.csv",
        "csv/collaborative_support_movies.csv",
        "csv/collaborative_ratings.csv",
    ):
        (dataset / relative).write_text(json.dumps({"valid": True}), encoding="utf-8")


def _env_values(path: Path) -> dict[str, str]:
    return dict(line.split("=", 1) for line in path.read_text(encoding="utf-8").splitlines())
