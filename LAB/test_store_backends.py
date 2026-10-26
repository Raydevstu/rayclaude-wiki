import pytest

from tier1.store import Store, build_store


def test_missing_database_url_preserves_sqlite_default(tmp_path):
    store = build_store("", str(tmp_path / "state.db"))
    assert isinstance(store, Store)
    store.run_start("run-1", "hello", "test")
    assert store.run_get("run-1")["status"] == "running"


def test_invalid_database_url_fails_closed():
    with pytest.raises(ValueError, match="PostgreSQL connection URL"):
        build_store("mysql://example", "unused.db")
