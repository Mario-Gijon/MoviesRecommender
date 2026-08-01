import io
import os
import subprocess
import sys
import tempfile
import unittest
import zipfile
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from pipelines.dataset_generation import cli, download_movielens_32m
from pipelines.dataset_generation.movielens_source import (
    MovieLensSourceError,
    MovieLensSourcePaths,
    has_valid_extracted_files,
    import_zip,
    inspect_zip,
    prepare_source,
)
from pipelines.dataset_generation.run_movielens_32m_pipeline import (
    DatasetStageError,
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

    def test_noninteractive_source_requirement_depends_on_selected_stages(self) -> None:
        self.assertEqual(0, cli.main([
            "--non-interactive", "--yes", "--start-at", "catalog", "--stop-after", "catalog", "--dry-run",
        ]))
        self.assertEqual(1, cli.main([
            "--non-interactive", "--yes", "--start-at", "candidates", "--dry-run",
        ]))
        self.assertEqual(1, cli.main([
            "--non-interactive", "--yes", "--start-at", "ratings", "--stop-after", "ratings", "--dry-run",
        ]))
        self.assertEqual(0, cli.main([
            "--non-interactive", "--yes", "--source", "existing", "--start-at", "ratings", "--stop-after", "ratings", "--dry-run",
        ]))

    def test_interactive_non_raw_range_skips_source_and_prints_one_plan(self) -> None:
        args = cli.build_parser().parse_args(["--start-at", "catalog", "--stop-after", "catalog"])
        with patch("pipelines.dataset_generation.cli._ask_choice", return_value="recommended"), patch(
            "pipelines.dataset_generation.cli._ask_yes_no", return_value=False
        ), patch("pipelines.dataset_generation.cli.has_valid_extracted_files") as raw:
            config, source, zip_path = cli._interactive_configuration(args)
        self.assertEqual("existing", source)
        self.assertIsNone(zip_path)
        self.assertEqual("catalog", config.start_at)
        raw.assert_not_called()
        config = DatasetPipelineConfig(start_at="catalog", stop_after="catalog", skip_posters=True)
        output = io.StringIO()
        with patch("pipelines.dataset_generation.cli._interactive_configuration", return_value=(config, "existing", None)), patch(
            "pipelines.dataset_generation.cli._resolve_token", return_value=None
        ), patch("builtins.input", return_value="n"), redirect_stdout(output):
            cli.main([])
        self.assertEqual(1, output.getvalue().count("Dataset installation summary"))

    def test_interactive_ratings_range_asks_for_source(self) -> None:
        args = cli.build_parser().parse_args(["--start-at", "ratings", "--stop-after", "ratings"])
        with patch("pipelines.dataset_generation.cli._ask_choice", side_effect=("recommended", "existing", "standard")) as choice, patch(
            "pipelines.dataset_generation.cli._ask_yes_no", return_value=False
        ), patch("pipelines.dataset_generation.cli.has_valid_extracted_files", return_value=True) as raw:
            config, source, zip_path = cli._interactive_configuration(args)
        self.assertEqual("ratings", config.start_at)
        self.assertEqual("existing", source)
        self.assertIsNone(zip_path)
        raw.assert_called_once()
        self.assertEqual("MovieLens source", choice.call_args_list[1].args[0])

    def test_custom_stop_after_uses_explicit_default(self) -> None:
        config = DatasetPipelineConfig(stop_after="export")
        with patch("pipelines.dataset_generation.cli._ask_integer", side_effect=lambda _q, value, **_k: value), patch(
            "pipelines.dataset_generation.cli._ask_yes_no", return_value=False
        ), patch("pipelines.dataset_generation.cli._ask_text", side_effect=lambda _q, default=None, **_k: default), patch(
            "pipelines.dataset_generation.cli._ask_choice", side_effect=lambda _q, _choices, default: default
        ) as choice:
            cli._ask_advanced_config(config)
        self.assertEqual("export", choice.call_args_list[-1].args[2])

    def test_configuration_mode_menu_accepts_number_and_text(self) -> None:
        with patch("builtins.input", return_value="1"):
            self.assertEqual(cli._ask_configuration_mode(), "recommended")

        with patch("builtins.input", return_value="advanced"):
            self.assertEqual(cli._ask_configuration_mode(), "advanced")

    def test_explained_prompt_uses_the_actual_decision_question(self) -> None:
        question = "Download missing movie posters?"
        with (
            patch("pipelines.dataset_generation.cli._ask_yes_no", return_value=True) as ask,
            redirect_stdout(io.StringIO()) as output,
        ):
            result = cli._ask_explained_yes_no(
                question,
                "Posters are saved for frontend display.",
                default=True,
            )

        self.assertTrue(result)
        ask.assert_called_once_with(question, default=True)
        self.assertNotIn("Continue?", output.getvalue())

    def test_installation_summary_uses_readable_resolved_decisions(self) -> None:
        config = DatasetPipelineConfig(skip_posters=False, audit=True, force_tmdb=False)
        output = io.StringIO()

        with redirect_stdout(output):
            cli._print_plan(
                config,
                "download",
                None,
                mode="advanced",
                cleanup="minimal",
            )

        summary = output.getvalue()
        self.assertIn("Configuration mode: Advanced", summary)
        self.assertIn("MovieLens source: Download automatically", summary)
        self.assertIn("Download posters: Yes", summary)
        self.assertIn("Generate audit: Yes", summary)
        self.assertIn("TMDB behavior: Resume completed enrichment", summary)
        self.assertIn("Cleanup mode: Minimal runtime files", summary)
        self.assertIn(
            "Cleanup effect: Removes pipeline cache, raw MovieLens data and offline audit files",
            summary,
        )

    def test_cleanup_menu_describes_raw_data_and_audit_retention(self) -> None:
        output = io.StringIO()
        with patch("pipelines.dataset_generation.cli._ask_choice", return_value="standard"), redirect_stdout(output):
            self.assertEqual("standard", cli._ask_cleanup())

        menu = output.getvalue()
        self.assertIn("Removes pipeline cache and downloaded MovieLens source files.", menu)
        self.assertIn("Keeps the final dataset, posters and dataset quality report.", menu)
        self.assertIn("Removes pipeline cache, downloaded MovieLens source files and dataset quality report.", menu)

    def test_cleanup_effects_and_previews_include_all_removable_paths(self) -> None:
        self.assertIn("pipeline cache", cli._cleanup_effect("standard"))
        self.assertIn("raw MovieLens data", cli._cleanup_effect("standard"))
        self.assertIn("pipeline cache", cli._cleanup_effect("minimal"))
        self.assertIn("raw MovieLens data", cli._cleanup_effect("minimal"))
        self.assertIn("offline audit files", cli._cleanup_effect("minimal"))

        paths = cli.DatasetPaths(Path("/app/data"))
        standard = io.StringIO()
        minimal = io.StringIO()
        with redirect_stdout(standard):
            cli._print_cleanup_preview("standard", paths)
        with redirect_stdout(minimal):
            cli._print_cleanup_preview("minimal", paths)

        self.assertIn("/app/data/pipeline_cache", standard.getvalue())
        self.assertIn("/app/data/raw", standard.getvalue())
        self.assertNotIn("/app/data/offline_dataset/audit", standard.getvalue())
        self.assertIn("/app/data/offline_dataset/audit", minimal.getvalue())
        self.assertIn("/app/data/offline_dataset/images/posters", minimal.getvalue())

    def test_dry_run_does_not_prepare_source_or_run_commands(self) -> None:
        runner = Mock()
        with patch("pipelines.dataset_generation.run_movielens_32m_pipeline.prepare_source") as prepare:
            stages = run_pipeline(DatasetPipelineConfig(skip_posters=True), source="download", dry_run=True, runner=runner)
        self.assertNotIn("posters", stages)
        prepare.assert_not_called()
        runner.assert_not_called()

    def test_run_pipeline_prepares_source_for_ratings_but_not_catalog(self) -> None:
        runner = Mock()
        with patch("pipelines.dataset_generation.run_movielens_32m_pipeline.prepare_source") as prepare:
            run_pipeline(DatasetPipelineConfig(start_at="ratings", stop_after="ratings"), source="existing", runner=runner)
        prepare.assert_called_once_with("existing", zip_path=None)
        with patch("pipelines.dataset_generation.run_movielens_32m_pipeline.prepare_source") as prepare:
            run_pipeline(DatasetPipelineConfig(start_at="catalog", stop_after="catalog"), runner=runner)
        prepare.assert_not_called()
        with patch("pipelines.dataset_generation.run_movielens_32m_pipeline.prepare_source") as prepare:
            run_pipeline(DatasetPipelineConfig(start_at="catalog", stop_after="export"), source="existing", runner=runner)
        prepare.assert_called_once_with("existing", zip_path=None)

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
        with patch("pipelines.dataset_generation.cli.run_pipeline", side_effect=DatasetStageError("catalog", ["stage"], subprocess.CalledProcessError(1, ["stage"]))), patch.object(
            cli, "settings", SimpleNamespace(tmdb_bearer_token=None)
        ):
            self.assertEqual(1, cli.main([
                "--non-interactive", "--yes", "--source", "existing", "--start-at", "catalog", "--skip-posters",
            ]))

    def test_force_tmdb_is_reflected_once_in_stage_command(self) -> None:
        command = build_stage_command("enrich", DatasetPipelineConfig(force_tmdb=True, resume_tmdb=False))
        self.assertIn("--force", command)
        self.assertNotIn("--resume", command)

    def test_minimum_tags_is_optional_and_reaches_candidate_command(self) -> None:
        config = DatasetPipelineConfig(candidate_min_tags=0)
        self.assertIn("--min-tags", build_stage_command("candidates", config))
        with self.assertRaises(ValueError):
            cli.validate_config(DatasetPipelineConfig(candidate_min_tags=-1))

    def test_legacy_downloader_force_requests_fresh_source(self) -> None:
        paths = MovieLensSourcePaths(Path("/tmp/raw/ml-32m"), Path("/tmp/raw/ml-32m.zip"))
        with patch.object(sys, "argv", ["download_movielens_32m", "--force"]), patch(
            "pipelines.dataset_generation.download_movielens_32m.default_paths", return_value=paths
        ), patch(
            "pipelines.dataset_generation.download_movielens_32m.prepare_source", return_value="downloaded official MovieLens ZIP"
        ) as prepare:
            download_movielens_32m.main()
        prepare.assert_called_once_with("download", paths=paths, force=True)

    def test_stage_failures_identify_the_stage(self) -> None:
        config = DatasetPipelineConfig(start_at="catalog", stop_after="catalog")
        for failure in (subprocess.CalledProcessError(2, ["catalog"]), OSError("cannot start")):
            with self.subTest(failure=type(failure).__name__):
                with self.assertRaises(DatasetStageError) as raised:
                    run_pipeline(config, runner=Mock(side_effect=failure))
                self.assertEqual("catalog", raised.exception.stage)


class MovieLensSourceTests(unittest.TestCase):
    def test_valid_nested_zip_recognition_and_safe_import(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive = root / "source.zip"
            _write_zip(archive, {f"nested/ml-32m/{name}": name.encode() for name in _required_names()})
            paths = MovieLensSourcePaths(root / "raw" / "ml-32m", root / "raw" / "ml-32m.zip")
            self.assertEqual(set(_required_names()), set(inspect_zip(archive)))
            self.assertIsNone(import_zip(archive, paths=paths))
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

    def test_cached_and_fresh_download_outcomes_and_force(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            paths = MovieLensSourcePaths(root / "raw" / "ml-32m", root / "raw" / "ml-32m.zip")
            paths.zip_path.parent.mkdir(parents=True)
            _write_zip(paths.zip_path, {f"ml-32m/{name}": b"cached" for name in _required_names()})
            self.assertEqual("reused cached ZIP", prepare_source("download", paths=paths))
            downloader = Mock(side_effect=lambda _url, target: _write_zip(target, {f"ml-32m/{name}": b"fresh" for name in _required_names()}))
            self.assertEqual("downloaded official MovieLens ZIP", prepare_source("download", paths=paths, force=True, download=downloader))
            downloader.assert_called_once()

    def test_invalid_cached_zip_replaces_only_after_valid_download(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            paths = MovieLensSourcePaths(root / "raw" / "ml-32m", root / "raw" / "ml-32m.zip")
            paths.zip_path.parent.mkdir(parents=True)
            paths.zip_path.write_bytes(b"bad cached zip")
            downloader = Mock(side_effect=lambda _url, target: _write_zip(target, {f"ml-32m/{name}": b"new" for name in _required_names()}))
            self.assertEqual("downloaded official MovieLens ZIP", prepare_source("download", paths=paths, download=downloader))
            self.assertEqual(set(_required_names()), set(inspect_zip(paths.zip_path)))
            paths.zip_path.write_bytes(b"old cache")
            with self.assertRaises(MovieLensSourceError):
                prepare_source("download", paths=MovieLensSourcePaths(root / "other" / "ml-32m", paths.zip_path), download=Mock(side_effect=OSError("offline")))
            self.assertEqual(b"old cache", paths.zip_path.read_bytes())

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
