"""Runtime dependency smoke checks for the API-image audit entrypoint."""

import unittest


class RecommenderAuditImportTests(unittest.TestCase):
    def test_audit_and_testclient_imports(self) -> None:
        from fastapi.testclient import TestClient
        from pipelines.recommender_evaluation import compare_collaborative_recommenders

        self.assertIsNotNone(TestClient)
        self.assertIsNotNone(compare_collaborative_recommenders)
