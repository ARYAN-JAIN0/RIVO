from __future__ import annotations

import app.core.config as config_module


def teardown_function(_):
    config_module.get_config.cache_clear()


def _build_with_env(monkeypatch, **env_values):
    keys = ["OLLAMA_URL", "OLLAMA_GENERATE_URL", "OLLAMA_EMBEDDING_URL"]
    for key in keys:
        if key in env_values:
            monkeypatch.setenv(key, env_values[key])
        else:
            monkeypatch.delenv(key, raising=False)

    config_module.get_config.cache_clear()
    return config_module.get_config()


def test_ollama_url_base_derives_split_urls(monkeypatch):
    cfg = _build_with_env(monkeypatch, OLLAMA_URL="http://localhost:11434")
    assert cfg.OLLAMA_URL == "http://localhost:11434"
    assert cfg.OLLAMA_GENERATE_URL == "http://localhost:11434/api/generate"
    assert cfg.OLLAMA_EMBEDDING_URL == "http://localhost:11434/api/embeddings"


def test_ollama_url_generate_derives_base_and_embedding(monkeypatch):
    cfg = _build_with_env(monkeypatch, OLLAMA_URL="http://localhost:11434/api/generate")
    assert cfg.OLLAMA_URL == "http://localhost:11434"
    assert cfg.OLLAMA_GENERATE_URL == "http://localhost:11434/api/generate"
    assert cfg.OLLAMA_EMBEDDING_URL == "http://localhost:11434/api/embeddings"


def test_explicit_split_urls_take_precedence(monkeypatch):
    cfg = _build_with_env(
        monkeypatch,
        OLLAMA_URL="http://localhost:11434",
        OLLAMA_GENERATE_URL="http://localhost:11434/custom/generate",
        OLLAMA_EMBEDDING_URL="http://localhost:11434/custom/embeddings",
    )
    assert cfg.OLLAMA_URL == "http://localhost:11434"
    assert cfg.OLLAMA_GENERATE_URL == "http://localhost:11434/custom/generate"
    assert cfg.OLLAMA_EMBEDDING_URL == "http://localhost:11434/custom/embeddings"
