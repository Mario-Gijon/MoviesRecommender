import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


SPEC = importlib.util.spec_from_file_location("manage", Path(__file__).parents[2] / "manage.py")
manage = importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(manage)


class ManageTests(unittest.TestCase):
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
