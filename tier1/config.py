from __future__ import annotations
import os
from dataclasses import dataclass, field
from pathlib import Path


def _float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, default))
    except ValueError:
        return float(default)


def _price(tier: str, default: tuple[float, float]) -> tuple[float, float]:
    raw = os.getenv(f"TIER1_PRICE_{tier.upper()}", "")
    try:
        a, b = raw.split(",")
        return float(a), float(b)
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    env: str = "development"
    provider: str = "mock"            # mock | anthropic | openai | ollama
    api_key: str = ""
    base_url: str = ""
    models: dict = field(default_factory=dict)
    prices: dict = field(default_factory=dict)   # tier -> (usd per 1M input, usd per 1M output)
    db_path: str = "data/tier1.db"
    database_url: str = ""
    skills_dir: str = "skills"
    sandbox_dir: str = "sandbox"
    api_token: str = ""
    webhook_secret: str = ""
    audit_threshold: float = 0.85
    daily_budget_usd: float = 25.0
    http_allowlist: tuple = ("*",)
    cache_ttl: int = 3600
    max_concurrency: int = 8
    rate_limit_per_min: int = 60
    slack_signing_secret: str = ""
    slack_bot_token: str = ""
    notify_url: str = ""
    vault_dir: str = ""              # relative to sandbox_dir; auto-synced into notebook `vault`
    max_ralph_iterations: int = 3
    sandbox_writable: bool = False    # allow saving notes into the sandbox (compose mounts it read-only by default)
    memory_url: str = ""
    memory_authorization: str = ""
    memory_tenant_id: str = "staging-tenant"
    memory_bank_id: str = "staging-bank"
    memory_project_id: str = "Rayclaude-wiki"

    def validate_runtime(self) -> None:
        if self.env.lower() != "production":
            return
        if not self.database_url.startswith(("postgres://", "postgresql://")):
            raise ValueError("production requires a PostgreSQL TIER1_DATABASE_URL")
        if not self.api_token:
            raise ValueError("production requires an API token (TIER1_API_TOKEN)")


def load() -> Settings:
    provider = os.getenv("TIER1_PROVIDER", "mock").lower()
    defaults = {
        "anthropic": ("claude-haiku-5-5", "claude-sonnet-5-5", "claude-opus-5-5"),
        "openai": ("", "", ""),
        "ollama": ("llama3.2", "llama3.2", "llama3.2"),
        "mock": ("mock-small", "mock-medium", "mock-large"),
    }.get(provider, ("", "", ""))
    models = {t: os.getenv(f"TIER1_MODEL_{t.upper()}", d) for t, d in zip(("small", "medium", "large"), defaults)}
    prices = {"small": _price("small", (0.8, 4.0)), "medium": _price("medium", (3.0, 15.0)),
              "large": _price("large", (15.0, 75.0))}
    allow = tuple(x.strip() for x in os.getenv("TIER1_HTTP_ALLOWLIST", "*").split(",") if x.strip())
    return Settings(
        env=os.getenv("TIER1_ENV", "development"), provider=provider,
        api_key=os.getenv("TIER1_PROVIDER_API_KEY", os.getenv("ANTHROPIC_API_KEY", "")),
        base_url=os.getenv("TIER1_PROVIDER_BASE_URL", ""), models=models, prices=prices,
        db_path=os.getenv("TIER1_DB", str(Path(os.getenv("TIER1_HOME", ".")) / "data" / "tier1.db")),
        database_url=os.getenv("TIER1_DATABASE_URL", ""),
        skills_dir=os.getenv("TIER1_SKILLS_DIR", "skills"),
        sandbox_dir=os.getenv("TIER1_SANDBOX_DIR", "sandbox"),
        api_token=os.getenv("TIER1_API_TOKEN", ""), webhook_secret=os.getenv("TIER1_WEBHOOK_SECRET", ""),
        audit_threshold=_float("TIER1_AUDIT_THRESHOLD", 0.85),
        daily_budget_usd=_float("TIER1_DAILY_BUDGET_USD", 25.0),
        http_allowlist=allow or ("*",), cache_ttl=int(_float("TIER1_CACHE_TTL", 3600)),
        max_concurrency=int(_float("TIER1_MAX_CONCURRENCY", 8)),
        rate_limit_per_min=int(_float("TIER1_RATE_LIMIT_PER_MIN", 60)),
        slack_signing_secret=os.getenv("TIER1_SLACK_SIGNING_SECRET", ""),
        slack_bot_token=os.getenv("TIER1_SLACK_BOT_TOKEN", ""), notify_url=os.getenv("TIER1_NOTIFY_URL", ""),
        vault_dir=os.getenv("TIER1_VAULT_DIR", ""),
        sandbox_writable=os.getenv("TIER1_SANDBOX_WRITABLE", "").lower() in ("1", "true", "yes"),
        max_ralph_iterations=max(1, min(5, int(_float("TIER1_MAX_RALPH_ITERATIONS", 3)))),
        memory_url=os.getenv("TIER1_MEMORY_URL", "").rstrip("/"),
        memory_authorization=os.getenv("TIER1_MEMORY_AUTHORIZATION", ""),
        memory_tenant_id=os.getenv("TIER1_MEMORY_TENANT_ID", "staging-tenant"),
        memory_bank_id=os.getenv("TIER1_MEMORY_BANK_ID", "staging-bank"),
        memory_project_id=os.getenv("TIER1_MEMORY_PROJECT_ID", "Rayclaude-wiki"),
    )
