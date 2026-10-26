from pathlib import Path


def test_vite_allows_only_the_configured_tailscale_ui_hostname():
    source = Path("vite.config.ts").read_text(encoding="utf-8")
    assert "allowedHosts: ['ray.tail4663f6.ts.net']" in source
