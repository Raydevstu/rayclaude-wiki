"""Read-only Phase 1 CLI for repository identity and guard configuration."""

from __future__ import annotations

import argparse
import json

from config_loader import load_guard_config
from repository_adapter import inspect_repository


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="guard-quickwin")
    parser.add_argument("path", nargs="?", default=".")
    parser.add_argument("--config")
    args = parser.parse_args(argv)
    identity = inspect_repository(args.path)
    config = load_guard_config(args.config)
    print(json.dumps({"repository": identity.__dict__, "guard_config": config.__dict__}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
