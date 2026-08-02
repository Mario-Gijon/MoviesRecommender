import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).parents[2]
SPEC = importlib.util.spec_from_file_location("manage", ROOT / "manage.py")
manage = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(manage)


class ManageTests(unittest.TestCase):
    def test_compose_projects_are_standalone_and_distinct(self) -> None:
        production = manage.compose_args(False)
        development = manage.compose_args(True)
        self.assertIn("compose.yaml", production)
        self.assertNotIn("compose.dev.yaml", production)
        self.assertIn("movies-recommender-local", production)
        self.assertIn("compose.dev.yaml", development)
        self.assertNotIn("compose.yaml", development)
        self.assertIn("movies-recommender-dev", development)

    def test_dev_starts_api_and_frontend_without_force_recreate(self) -> None:
        args = manage.parser().parse_args(["dev"])
        with patch.object(manage, "ensure_docker", return_value=True), patch.object(
            manage, "run", return_value=0
        ) as run, patch.object(manage, "wait_ready", return_value=True), patch.object(
            manage, "read_env", return_value={}
        ):
            self.assertEqual(0, manage.dev(args))
        command = run.call_args.args[0]
        self.assertEqual(["api", "frontend"], command[-2:])
        self.assertNotIn("--force-recreate", command)
        self.assertIn("compose.dev.yaml", command)

    def test_dev_stop_only_targets_development_api_and_frontend(self) -> None:
        args = manage.parser().parse_args(["dev-stop"])
        with patch.object(manage, "run", return_value=0) as run:
            self.assertEqual(0, manage.dev_stop(args))
        command = run.call_args.args[0]
        self.assertEqual(["stop", "api", "frontend"], command[-3:])
        self.assertIn("compose.dev.yaml", command)
        self.assertNotIn("--volumes", command)

    def test_dev_rebuild_is_scoped_to_requested_service(self) -> None:
        for target, expected in (("frontend", "frontend"), ("backend", "api")):
            with self.subTest(target=target):
                args = manage.parser().parse_args(["dev-rebuild", target])
                with patch.object(manage, "ensure_docker", return_value=True), patch.object(
                    manage, "run", return_value=0
                ) as run:
                    self.assertEqual(0, manage.dev_rebuild(args))
                commands = [call.args[0] for call in run.call_args_list]
                self.assertEqual(expected, commands[0][-1])
                self.assertEqual(expected, commands[1][-1])
                self.assertIn("--force-recreate", commands[1])

    def test_frontend_published_commands_do_not_require_backend(self) -> None:
        args = manage.parser().parse_args(["frontend-start"])
        with patch.object(manage, "ensure_docker", return_value=True), patch.object(
            manage, "run", return_value=0
        ) as run:
            self.assertEqual(0, manage.frontend_start(args))
        self.assertIn("frontend", run.call_args.args[0])
        self.assertNotIn("api", run.call_args.args[0])
        self.assertIn("compose.yaml", run.call_args.args[0])

    def test_development_compose_has_hmr_reload_and_root_data_dir(self) -> None:
        content = (ROOT / "compose.dev.yaml").read_text(encoding="utf-8")
        self.assertIn("--reload", content)
        self.assertIn("bun\", \"run\", \"dev", content)
        self.assertIn("./Frontend:/app", content)
        self.assertIn("./Backend/pipelines:/app/pipelines", content)
        self.assertIn("${DATA_DIR:-./data}:/app/data", content)
        self.assertNotIn("VITE_API_URL", content)
        self.assertNotIn("bun install", content)

    def test_published_frontend_has_no_api_startup_dependency(self) -> None:
        production = (ROOT / "compose.yaml").read_text(encoding="utf-8")
        frontend = production.split("  frontend:", 1)[1]
        self.assertNotIn("depends_on", frontend)

    def test_vite_proxy_rewrites_only_api_prefix(self) -> None:
        content = (ROOT / "Frontend" / "vite.config.js").read_text(encoding="utf-8")
        self.assertIn("path.replace(/^\\/api/, '')", content)
        self.assertIn("'/offline'", content)
        self.assertIn("'/audit'", content)

    def test_main_menu_has_only_scoped_entries_and_submenu_back_returns(self) -> None:
        with patch("builtins.input", side_effect=["0"]):
            self.assertEqual(0, manage.menu())
        with patch("builtins.input", return_value="0"):
            self.assertEqual(0, manage.backend_management())
            self.assertEqual(0, manage.frontend_management())

    def test_relative_data_dir_remains_root_relative(self) -> None:
        args = manage.parser().parse_args(["start"])
        with patch.object(manage, "read_env", return_value={"DATA_DIR": "./data"}):
            data = manage.configured_data_dir(args)
        self.assertEqual(ROOT / "data", data)

    def test_env_update_preserves_unknown_entries(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            env = Path(temporary) / ".env"
            env.write_text("UNKNOWN=value\nDATA_DIR=old\n", encoding="utf-8")
            with patch.object(manage, "ENV_FILE", env), patch.object(manage, "EXAMPLE_ENV", env):
                manage.update_env({"DATA_DIR": "./data"})
            self.assertIn("UNKNOWN=value", env.read_text(encoding="utf-8"))
