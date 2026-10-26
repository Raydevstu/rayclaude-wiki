from dataclasses import replace

import pytest

from tier1 import config


def test_production_requires_postgres_and_api_token(settings):
    with pytest.raises(ValueError, match="PostgreSQL"):
        replace(settings, env="production", database_url="", api_token="token").validate_runtime()
    with pytest.raises(ValueError, match="API token"):
        replace(settings, env="production", database_url="postgresql://example/db", api_token="").validate_runtime()
    replace(settings, env="production", database_url="postgresql://example/db", api_token="token").validate_runtime()
