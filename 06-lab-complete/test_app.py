"""Behavior tests for the completed production agent."""
import unittest

from fastapi.testclient import TestClient

from app.config import settings
from app.config import Settings
from app.cost_guard import _monthly_costs
from app.main import app
from app.rate_limiter import _windows
from app.storage import _memory_history


class ProductionAgentTests(unittest.TestCase):
    def setUp(self):
        _windows.clear()
        _monthly_costs.clear()
        _memory_history.clear()
        self.client = TestClient(app)
        self.client.__enter__()
        self.headers = {"X-API-Key": settings.agent_api_key}

    def tearDown(self):
        self.client.__exit__(None, None, None)

    def test_health_and_readiness(self):
        root = self.client.get("/")
        self.assertEqual(root.status_code, 200)
        self.assertIn("Production AI Agent", root.text)
        self.assertEqual(self.client.get("/health").status_code, 200)
        self.assertEqual(self.client.get("/ready").status_code, 200)

    def test_authentication(self):
        self.assertEqual(
            self.client.post("/ask", json={"user_id": "alice", "question": "hello"}).status_code,
            401,
        )
        self.assertEqual(
            self.client.post(
                "/ask", json={"user_id": "alice", "question": "hello"}, headers=self.headers
            ).status_code,
            200,
        )

    def test_input_validation(self):
        response = self.client.post(
            "/ask", json={"user_id": "alice", "question": ""}, headers=self.headers
        )
        self.assertEqual(response.status_code, 422)

    def test_rate_limit(self):
        original_limit = settings.rate_limit_per_minute
        settings.rate_limit_per_minute = 2
        try:
            for _ in range(2):
                response = self.client.post(
                    "/ask", json={"user_id": "alice", "question": "hello"}, headers=self.headers
                )
                self.assertEqual(response.status_code, 200)
            response = self.client.post(
                "/ask", json={"user_id": "alice", "question": "hello"}, headers=self.headers
            )
            self.assertEqual(response.status_code, 429)
        finally:
            settings.rate_limit_per_minute = original_limit

    def test_production_rejects_placeholder_secrets(self):
        production = Settings(environment="production")
        with self.assertRaises(ValueError):
            production.validate()

    def test_production_requires_redis(self):
        production = Settings(
            environment="production",
            agent_api_key="real-agent-secret",
            jwt_secret="real-jwt-secret",
            redis_url="",
        )
        with self.assertRaises(ValueError):
            production.validate()

    def test_conversation_history(self):
        first = self.client.post(
            "/ask",
            json={"user_id": "alice", "question": "My name is Alice"},
            headers=self.headers,
        )
        second = self.client.post(
            "/ask",
            json={"user_id": "alice", "question": "What did I just say?"},
            headers=self.headers,
        )
        history = self.client.get("/history/alice", headers=self.headers)
        self.assertEqual(first.status_code, 200)
        self.assertIn("My name is Alice", second.json()["answer"])
        self.assertEqual(len(history.json()["messages"]), 4)

    def test_monthly_cost_guard(self):
        original_budget = settings.monthly_budget_usd
        settings.monthly_budget_usd = 0.0
        try:
            response = self.client.post(
                "/ask",
                json={"user_id": "alice", "question": "hello"},
                headers=self.headers,
            )
            self.assertEqual(response.status_code, 402)
        finally:
            settings.monthly_budget_usd = original_budget


if __name__ == "__main__":
    unittest.main()
