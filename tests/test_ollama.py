import asyncio
import json
import httpx

from tier1.config import load
from tier1.gateway import OpenAIProvider, make_provider


def test_ollama_defaults_are_local_and_keyless(monkeypatch):
    monkeypatch.setenv("TIER1_PROVIDER", "ollama")
    monkeypatch.delenv("TIER1_PROVIDER_API_KEY", raising=False)
    monkeypatch.delenv("TIER1_PROVIDER_BASE_URL", raising=False)
    s = load()
    assert s.provider == "ollama"
    assert s.models["small"] == "llama3.2"
    provider = make_provider(s)
    assert provider.base == "http://127.0.0.1:11434/v1"


def test_openai_compatible_provider_omits_empty_local_auth_header():
    def handler(req):
        assert "authorization" not in req.headers
        body = json.loads(req.content)
        assert body["model"] == "llama3.2"
        return httpx.Response(200, json={
            "choices": [{"message": {"content": "local answer"}}],
            "usage": {"prompt_tokens": 4, "completion_tokens": 2},
        })

    provider = OpenAIProvider("", "http://ollama.test/v1", httpx.MockTransport(handler))
    result = asyncio.run(provider.complete(task="generate", model="llama3.2", system="sys", prompt="hello", max_tokens=20))
    assert result == ("local answer", 4, 2)
