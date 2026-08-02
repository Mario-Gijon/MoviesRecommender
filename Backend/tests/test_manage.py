import importlib.util
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


SPEC = importlib.util.spec_from_file_location("manage", Path(__file__).parents[2] / "manage.py")
manage = importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(manage)


class ManageTests(unittest.TestCase):
    CATALOGUE = {"itemKnn": [{"variantId": "item", "recommended": True}], "biasedMatrixFactorization": [{"variantId": "bmf"}]}
    def test_env_update_preserves_unknown_and_normalizes_path(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); env = root / ".env"; env.write_text("# note\nUNKNOWN=value\nDATA_DIR=old\n", encoding="utf-8")
            with patch.object(manage, "ENV_FILE", env), patch.object(manage, "EXAMPLE_ENV", root / "missing"):
                manage.update_env({"DATA_DIR": manage.absolute_path(root / "data")})
            text = env.read_text(encoding="utf-8")
            self.assertIn("UNKNOWN=value", text); self.assertIn("DATA_DIR=" + (root / "data").as_posix(), text)
            self.assertFalse(any(root.glob("tmp*")))

    def test_compose_mode_and_dataset_validation_are_host_only(self) -> None:
        self.assertNotIn("compose.dev.yaml", manage.compose_args(False)); self.assertIn("compose.dev.yaml", manage.compose_args(True))
        with tempfile.TemporaryDirectory() as temporary:
            valid, _ = manage.validate_dataset(Path(temporary)); self.assertFalse(valid)

    def test_stop_command_never_uses_volumes(self) -> None:
        with patch.object(manage, "run", return_value=0) as run:
            self.assertEqual(0, manage.main(["stop", "--non-interactive"]))
        self.assertNotIn("--volumes", run.call_args.args[0])

    def test_start_reuses_compatible_models_without_rebuild(self) -> None:
        args = manage.parser().parse_args(["start"])
        with patch.object(manage, "configured_data_dir", return_value=Path("/tmp/data")), patch.object(
            manage, "update_env"
        ), patch.object(manage, "validate_dataset", return_value=(True, "ok")), patch.object(
            manage, "validate_active_models", return_value=(True, "compatible")
        ), patch.object(manage, "ensure_docker", return_value=True), patch.object(
            manage, "run", return_value=0
        ) as run, patch.object(manage, "wait_ready", return_value=True), patch.object(
            manage, "rebuild_models"
        ) as rebuild:
            self.assertEqual(0, manage.start_backend(args))
        rebuild.assert_not_called()
        self.assertIn("--force-recreate", run.call_args.args[0])

    def test_menu_exit_and_dataset_route(self) -> None:
        with patch("builtins.input", return_value="0"), patch.object(manage, "run") as run:
            self.assertEqual(0, manage.menu()); run.assert_not_called()
        with patch("builtins.input", return_value="1"), patch.object(manage, "main", return_value=0) as routed:
            self.assertEqual(0, manage.menu()); routed.assert_called_once_with(["dataset"])

    def test_interactive_dataset_does_not_invent_noninteractive_arguments(self) -> None:
        args = manage.parser().parse_args(["dataset"])
        with patch.object(manage, "configured_data_dir", return_value=Path("/tmp/data")), patch.object(manage, "read_env", return_value={"MOVIES_RECOMMENDER_TMDB_BEARER_TOKEN": "set"}), patch.object(manage, "update_env"), patch.object(manage, "ensure_docker", return_value=True), patch.object(manage, "run", return_value=0) as run:
            self.assertEqual(0, manage.dataset(args))
        command = run.call_args.args[0]
        self.assertNotIn("--non-interactive", command); self.assertNotIn("existing", command)

    def test_noninteractive_zip_mount_and_confirmation_requirements(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            archive = Path(temporary) / "source.zip"; archive.write_text("zip", encoding="utf-8")
            args = manage.parser().parse_args(["dataset", "--non-interactive", "--source", "zip", "--zip-path", str(archive), "--yes"])
            with patch.object(manage, "configured_data_dir", return_value=Path(temporary) / "data"), patch.object(manage, "update_env"), patch.object(manage, "ensure_docker", return_value=True), patch.object(manage, "run", return_value=0) as run:
                self.assertEqual(0, manage.dataset(args))
            command = run.call_args.args[0]
            self.assertIn("--volume", command); self.assertIn("/input/ml-32m.zip", command); self.assertNotIn(str(archive), command[command.index("dataset") + 1:])
        args = manage.parser().parse_args(["deploy", "--non-interactive"])
        with patch.object(manage, "configured_data_dir", return_value=Path("/missing")), patch.object(manage, "update_env") as update:
            self.assertEqual(1, manage.deploy(args)); update.assert_called_once()

    def test_clean_resolution_controls_builder_and_summary(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            data = Path(temporary)
            def execute(arguments):
                args = manage.parser().parse_args(arguments)
                with patch.object(manage, "configured_data_dir", return_value=data), patch.object(manage, "validate_dataset", return_value=(True, "ok")), patch.object(manage, "ensure_docker", return_value=True), patch.object(manage, "profiles", return_value=self.CATALOGUE), patch.object(manage, "update_env"), patch.object(manage, "_write_model_dataset_state"), patch.object(manage, "run", return_value=0) as run, patch.object(manage, "wait_ready", return_value=True), patch.object(manage, "_choose_profile", side_effect=lambda _t, _v, default: default), patch.object(manage, "_ask_yes_no", side_effect=[False, True]), patch("builtins.input", return_value="all"):
                    self.assertEqual(0, manage.rebuild_models(args))
                return run.call_args_list[0].args[0]
            self.assertNotIn("--clean", execute(["rebuild-models"]))
            self.assertIn("--clean", execute(["rebuild-models", "--non-interactive", "--yes"]))
            self.assertNotIn("--clean", execute(["rebuild-models", "--non-interactive", "--yes", "--no-clean"]))

    def test_explicit_clean_does_not_prompt_and_zip_errors_precede_compose(self) -> None:
        args = manage.parser().parse_args(["dataset", "--source", "zip"])
        with patch.object(manage, "ensure_docker") as docker:
            self.assertEqual(1, manage.dataset(args)); docker.assert_not_called()
        args = manage.parser().parse_args(["dataset", "--source", "existing", "--zip-path", "/tmp/x.zip"])
        with patch.object(manage, "ensure_docker") as docker:
            self.assertEqual(1, manage.dataset(args)); docker.assert_not_called()
