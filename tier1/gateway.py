from __future__ import annotations
import asyncio, contextvars, json, time
from dataclasses import dataclass

import httpx

from .config import Settings
from .store import Store
from .util import tok


class ProviderError(Exception):
    def __init__(self, msg: str, retryable: bool = False):
        super().__init__(msg)
        self.retryable = retryable


class BudgetExceeded(Exception):
    pass


@dataclass
class Completion:
    text: str
    input_tokens: int
    output_tokens: int
    model: str
    tier: str
    task: str
    cost_usd: float
    latency_ms: int


class MockProvider:
    """Deterministic offline provider for tests, demos and CI. Never used unless TIER1_PROVIDER=mock."""
    name = "mock"

    async def complete(self, *, task, model, system, prompt, max_tokens):
        from .compiler import heuristic_compile
        if task == "compile":
            out = json.dumps(heuristic_compile(prompt))
        elif task == "audit":
            bad = "[[lowscore]]" in prompt.split("ANSWER:\n", 1)[-1]
            out = json.dumps({"score": 0.5 if bad else 0.93, "issues": ["mock: flagged"] if bad else []})
        elif task == "generate":
            out = ("[revised] Answer (mock provider) addressing audit issues." if "REMEDIATE" in prompt
                   else "Answer (mock provider)\n" + prompt.split("\n\n")[0])
        else:
            out = prompt[: max_tokens * 4]
        return out, tok(system + prompt), tok(out)


class AnthropicProvider:
    name = "anthropic"

    def __init__(self, key: str, base: str = "", transport=None):
        self.key, self.base, self.transport = key, (base or "https://api.anthropic.com").rstrip("/"), transport

    async def complete(self, *, task, model, system, prompt, max_tokens):
        async with httpx.AsyncClient(timeout=120, transport=self.transport) as c:
            r = await c.post(f"{self.base}/v1/messages",
                             headers={"x-api-key": self.key, "anthropic-version": "2023-06-01"},
                             json={"model": model, "max_tokens": max_tokens, "system": system,
                                   "messages": [{"role": "user", "content": prompt}]})
        if r.status_code in (429, 500, 502, 503, 529):
            raise ProviderError(f"{r.status_code} from provider", retryable=True)
        if r.status_code >= 400:
            raise ProviderError(f"{r.status_code}: {r.text[:200]}")
        d = r.json()
        text = "".join(b.get("text", "") for b in d.get("content", []) if b.get("type") == "text")
        u = d.get("usage", {})
        return text, int(u.get("input_tokens", 0)), int(u.get("output_tokens", 0))


class OpenAIProvider:
    """Any OpenAI-compatible /chat/completions endpoint (OpenAI, vLLM, Ollama, gateways)."""
    name = "openai"

    def __init__(self, key: str, base: str = "", transport=None):
        self.key, self.base, self.transport = key, (base or "https://api.openai.com/v1").rstrip("/"), transport

    async def complete(self, *, task, model, system, prompt, max_tokens):
        async with httpx.AsyncClient(timeout=120, transport=self.transport) as c:
            r = await c.post(f"{self.base}/chat/completions", headers={"Authorization": f"Bearer {self.key}"},
                             json={"model": model, "max_tokens": max_tokens,
                                   "messages": [{"role": "system", "content": system},
                                                {"role": "user", "content": prompt}]})
        if r.status_code in (429, 500, 502, 503):
            raise ProviderError(f"{r.status_code} from provider", retryable=True)
        if r.status_code >= 400:
            raise ProviderError(f"{r.status_code}: {r.text[:200]}")
        d = r.json()
        u = d.get("usage", {})
        return d["choices"][0]["message"]["content"] or "", int(u.get("prompt_tokens", 0)), int(u.get("completion_tokens", 0))


def make_provider(s: Settings):
    if s.provider == "mock":
        return MockProvider()
    if not s.api_key:
        raise ProviderError("TIER1_PROVIDER_API_KEY is required for provider " + s.provider)
    if not all(s.models.values()):
        raise ProviderError("set TIER1_MODEL_SMALL / MEDIUM / LARGE for provider " + s.provider)
    return (AnthropicProvider if s.provider == "anthropic" else OpenAIProvider)(s.api_key, s.base_url)


# Per-request soft spend cap. A shared mutable dict, so concurrent sub-tasks (asyncio.gather) draw from one budget.
request_budget: contextvars.ContextVar = contextvars.ContextVar("request_budget", default=None)


class Gateway:
    retry_base = 0.5

    def __init__(self, s: Settings, store: Store, provider=None):
        self.s, self.store = s, store
        self.provider = provider or make_provider(s)

    def price(self, tier: str, i: int, o: int) -> float:
        pin, pout = self.s.prices[tier]
        return (i * pin + o * pout) / 1_000_000

    async def complete(self, *, task: str, tier: str, system: str, prompt: str, max_tokens: int = 1024,
                       run_id: str = "") -> Completion:
        if self.store.spend_today() >= self.s.daily_budget_usd:
            raise BudgetExceeded(f"daily budget of ${self.s.daily_budget_usd:.2f} reached")
        rb = request_budget.get()
        if rb is not None and rb["spent"] >= rb["limit"]:
            raise BudgetExceeded(f"request budget of ${rb['limit']:.4f} reached")
        model, last = self.s.models[tier], None
        for attempt in range(3):
            t0 = time.perf_counter()
            try:
                text, i, o = await self.provider.complete(task=task, model=model, system=system,
                                                          prompt=prompt, max_tokens=max_tokens)
                break
            except (ProviderError, httpx.TransportError) as e:
                last = e
                if isinstance(e, ProviderError) and not e.retryable:
                    raise
                await asyncio.sleep(self.retry_base * 2 ** attempt)
        else:
            raise ProviderError(f"provider failed after retries: {last}")
        ms = int((time.perf_counter() - t0) * 1000)
        cost = self.price(tier, i, o)
        self.store.usage_add(run_id, task, tier, model, i, o, cost, ms)
        if rb is not None:
            rb["spent"] += cost
        return Completion(text, i, o, model, tier, task, cost, ms)
