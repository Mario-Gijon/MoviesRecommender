import io
import os
import subprocess
import tempfile
import unittest
import zipfile
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from pipelines.dataset_generation import cli
from pipelines.dataset_generation.movielens_source import (
    MovieLensSourceError,
    MovieLensSourcePaths,
    has_valid_extracted_files,
    import_zip,
    inspect_zip,
    prepare_source,
)
from pipelines.dataset_generation.run_movielens_32m_pipeline import (
    DatasetPipelineConfig,
    build_stage_command,
    run_pipeline,
    select_stages,
)


class DatasetCliConfigurationTests(unittest.TestCase):
    def test_recommended_preset_values(self) -> None:
        config = cli.resolve_config(cli.build_parser().parse_args(["--preset", "recommended"]))
        self.assertEqual(15000, config.candidate_limit)
        self.assertEqual(1990, config.candidate_min_year)
        self.assertEqual(15000, config.collaborative_core_limit)

    def test_defaults_preset_uses_orchestrator_defaults(self) -> None:
        config = cli.resolve_config(cli.build_parser().parse_args(["--preset", "defaults"]))
        self.assertEqual(DatasetPipelineConfig(), config)

    def test_explicit_flags_override_preset(self) -> None:
        config = cli.resolve_config(cli.build_parser().parse_args([
            "--preset", "recommended", "--candidate-limit", "123", "--skip-posters", "--audit",
        ]))
        self.assertEqual(123, config.candidate_limit)
        self.assertTrue(config.skip_posters)
        self.assertTrue(config.audit)

    def test_invalid_ranges_and_stage_range_are_rejected(self) -> None:
        with self.assertRaises(ValueError):
            cli.resolve_config(cli.build_parser().parse_args([
                "--candidate-min-year", "2020", "--candidate-max-year", "2019",
            ]))
        with self.assertRaises(ValueError):
            select_stages(DatasetPipelineConfig(start_at="export", stop_after="catalog"))

    def test_non_interactive_validates_source_requirements(self) -> None:
        self.assertEqual(1, cli.main(["--non-interactive", "--yes", "--dry-run"]))
        self.assertEqual(1, cli.main([
            "--non-interactive", "--yes", "--source", "zip", "--dry-run",
        ]))

    def test_dry_run_does_not_prepare_source_or_run_commands(self) -> None:
        runner = Mock()
        with patch("pipelines.dataset_generation.run_movielens_32m_pipeline.prepare_source") as prepare:
            stages = run_pipeline(DatasetPipelineConfig(skip_posters=True), source="download", dry_run=True, runner=runner)
        self.assertNotIn("posters", stages)
        prepare.assert_not_called()
        runner.assert_not_called()

    def test_tmdb_token_not_required_outside_enrichment_and_not_printed(self) -> None:
        config = DatasetPipelineConfig(start_at="catalog", skip_posters=True)
        with patch.object(cli, "settings", SimpleNamespace(tmdb_bearer_token=None)), patch.dict(os.environ, {}, clear=True):
            self.assertIsNone(cli._resolve_token(config, interactive=False, dry_run=False))
        preview = io.StringIO()
        with redirect_stdout(preview):
            cli._print_plan(config, "existing", None)
        self.assertNotIn("secret-token", preview.getvalue())

    def test_enrichment_requires_noninteractive_token_before_run(self) -> None:
        with patch.object(cli, "settings", SimpleNamespace(tmdb_bearer_token=None)), patch.dict(os.environ, {}, clear=True):
            self.assertEqual(1, cli.main([
                "--non-interactive", "--yes", "--source", "download", "--skip-posters",
            ]))

    def test_interactive_token_uses_hidden_prompt(self) -> None:
        with patch.object(cli, "settings", SimpleNamespace(tmdb_bearer_token=None)), patch.dict(os.environ, {}, clear=True), patch(
            "pipelines.dataset_generation.cli.getpass.getpass", return_value="hidden-token"
        ) as prompt:
            token = cli._resolve_token(DatasetPipelineConfig(), interactive=True, dry_run=False)
        self.assertEqual("hidden-token", token)
        prompt.assert_called_once()

    def test_cancellation_and_stage_failure_do_not_report_success(self) -> None:
        config = DatasetPipelineConfig(start_at="catalog", skip_posters=True)
        with patch("pipelines.dataset_generation.cli._interactive_configuration", return_value=(config, "existing", None)), patch(
            "pipelines.dataset_generation.cli._resolve_token", return_value=None
        ), patch("builtins.input", return_value="n"), patch(
            "pipelines.dataset_generation.cli.run_pipeline"
        ) as run:
            self.assertEqual(0, cli.main([]))
        run.assert_not_called()
        with patch("pipelines.dataset_generation.cli.run_pipeline", side_effect=subprocess.CalledProcessError(1, ["stage"])), patch.object(
            cli, "settings", SimpleNamespace(tmdb_bearer_token=None)
        ):
            self.assertEqual(1, cli.main([
                "--non-interactive", "--yes", "--source", "existing", "--start-at", "catalog", "--skip-posters",
            ]))

    def test_force_tmdb_is_reflected_once_in_stage_command(self) -> None:
        command = build_stage_command("enrich", DatasetPipelineConfig(force_tmdb=True, resume_tmdb=False))
        self.assertIn("--force", command)
        self.assertNotIn("--resume", command)


class MovieLensSourceTests(unittest.TestCase):
    def test_valid_nested_zip_recognition_and_safe_import(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive = root / "source.zip"
            _write_zip(archive, {f"nested/ml-32m/{name}": name.encode() for name in _required_names()})
            paths = MovieLensSourcePaths(root / "raw" / "ml-32m", root / "raw" / "ml-32m.zip")
            self.assertEqual(set(_required_names()), set(inspect_zip(archive)))
            self.assertEqual("imported", import_zip(archive, paths=paths))
            self.assertTrue(has_valid_extracted_files(paths.dataset_dir))

    def test_zip_rejects_missing_ambiguous_traversal_and_corrupt_content(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            missing = root / "missing.zip"
            _write_zip(missing, {"ml-32m/movies.csv": b"x"})
            with self.assertRaises(MovieLensSourceError):
                inspect_zip(missing)
            ambiguous = root / "ambiguous.zip"
            entries = {f"a/ml-32m/{name}": b"x" for name in _required_names()}
            entries.update({f"b/ml-32m/{name}": b"x" for name in _required_names()})
            _write_zip(ambiguous, entries)
            with self.assertRaises(MovieLensSourceError):
                inspect_zip(ambiguous)
            traversal = root / "traversal.zip"
            _write_zip(traversal, {"../movies.csv": b"x"})
            with self.assertRaises(MovieLensSourceError):
                inspect_zip(traversal)
            corrupt = root / "corrupt.zip"
            corrupt.write_bytes(b"not a zip")
            with self.assertRaises(MovieLensSourceError):
                inspect_zip(corrupt)

    def test_failed_import_leaves_existing_raw_files_unchanged(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            paths = MovieLensSourcePaths(root / "raw" / "ml-32m", root / "raw" / "ml-32m.zip")
            paths.dataset_dir.mkdir(parents=True)
            for name in _required_names():
                (paths.dataset_dir / name).write_text("old", encoding="utf-8")
            corrupt = root / "corrupt.zip"
            corrupt.write_bytes(b"invalid")
            with self.assertRaises(MovieLensSourceError):
                import_zip(corrupt, paths=paths)
            self.assertEqual("old", (paths.dataset_dir / "movies.csv").read_text(encoding="utf-8"))

    def test_existing_source_and_download_reuse(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            paths = MovieLensSourcePaths(root / "raw" / "ml-32m", root / "raw" / "ml-32m.zip")
            paths.dataset_dir.mkdir(parents=True)
            for name in _required_names():
                (paths.dataset_dir / name).write_text("ready", encoding="utf-8")
            self.assertEqual("reused existing raw files", prepare_source("existing", paths=paths))
            downloader = Mock()
            self.assertEqual("reused existing raw files", prepare_source("download", paths=paths, download=downloader))
            downloader.assert_not_called()

    def test_zip_path_is_rejected_for_unrelated_source(self) -> None:
        self.assertEqual(1, cli.main([
            "--non-interactive", "--yes", "--source", "existing", "--zip-path", "/input/source.zip", "--dry-run",
        ]))


def _required_names() -> tuple[str, ...]:
    return ("movies.csv", "ratings.csv", "tags.csv", "links.csv")


def _write_zip(path: Path, entries: dict[str, bytes]) -> None:
    with zipfile.ZipFile(path, "w") as archive:
        for name, content in entries.items():
            archive.writestr(name, content)
