from pathlib import Path

import pytest

from config_loader import load_guard_config
from quickwin_cli import main
from repository_adapter import inspect_repository


def test_repository_adapter_reports_non_git_workspace():
    identity = inspect_repository(Path(__file__).resolve().parents[1])
    assert identity.root.endswith("Rayclaude-wiki")
    assert identity.is_git is False
    assert identity.branch == "unavailable"


def test_config_loader_accepts_scoped_thresholds(tmp_path):
    config = tmp_path / "guards.toml"
    config.write_text('[scope]\nmax_files = 3\nmax_changed_lines = 20\nrisk = "medium"\n', encoding="utf-8")
    result = load_guard_config(config)
    assert (result.max_files, result.max_changed_lines, result.risk) == (3, 20, "medium")


def test_config_loader_rejects_invalid_risk(tmp_path):
    config = tmp_path / "guards.toml"
    config.write_text('risk = "unsafe"\n', encoding="utf-8")
    with pytest.raises(ValueError):
        load_guard_config(config)


def test_quickwin_cli_is_read_only(capsys):
    assert main([str(Path(__file__).resolve().parents[1])]) == 0
    assert "repository" in capsys.readouterr().out
