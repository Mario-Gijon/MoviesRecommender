import tempfile
import unittest
import os
from pathlib import Path
from unittest.mock import Mock, patch

from app.core.config import settings
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
            ), patch("pipelines.recommender_build.cli.validate_staged"), patch("pipelines.recommender_build.cli.promote") as promote:
                cli.build_selected(("item_knn", "biased"), paths)
            self.assertEqual(100, item.call_args_list[0].args[0].top_k)
            self.assertNotEqual(item.call_args.kwargs["offline_context"].collaborative_model_artifact_root, paths.collaborative_root)
            self.assertEqual(["item_knn", "biased"], list(promote.call_args.args[0]))

    def test_promotion_replaces_selected_target_and_cleans_backup(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            paths = _paths(Path(temporary))
            plan = cli.ResolvedBuildPlan(("tfidf",))
            paths.content_root.mkdir(parents=True)
            (paths.content_root / "value").write_text("old", encoding="utf-8")
            staged = Path(temporary) / "stage" / "content_based"
            staged.mkdir(parents=True)
            (staged / "value").write_text("new", encoding="utf-8")
            cli.promote(("tfidf",), plan, staged, staged.parent / "collaborative", paths)
            self.assertEqual("new", (paths.content_root / "value").read_text(encoding="utf-8"))
            self.assertFalse(any(paths.temp_root.iterdir()) if paths.temp_root.exists() else False)

    def test_failed_backup_keeps_original_target_untouched(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            paths = _paths(Path(temporary))
            plan = cli.ResolvedBuildPlan(("tfidf",))
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
                    cli.promote(("tfidf",), plan, staged, staged.parent / "collaborative", paths)
            self.assertEqual("old", (paths.content_root / "value").read_text(encoding="utf-8"))


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
