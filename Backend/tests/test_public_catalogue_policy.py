from argparse import Namespace
import unittest

from app.catalog.filtering import build_public_exclusion_reasons, is_collaborative_candidate, is_public_candidate
from pipelines.dataset_generation.export_offline_dataset_from_movielens_32m import _build_catalog_index


def _args(**overrides):
    values = dict(min_ratings=100, public_min_year=2000, collaborative_min_year=1990, family_only=False, public_min_runtime=60)
    values.update(overrides)
    return Namespace(**values)


def _movie(*, genres, runtime, reasons=None):
    return {
        "ratingCount": 500, "year": 2020, "suitabilityCategory": "family_friendly",
        "standDisplayScore": 10, "publicBlockedTerms": [],
        "tmdb": {"posterPath": "/poster.jpg", "genres": genres, "runtime": runtime},
        "publicExclusionReasons": reasons or [],
    }


class PublicCataloguePolicyTests(unittest.TestCase):
    def test_documentary_is_excluded_from_public_but_remains_collaborative(self):
        movie = _movie(genres=["Documentary"], runtime=90)
        reasons = build_public_exclusion_reasons(movie, args=_args())
        self.assertIn("documentary", reasons)
        self.assertNotIn("short_runtime", reasons)
        self.assertFalse(is_public_candidate(movie, args=_args()))
        self.assertTrue(is_collaborative_candidate(movie, args=_args()))

    def test_short_runtime_is_excluded_from_public_but_remains_collaborative(self):
        movie = _movie(genres=["Drama"], runtime=59)
        reasons = build_public_exclusion_reasons(movie, args=_args())
        self.assertIn("short_runtime", reasons)
        self.assertNotIn("documentary", reasons)
        self.assertFalse(is_public_candidate(movie, args=_args()))
        self.assertTrue(is_collaborative_candidate(movie, args=_args()))

    def test_documentary_short_movie_has_both_reasons(self):
        reasons = build_public_exclusion_reasons(
            _movie(genres=["Documentary"], runtime=59), args=_args()
        )
        self.assertEqual(["documentary", "short_runtime"], reasons)

    def test_runtime_boundary_and_missing_runtime_remain_eligible(self):
        for runtime in (60, None):
            with self.subTest(runtime=runtime):
                movie = _movie(genres=["Drama"], runtime=runtime)
                self.assertNotIn("short_runtime", build_public_exclusion_reasons(movie, args=_args()))
                self.assertTrue(is_public_candidate(movie, args=_args()))

    def test_existing_reasons_are_preserved(self):
        movie = _movie(genres=["Documentary"], runtime=90)
        movie["publicBlockedTerms"] = ["existing"]
        reasons = build_public_exclusion_reasons(movie, args=_args())
        self.assertIn("blocked_public_topic", reasons)
        self.assertIn("documentary", reasons)

    def test_public_policy_exclusions_are_reported_without_losing_collaborative_support(self):
        item = {"movieId": 1, "title": "Documentary", "publicExclusionReasons": ["documentary"]}
        catalog_index = _build_catalog_index(
            {
                "publicCatalog": [],
                "collaborativeCore": [item],
                "excludedOrSensitive": [item],
            },
            ratings_summary_by_movie={},
            has_ratings_summary=False,
        )
        self.assertEqual([1], [item["movieId"] for item in catalog_index["collaborative_support_items"]])
        self.assertEqual([1], [item["movieId"] for item in catalog_index["excluded_items"]])
