"""Inference config resolution (no network / API key needed)."""

from rl_hdl import inference


def test_max_tokens_defaults(monkeypatch):
    monkeypatch.delenv("RLHDL_MAX_TOKENS", raising=False)
    assert inference.max_tokens_setting() == inference.DEFAULT_MAX_TOKENS


def test_max_tokens_env_override(monkeypatch):
    monkeypatch.setenv("RLHDL_MAX_TOKENS", "8192")
    assert inference.max_tokens_setting() == 8192
