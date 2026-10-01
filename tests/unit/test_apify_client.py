from __future__ import annotations

from unittest.mock import patch

import pytest
from src.integrations.apify_client import ApifyRunner, ApifyIntegrationError


class FakeApifyClient:
    """Test double for ApifyClient."""

    def __init__(self, token: str) -> None:
        self.token = token
        self.actor_calls = []
        self.dataset_iterations = []

    def actor(self, actor_id: str) -> FakeActorClient:
        call = FakeActorClient(actor_id)
        self.actor_calls.append((actor_id, call))
        return call

    def dataset(self, dataset_id: str) -> FakeDatasetClient:
        return FakeDatasetClient(dataset_id, self.dataset_iterations)


class FakeActorClient:
    def __init__(self, actor_id: str) -> None:
        self.actor_id = actor_id
        self.calls = []

    def call(
        self,
        run_input: dict,
        **kwargs: object,
    ) -> FakeRun:
        self.calls.append((run_input, kwargs))
        return FakeRun()


class FakeDatasetClient:
    def __init__(self, dataset_id: str, iterations: list) -> None:
        self.dataset_id = dataset_id
        self.iterations = iterations

    def iterate_items(self) -> iter:
        return iter(self.iterations)


class FakeRun:
    """Emulates the v3 SDK typed Run response."""

    default_dataset_id = "dataset-123"


class FakeRunWithoutDataset:
    """Emulates a Run with no default dataset."""

    default_dataset_id = None


class FakeActorClientWithRun:
    def __init__(self) -> None:
        self.calls = []

    def call(self, run_input: dict, **kwargs: object) -> FakeRunWithoutDataset:
        self.calls.append((run_input, kwargs))
        return FakeRunWithoutDataset()


def test_apify_runner_initializes_with_token(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_client = FakeApifyClient("test-token")
    monkeypatch.setattr("src.integrations.apify_client.ApifyClient", lambda _: fake_client)
    monkeypatch.setattr("os.getenv", lambda k, _="": {
        "APIFY_API_TOKEN": "test-token",
        "OPENROUTER_API_KEY": "test",
        "TAVILY_API_KEY": "test",
        "EXA_API_KEY": "test",
        "OPENROUTER_MODEL": "test",
        "OPENMONTAGE_PATH": "/test",
        "CROWDWISDOM_URL": "https://test",
    }[k])

    runner = ApifyRunner()

    assert runner.client is fake_client


def test_apify_runner_initializes_with_real_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("src.integrations.apify_client.os.getenv", lambda k, _="": {
        "APIFY_API_TOKEN": "real-token",
        "OPENROUTER_API_KEY": "test",
        "TAVILY_API_KEY": "test",
        "EXA_API_KEY": "test",
        "OPENROUTER_MODEL": "test",
        "OPENMONTAGE_PATH": "/test",
        "CROWDWISDOM_URL": "https://test",
    }[k])

    with patch("src.integrations.apify_client.ApifyClient") as mock_apify:
        monkeypatch.setattr("src.integrations.apify_client.ApifyClient", mock_apify)

        runner = ApifyRunner()

        assert runner.client is mock_apify.return_value


def test_apify_runner_raises_when_token_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("src.integrations.apify_client.os.getenv", lambda k, _="": {
        "APIFY_API_TOKEN": "",
        "OPENROUTER_API_KEY": "test",
        "TAVILY_API_KEY": "test",
        "EXA_API_KEY": "test",
        "OPENROUTER_MODEL": "test",
        "OPENMONTAGE_PATH": "/test",
        "CROWDWISDOM_URL": "https://test",
    }[k])

    with pytest.raises(ApifyIntegrationError, match="APIFY_API_TOKEN is missing"):
        ApifyRunner()


def test_apify_runner_calls_actor_and_gets_items(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_client = FakeApifyClient("test-token")
    fake_client.dataset_iterations.append({"id": 1, "text": "Ad 1"})
    fake_client.dataset_iterations.append({"id": 2, "text": "Ad 2"})

    monkeypatch.setattr("src.integrations.apify_client.ApifyClient", lambda _: fake_client)
    monkeypatch.setattr("src.integrations.apify_client.os.getenv", lambda k, _="": {
        "APIFY_API_TOKEN": "test-token",
        "OPENROUTER_API_KEY": "test",
        "TAVILY_API_KEY": "test",
        "EXA_API_KEY": "test",
        "OPENROUTER_MODEL": "test",
        "OPENMONTAGE_PATH": "/test",
        "CROWDWISDOM_URL": "https://test",
    }[k])

    runner = ApifyRunner()
    result = runner.run_actor(
        actor_id="test-actor",
        run_input={"source": "scrape"},
        timeout_secs=300,
    )

    assert result == [{"id": 1, "text": "Ad 1"}, {"id": 2, "text": "Ad 2"}]


def test_apify_runner_raises_on_missing_dataset_id(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_client = FakeApifyClient("test-token")
    fake_client.actor = lambda actor_id: FakeActorClientWithRun()

    monkeypatch.setattr("src.integrations.apify_client.ApifyClient", lambda _: fake_client)
    monkeypatch.setattr("src.integrations.apify_client.os.getenv", lambda k, _="": {
        "APIFY_API_TOKEN": "test-token",
        "OPENROUTER_API_KEY": "test",
        "TAVILY_API_KEY": "test",
        "EXA_API_KEY": "test",
        "OPENROUTER_MODEL": "test",
        "OPENMONTAGE_PATH": "/test",
        "CROWDWISDOM_URL": "https://test",
    }[k])

    runner = ApifyRunner()

    with pytest.raises(ApifyIntegrationError, match="without a dataset"):
        runner.run_actor(
            actor_id="test-actor",
            run_input={},
            timeout_secs=300,
        )


def test_apify_runner_raises_on_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("src.integrations.apify_client.ApifyClient", lambda _: None)
    monkeypatch.setattr("src.integrations.apify_client.os.getenv", lambda k, _="": {
        "APIFY_API_TOKEN": "test-token",
        "OPENROUTER_API_KEY": "test",
        "TAVILY_API_KEY": "test",
        "EXA_API_KEY": "test",
        "OPENROUTER_MODEL": "test",
        "OPENMONTAGE_PATH": "/test",
        "CROWDWISDOM_URL": "https://test",
    }[k])

    with pytest.raises(ApifyIntegrationError, match="failed"):
        ApifyRunner().run_actor("test-actor", {})


if __name__ == "__main__":
    pytest.main([__file__, "-v"])