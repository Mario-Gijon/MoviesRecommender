import csv
import json
import tempfile
import unittest
from pathlib import Path

from pipelines.dataset_generation.export_offline_dataset_from_movielens_32m import (
    PUBLIC_MOVIE_COLUMNS, SUPPORT_MOVIE_COLUMNS,
)
from pipelines.dataset_generation.reconfigure_offline_dataset import reconfigure


class OfflineDatasetReconfigurationTests(unittest.TestCase):
    def test_legacy_repartition_is_reversible_and_preserves_non_public_teen(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "offline_dataset"
            csv_dir = root / "csv"; csv_dir.mkdir(parents=True)
            public = [_row("1", "family_friendly"), _row("2", "teen")]
            support = [_row("3", "teen", "below_min_ratings"), _row("4", "adult_or_sensitive", "adult_or_sensitive")]
            _write(csv_dir / "public_movies.csv", PUBLIC_MOVIE_COLUMNS, public)
            _write(csv_dir / "collaborative_support_movies.csv", SUPPORT_MOVIE_COLUMNS, support)
            _write(csv_dir / "excluded_movies.csv", SUPPORT_MOVIE_COLUMNS + ["exclusionCategory", "exclusionReasons"], [])
            _write(csv_dir / "movie_ratings_summary.csv", ["movieId"], [])
            _write(csv_dir / "collaborative_ratings.csv", ["movieId"], [])
            (root / "manifest.json").write_text(json.dumps({"counts": {}}), encoding="utf-8")
            ratings_before = (csv_dir / "collaborative_ratings.csv").read_bytes()

            family_only = reconfigure(root, "family_only")
            self.assertEqual((1, 3), (family_only.new_public_movies, family_only.new_support_movies))
            self.assertEqual(ratings_before, (csv_dir / "collaborative_ratings.csv").read_bytes())
            restored = reconfigure(root, "family_and_teen")
            self.assertEqual(2, restored.new_public_movies)
            self.assertEqual({"1", "2"}, _ids(csv_dir / "public_movies.csv"))
            self.assertEqual({"3", "4"}, _ids(csv_dir / "collaborative_support_movies.csv"))
            self.assertTrue((csv_dir / "catalog_movies.csv").exists())
            manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual("family_and_teen", manifest["publicAudiencePolicy"])

    def test_conflicting_legacy_duplicate_fails_without_changes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "offline_dataset"; csv_dir = root / "csv"; csv_dir.mkdir(parents=True)
            _write(csv_dir / "public_movies.csv", PUBLIC_MOVIE_COLUMNS, [_row("1", "family_friendly")])
            _write(csv_dir / "collaborative_support_movies.csv", SUPPORT_MOVIE_COLUMNS, [_row("1", "teen")])
            _write(csv_dir / "excluded_movies.csv", SUPPORT_MOVIE_COLUMNS + ["exclusionCategory", "exclusionReasons"], [])
            _write(csv_dir / "movie_ratings_summary.csv", ["movieId"], []); _write(csv_dir / "collaborative_ratings.csv", ["movieId"], [])
            (root / "manifest.json").write_text("{}", encoding="utf-8")
            before = (csv_dir / "public_movies.csv").read_bytes()
            with self.assertRaisesRegex(Exception, "duplicate movieId"):
                reconfigure(root, "family_only")
            self.assertEqual(before, (csv_dir / "public_movies.csv").read_bytes())

    def test_documentaries_and_short_movies_move_to_support_without_raw_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "offline_dataset"; csv_dir = root / "csv"; csv_dir.mkdir(parents=True)
            documentary = _row("1", "family_friendly"); documentary.update(genres="Documentary", runtime="90")
            short = _row("2", "family_friendly"); short.update(genres="Drama", runtime="59")
            regular = _row("3", "family_friendly"); regular.update(genres="Drama", runtime="60")
            _write(csv_dir / "public_movies.csv", PUBLIC_MOVIE_COLUMNS, [documentary, short, regular])
            _write(csv_dir / "collaborative_support_movies.csv", SUPPORT_MOVIE_COLUMNS, [])
            _write(csv_dir / "excluded_movies.csv", SUPPORT_MOVIE_COLUMNS + ["exclusionCategory", "exclusionReasons"], [])
            _write(csv_dir / "movie_ratings_summary.csv", ["movieId"], [])
            _write(csv_dir / "collaborative_ratings.csv", ["movieId"], [])
            (root / "manifest.json").write_text(json.dumps({"counts": {}}), encoding="utf-8")

            reconfigure(root, "family_and_teen")

            self.assertEqual({"3"}, _ids(csv_dir / "public_movies.csv"))
            self.assertEqual({"1", "2"}, _ids(csv_dir / "collaborative_support_movies.csv"))
            support_rows = _read_rows(csv_dir / "collaborative_support_movies.csv")
            self.assertEqual("documentary", support_rows["1"]["publicExclusionReasons"])
            self.assertEqual("short_runtime", support_rows["2"]["publicExclusionReasons"])


def _row(movie_id, suitability, reason=""):
    row = {column: "" for column in SUPPORT_MOVIE_COLUMNS}
    row.update(movieId=movie_id, title="Movie " + movie_id, cleanTitle="Movie " + movie_id, year="2020", ratingCount="100", standDisplayScore="10", suitabilityCategory=suitability, publicExclusionReasons=reason)
    return row


def _write(path, fields, rows):
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fields, extrasaction="ignore"); writer.writeheader(); writer.writerows(rows)


def _ids(path):
    with path.open(encoding="utf-8", newline="") as file:
        return {row["movieId"] for row in csv.DictReader(file)}


def _read_rows(path):
    with path.open(encoding="utf-8", newline="") as file:
        return {row["movieId"]: row for row in csv.DictReader(file)}
