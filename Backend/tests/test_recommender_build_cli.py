import tempfile
import unittest
import os
import errno
from io import StringIO
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

from app.core.config import settings
from app.recommenders.artifact_policy import (
    optional_artifacts,
    remove_optional_artifacts,
    required_artifacts,
    validate_runtime_artifacts,
)
from app.recommenders.content_based.build_content_index import build_content_index
from pipelines.recommender_build import cli
from app.recommenders.build_profiles import (
    DEFAULT_BIASED_MATRIX_FACTORIZATION_VARIANT_ID,
    DEFAULT_ITEM_KNN_VARIANT_ID,
    get_item_knn_variant_profile,
    get_supported_item_knn_profiles,
)


class RecommenderBuildCliTests(unittest.TestCase):
    def test_default_and_repeated_selections_use_canonical_order(self) -> None:
        self.assertEqual(cli.ALGORITHM_ORDER, cli.select_algorithms(None))
        self.assertEqual(("item_knn", "biased"), cli.select_algorithms(["biased", "item_knn", "item_knn"]))

    def test_all_cannot_be_combined(self) -> None:
        with self.assertRaises(cli.RecommenderBuildError):
            cli.select_algorithms(["all", "tfidf"])

    def test_profile_variants_match_runtime_settings(self) -> None:
        with patch.object(cli.settings, "active_collaborative_model_variant", DEFAULT_ITEM_KNN_VARIANT_ID), patch.object(
            cli.settings, "biased_matrix_factorization_model_variant", DEFAULT_BIASED_MATRIX_FACTORIZATION_VARIANT_ID
        ):
            cli.validate_runtime_profile(("item_knn", "biased"))

    def test_catalogue_has_recommended_100_and_supported_50(self) -> None:
        profiles = get_supported_item_knn_profiles()
        self.assertEqual(("top_k_100_min_support_25", "top_k_50_min_support_25"), tuple(p.variant_id for p in profiles))
        self.assertTrue(profiles[0].recommended)
        self.assertEqual(profiles[0].variant_id, DEFAULT_ITEM_KNN_VARIANT_ID)
        self.assertEqual("top_k_50_min_support_25", get_item_knn_variant_profile("top_k_50_min_support_25").build_config(overwrite=True).variant_id)

    def test_selected_resolution_uses_active_50_and_ignores_unselected_variants(self) -> None:
        with patch.object(cli.settings, "active_collaborative_model_variant", "top_k_50_min_support_25"):
            plan = cli.resolve_plan(("item_knn",))
        self.assertEqual("top_k_50_min_support_25", plan.item_knn_variant_id)
        self.assertEqual(50, get_item_knn_variant_profile(plan.item_knn_variant_id).top_k)
        with patch.object(cli.settings, "active_collaborative_model_variant", "unsupported"):
            self.assertEqual(("tfidf",), cli.resolve_plan(("tfidf",)).algorithms)
            with self.assertRaises(cli.RecommenderBuildError):
                cli.resolve_plan(("item_knn",))

    def test_variant_mismatch_fails_before_build(self) -> None:
        with patch.object(cli.settings, "active_collaborative_model_variant", "wrong"):
            with self.assertRaises(cli.RecommenderBuildError):
                cli.validate_runtime_profile(("item_knn",))

    def test_tfidf_preflight_does_not_require_collaborative_csvs(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            paths = _paths(Path(temporary))
            _write_public(paths.public_movies)
            cli.preflight(("tfidf",), paths)
            cli.preflight(("popularity",), paths)

    def test_collaborative_preflight_requires_all_collaborative_csvs(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            paths = _paths(Path(temporary))
            _write_public(paths.public_movies)
            with self.assertRaises(cli.RecommenderBuildError):
                cli.preflight(("item_knn",), paths)
            _write_support(paths.support_movies)
            _write_ratings(paths.ratings)
            cli.preflight(("item_knn",), paths)

    def test_empty_input_fails_before_staging(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            paths = _paths(Path(temporary))
            paths.public_movies.parent.mkdir(parents=True)
            paths.public_movies.write_text("movieId,displayTitle,genres,suitabilityCategory,standDisplayScore\n", encoding="utf-8")
            with self.assertRaises(cli.RecommenderBuildError):
                cli.build_selected(("tfidf",), paths)
            self.assertFalse(any(paths.temp_root.iterdir()) if paths.temp_root.exists() else False)

    def test_dry_run_is_read_only_and_noninteractive_needs_yes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            paths = _paths(Path(temporary))
            _write_public(paths.public_movies)
            with patch("pipelines.recommender_build.cli.default_paths", return_value=paths):
                self.assertEqual(0, cli.main(["--algorithm", "tfidf", "--dry-run"]))
                self.assertEqual(1, cli.main(["--algorithm", "tfidf"]))
            self.assertFalse(paths.temp_root.exists())

    def test_content_builder_accepts_injected_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "public_movies.csv"
            source.write_text(
                "movieId,displayTitle,genres,suitabilityCategory,standDisplayScore\n"
                "1,First,Drama,general,50\n2,Second,Drama,general,60\n",
                encoding="utf-8",
            )
            output = root / "content"
            build_content_index(public_movies_path=source, output_dir=output)
            self.assertTrue((output / "movie_content_features.npz").is_file())
            self.assertFalse((root / "recommender_models").exists())

    def test_artifact_policy_matches_runtime_and_clean_removes_only_optional_files(self) -> None:
        self.assertEqual(
            ("model_manifest.json", "ranking.sqlite"),
            required_artifacts("popularity"),
        )
        self.assertEqual(
            ("user_factors.npy", "user_biases.csv", "user_index.csv"),
            optional_artifacts("biased"),
        )
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary)
            for name in (*required_artifacts("tfidf"), *optional_artifacts("tfidf")):
                (target / name).write_text("artifact", encoding="utf-8")
            self.assertEqual(("content_index_summary.json",), remove_optional_artifacts("tfidf", target))
            validate_runtime_artifacts("tfidf", target)
            self.assertFalse((target / "content_index_summary.json").exists())

    def test_selected_builds_receive_staging_context_in_canonical_order(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            paths = _paths(Path(temporary))
            _write_public(paths.public_movies)
            _write_support(paths.support_movies)
            _write_ratings(paths.ratings)
            item = Mock()
            biased = Mock()
            with patch.object(cli.settings, "active_collaborative_model_variant", DEFAULT_ITEM_KNN_VARIANT_ID), patch.object(
                cli.settings, "biased_matrix_factorization_model_variant", DEFAULT_BIASED_MATRIX_FACTORIZATION_VARIANT_ID
            ), patch("pipelines.recommender_build.cli.build_item_knn_cosine_model", item), patch(
                "pipelines.recommender_build.cli.build_biased_matrix_factorization_model", biased
            ), patch("pipelines.recommender_build.cli.validate_staged"), patch(
                "pipelines.recommender_build.cli.validate_runtime_artifacts"
            ), patch("pipelines.recommender_build.cli.replace_target") as replace_target:
                cli.build_selected(("item_knn", "biased"), paths)
            self.assertEqual(100, item.call_args_list[0].args[0].top_k)
            self.assertNotEqual(item.call_args.kwargs["offline_context"].collaborative_model_artifact_root, paths.collaborative_root)
            self.assertEqual(2, replace_target.call_count)

    def test_replacement_replaces_target_and_cleans_sibling_backup(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            paths = _paths(Path(temporary))
            paths.content_root.mkdir(parents=True)
            (paths.content_root / "value").write_text("old", encoding="utf-8")
            staged = Path(temporary) / "stage" / "content_based"
            staged.mkdir(parents=True)
            (staged / "value").write_text("new", encoding="utf-8")
            cli.replace_target(staged, paths.content_root)
            self.assertEqual("new", (paths.content_root / "value").read_text(encoding="utf-8"))
            self.assertFalse((paths.content_root.parent / ".content_based.recommender-build-backup").exists())

    def test_failed_backup_keeps_original_target_untouched(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            paths = _paths(Path(temporary))
            paths.content_root.mkdir(parents=True)
            (paths.content_root / "value").write_text("old", encoding="utf-8")
            staged = Path(temporary) / "stage" / "content_based"
            staged.mkdir(parents=True)
            real_replace = os.replace
            def fail_backup(source, target):
                if Path(source) == paths.content_root:
                    raise OSError("backup failure")
                return real_replace(source, target)
            with patch("pipelines.recommender_build.cli.os.replace", side_effect=fail_backup):
                with self.assertRaises(cli.RecommenderPromotionError):
                    cli.replace_target(staged, paths.content_root)
            self.assertEqual("old", (paths.content_root / "value").read_text(encoding="utf-8"))

    def test_transient_backup_rename_retries_and_then_installs(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            production = root / "target"
            production.mkdir()
            (production / "value").write_text("old", encoding="utf-8")
            staged = root / "staged"
            staged.mkdir()
            (staged / "value").write_text("new", encoding="utf-8")
            real_replace = os.replace
            attempts = 0

            def transient_backup_lock(source, target):
                nonlocal attempts
                if Path(source) == production and Path(target).name.startswith(".target"):
                    attempts += 1
                    if attempts == 1:
                        raise PermissionError(errno.EACCES, "sharing violation")
                return real_replace(source, target)

            with patch("pipelines.recommender_build.cli.os.replace", side_effect=transient_backup_lock), patch(
                "pipelines.recommender_build.cli.time.sleep"
            ):
                cli.replace_target(staged, production)
            self.assertEqual(2, attempts)
            self.assertEqual("new", (production / "value").read_text(encoding="utf-8"))

    def test_backup_copy_is_verified_before_production_is_removed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            production = root / "target"
            production.mkdir()
            (production / "value").write_text("old", encoding="utf-8")
            staged = root / "staged"
            staged.mkdir()
            (staged / "value").write_text("new", encoding="utf-8")
            backup = root / ".target.recommender-build-backup"
            real_replace = os.replace
            real_copytree = cli.shutil.copytree

            def reject_backup_rename(source, target):
                if Path(source) == production and Path(target) == backup:
                    raise PermissionError(errno.EACCES, "sharing violation")
                return real_replace(source, target)

            def copy_backup(source, target, *args, **kwargs):
                result = real_copytree(source, target, *args, **kwargs)
                if Path(source) == production:
                    self.assertTrue(production.exists())
                    self.assertEqual("old", (target / "value").read_text(encoding="utf-8"))
                return result

            with patch("pipelines.recommender_build.cli.os.replace", side_effect=reject_backup_rename), patch(
                "pipelines.recommender_build.cli.shutil.copytree", side_effect=copy_backup
            ), patch("pipelines.recommender_build.cli.time.sleep"):
                cli.replace_target(staged, production)
            self.assertEqual("new", (production / "value").read_text(encoding="utf-8"))

    def test_failed_backup_copy_leaves_original_model_intact(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            production = root / "target"
            production.mkdir()
            (production / "value").write_text("old", encoding="utf-8")
            staged = root / "staged"
            staged.mkdir()
            backup = root / ".target.recommender-build-backup"
            real_replace = os.replace

            def reject_backup_rename(source, target):
                if Path(source) == production:
                    raise PermissionError(errno.EACCES, "sharing violation")
                return real_replace(source, target)

            with patch("pipelines.recommender_build.cli.os.replace", side_effect=reject_backup_rename), patch(
                "pipelines.recommender_build.cli.shutil.copytree", side_effect=OSError("copy failure")
            ), patch("pipelines.recommender_build.cli.time.sleep"):
                with self.assertRaises(cli.RecommenderPromotionError):
                    cli.replace_target(staged, production)
            self.assertEqual("old", (production / "value").read_text(encoding="utf-8"))
            self.assertFalse(backup.exists())

    def test_verified_backup_is_retained_when_production_cannot_be_removed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            production = root / "target"
            production.mkdir()
            (production / "value").write_text("old", encoding="utf-8")
            staged = root / "staged"
            staged.mkdir()
            backup = root / ".target.recommender-build-backup"
            real_replace = os.replace

            def reject_backup_rename(source, target):
                if Path(source) == production:
                    raise PermissionError(errno.EACCES, "sharing violation")
                return real_replace(source, target)

            def cannot_remove_production(path):
                if path == production:
                    raise PermissionError(errno.EACCES, "still locked")
                raise AssertionError("unexpected removal")

            with patch("pipelines.recommender_build.cli.os.replace", side_effect=reject_backup_rename), patch(
                "pipelines.recommender_build.cli._remove_target", side_effect=cannot_remove_production
            ), patch("pipelines.recommender_build.cli.time.sleep"):
                with self.assertRaises(cli.RecommenderPromotionError) as raised:
                    cli.replace_target(staged, production)
            self.assertIn(str(backup), str(raised.exception))
            self.assertEqual("old", (production / "value").read_text(encoding="utf-8"))
            self.assertEqual("old", (backup / "value").read_text(encoding="utf-8"))

    def test_stale_backup_blocks_replacement_without_touching_original(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            production = root / "target"
            production.mkdir()
            (production / "value").write_text("old", encoding="utf-8")
            staged = root / "staged"
            staged.mkdir()
            (root / ".target.recommender-build-backup").mkdir()
            with self.assertRaises(cli.RecommenderPromotionError):
                cli.replace_target(staged, production)
            self.assertEqual("old", (production / "value").read_text(encoding="utf-8"))

    def test_windows_like_staged_rename_uses_verified_copy_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            production = root / "target"
            staged = root / "staged"
            staged.mkdir()
            (staged / "nested").mkdir()
            (staged / "nested" / "artifact").write_text("new", encoding="utf-8")
            real_replace = os.replace

            def windows_lock(source, target):
                if Path(source) == staged and Path(target) == production:
                    raise PermissionError(errno.EACCES, "sharing violation")
                return real_replace(source, target)

            with patch("pipelines.recommender_build.cli.os.replace", side_effect=windows_lock), patch(
                "pipelines.recommender_build.cli.time.sleep"
            ):
                cli.replace_target(staged, production)
            self.assertEqual("new", (production / "nested" / "artifact").read_text(encoding="utf-8"))

    def test_copy_fallback_preserves_old_model_until_new_model_is_installed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            production = root / "target"
            production.mkdir()
            (production / "value").write_text("old", encoding="utf-8")
            staged = root / "staged"
            staged.mkdir()
            (staged / "value").write_text("new", encoding="utf-8")
            real_replace = os.replace

            def windows_lock(source, target):
                if Path(source) == staged:
                    raise PermissionError(errno.EACCES, "sharing violation")
                return real_replace(source, target)

            with patch("pipelines.recommender_build.cli.os.replace", side_effect=windows_lock), patch(
                "pipelines.recommender_build.cli.time.sleep"
            ):
                cli.replace_target(staged, production)
            self.assertEqual("new", (production / "value").read_text(encoding="utf-8"))
            self.assertFalse((root / ".target.recommender-build-backup").exists())

    def test_failed_copy_fallback_restores_old_model(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            production = root / "target"
            production.mkdir()
            (production / "value").write_text("old", encoding="utf-8")
            staged = root / "staged"
            staged.mkdir()
            (staged / "value").write_text("new", encoding="utf-8")
            real_replace = os.replace

            def windows_lock(source, target):
                if Path(source) == staged:
                    raise PermissionError(errno.EACCES, "sharing violation")
                return real_replace(source, target)

            def incomplete_copy(source, target, *args, **kwargs):
                Path(target).mkdir()
                (Path(target) / "value").write_text("partial", encoding="utf-8")
                raise OSError("copy interrupted")

            with patch("pipelines.recommender_build.cli.os.replace", side_effect=windows_lock), patch(
                "pipelines.recommender_build.cli.shutil.copytree", side_effect=incomplete_copy
            ), patch("pipelines.recommender_build.cli.time.sleep"):
                with self.assertRaises(cli.RecommenderPromotionError):
                    cli.replace_target(staged, production)
            self.assertEqual("old", (production / "value").read_text(encoding="utf-8"))

    def test_failed_copy_without_old_model_leaves_no_partial_target(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            production = root / "target"
            staged = root / "staged"
            staged.mkdir()
            (staged / "value").write_text("new", encoding="utf-8")

            def incomplete_copy(source, target, *args, **kwargs):
                Path(target).mkdir()
                raise OSError("copy interrupted")

            with patch("pipelines.recommender_build.cli.os.replace", side_effect=PermissionError(errno.EACCES, "locked")), patch(
                "pipelines.recommender_build.cli.shutil.copytree", side_effect=incomplete_copy
            ), patch("pipelines.recommender_build.cli.time.sleep"):
                with self.assertRaises(cli.RecommenderPromotionError):
                    cli.replace_target(staged, production)
            self.assertFalse(production.exists())

    def test_sqlite_validation_explicitly_closes_connection(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            database = Path(temporary) / "artifact.sqlite"
            database.write_bytes(b"x")
            connection = MagicMock()
            connection.execute.side_effect = [Mock(fetchall=Mock(return_value=[("ratings",)])), Mock(fetchone=Mock(return_value=(1,)))]
            with patch("pipelines.recommender_build.cli.sqlite3.connect", return_value=connection):
                cli._sqlite_has_row(database)
            connection.close.assert_called_once_with()

    def test_promotion_error_includes_filesystem_diagnostics(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            production = root / "target"
            production.mkdir()
            staged = root / "staged"
            staged.mkdir()
            error = OSError(errno.EIO, "input/output failure")
            with patch("pipelines.recommender_build.cli.os.replace", side_effect=error):
                with self.assertRaises(cli.RecommenderPromotionError) as raised:
                    cli.replace_target(staged, production)
            self.assertIn("exception=OSError", str(raised.exception))
            self.assertIn("errno=5", str(raised.exception))
            self.assertIn(str(production), str(raised.exception))

    def test_residual_backup_after_success_is_warning_not_failure(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            production = root / "target"
            production.mkdir()
            (production / "value").write_text("old", encoding="utf-8")
            staged = root / "staged"
            staged.mkdir()
            (staged / "value").write_text("new", encoding="utf-8")
            backup = root / ".target.recommender-build-backup"
            real_rmtree = cli.shutil.rmtree

            def cannot_remove_backup(path, *args, **kwargs):
                if Path(path) == backup:
                    raise PermissionError(errno.EACCES, "locked")
                return real_rmtree(path, *args, **kwargs)

            stderr = StringIO()
            with patch("pipelines.recommender_build.cli.shutil.rmtree", side_effect=cannot_remove_backup), patch(
                "pipelines.recommender_build.cli.sys.stderr", stderr
            ):
                cli.replace_target(staged, production)
            self.assertEqual("new", (production / "value").read_text(encoding="utf-8"))
            self.assertTrue(backup.exists())
            self.assertIn("Warning: installed", stderr.getvalue())

    def test_recovery_backup_without_production_is_never_deleted_automatically(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            production = root / "target"
            staged = root / "staged"
            staged.mkdir()
            backup = root / ".target.recommender-build-backup"
            backup.mkdir()
            (backup / "value").write_text("recoverable", encoding="utf-8")
            with self.assertRaises(cli.RecommenderPromotionError) as raised:
                cli.replace_target(staged, production)
            self.assertIn("production is absent", str(raised.exception))
            self.assertEqual("recoverable", (backup / "value").read_text(encoding="utf-8"))

    def test_sequential_build_keeps_completed_target_when_later_build_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            paths = _paths(Path(temporary))
            plan = cli.ResolvedBuildPlan(("tfidf", "popularity", "user_knn"))
            built: list[str] = []

            def build(algorithm, resolved_plan, build_paths, content_root, collaborative_root):
                built.append(algorithm)
                target = cli.targets_for(
                    algorithm, resolved_plan, content_root=content_root, collaborative_root=collaborative_root
                )
                if algorithm == "popularity":
                    raise RuntimeError("simulated later failure")
                target.mkdir(parents=True)
                for name in required_artifacts(algorithm):
                    (target / name).write_text("artifact", encoding="utf-8")

            with patch("pipelines.recommender_build.cli._build_algorithm", side_effect=build), patch(
                "pipelines.recommender_build.cli.validate_staged"
            ):
                with self.assertRaises(cli.RecommenderBuildStageError):
                    cli.execute_plan(plan, paths)
            self.assertTrue(paths.content_root.is_dir())
            self.assertFalse((paths.collaborative_root / "popularity_baseline" / "default").exists())
            self.assertEqual(["tfidf", "popularity"], built)

    def test_clean_removes_optional_artifacts_before_install(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            paths = _paths(Path(temporary))
            plan = cli.ResolvedBuildPlan(("tfidf",))

            def build(algorithm, resolved_plan, build_paths, content_root, collaborative_root):
                target = cli.targets_for(
                    algorithm, resolved_plan, content_root=content_root, collaborative_root=collaborative_root
                )
                target.mkdir(parents=True)
                for name in (*required_artifacts(algorithm), *optional_artifacts(algorithm)):
                    (target / name).write_text("artifact", encoding="utf-8")

            with patch("pipelines.recommender_build.cli._build_algorithm", side_effect=build), patch(
                "pipelines.recommender_build.cli.validate_staged"
            ):
                cli.execute_plan(plan, paths, clean=True)
            self.assertFalse((paths.content_root / "content_index_summary.json").exists())
            validate_runtime_artifacts("tfidf", paths.content_root)


def _paths(root: Path) -> cli.BuildPaths:
    offline = root / "offline_dataset" / "csv"
    return cli.BuildPaths(root, offline / "public_movies.csv", offline / "collaborative_support_movies.csv", offline / "collaborative_ratings.csv", root / "offline_dataset" / "manifest.json", root / "recommender_models", root / "recommender_models" / "content_based", root / "recommender_models" / "collaborative", root / "tmp")


def _write_public(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("movieId,displayTitle,genres,suitabilityCategory,standDisplayScore\n1,Movie,Drama,general,50\n", encoding="utf-8")


def _write_support(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("movieId\n1\n", encoding="utf-8")


def _write_ratings(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("userId,movieId,rating\n1,1,4\n", encoding="utf-8")
