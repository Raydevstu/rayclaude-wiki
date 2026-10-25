import pytest
from dataclasses import replace
from tier1 import config, services


@pytest.fixture
def settings(tmp_path):
    base = config.load()
    return replace(base, provider="mock", db_path=":memory:", sandbox_dir=str(tmp_path / "sb"),
                   skills_dir="skills", api_token="tok", webhook_secret="whsec", daily_budget_usd=100.0,
                   models={"small": "m-s", "medium": "m-m", "large": "m-l"})


@pytest.fixture
def svc(settings):
    return services.build(settings)
