import tempfile
import unittest
from pathlib import Path

from pipelines.dataset_generation.cleanup import DatasetCleanupError, DatasetPaths, apply_cleanup


class DatasetCleanupTests(unittest.TestCase):
    def _fixture(self, root: Path) -> DatasetPaths:
        paths = DatasetPaths(root)
        for path in paths.required_files:
            path.parent.mkdir(parents=True, exist_ok=True); path.write_text("data", encoding="utf-8")
        paths.posters.mkdir(parents=True); (paths.posters / "poster.jpg").write_text("x", encoding="utf-8")
        for path in (root / "pipeline_cache", root / "raw", root / "offline_dataset" / "audit", root / "recommender_models"):
            path.mkdir(parents=True, exist_ok=True)
        return paths

    def test_modes_only_remove_known_paths_and_preserve_runtime_dataset(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            paths = self._fixture(Path(temporary)); apply_cleanup("standard", paths)
            self.assertFalse((paths.data_dir / "pipeline_cache").exists())
            self.assertFalse((paths.data_dir / "raw").exists())
            self.assertTrue((paths.offline / "audit").exists())
            paths = self._fixture(Path(temporary) / "minimal"); apply_cleanup("minimal", paths)
            self.assertFalse((paths.data_dir / "pipeline_cache").exists())
            self.assertFalse((paths.data_dir / "raw").exists())
            self.assertFalse((paths.offline / "audit").exists())
            self.assertTrue((paths.offline / "csv" / "public_movies.csv").exists())
            self.assertTrue(paths.posters.exists()); self.assertTrue((paths.data_dir / "recommender_models").exists())

    def test_removable_paths_preserve_runtime_dataset_components(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            paths = DatasetPaths(Path(temporary))
            cache = paths.data_dir / "pipeline_cache"
            raw = paths.data_dir / "raw"
            audit = paths.offline / "audit"

            self.assertEqual((), paths.removable("none"))
            self.assertEqual((cache, raw), paths.removable("standard"))
            self.assertEqual((cache, raw, audit), paths.removable("minimal"))

            protected = {paths.offline / "csv", paths.posters, paths.offline / "manifest.json", paths.data_dir / "recommender_models"}
            for mode in ("none", "standard", "minimal"):
                self.assertTrue(protected.isdisjoint(paths.removable(mode)))

    def test_invalid_dataset_blocks_cleanup_and_dry_run_keeps_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            paths = DatasetPaths(Path(temporary)); (paths.data_dir / "pipeline_cache").mkdir()
            with self.assertRaises(DatasetCleanupError): apply_cleanup("minimal", paths)
            self.assertTrue((paths.data_dir / "pipeline_cache").exists())
            paths = self._fixture(Path(temporary)); apply_cleanup("minimal", paths, dry_run=True)
            self.assertTrue((paths.data_dir / "raw").exists())
