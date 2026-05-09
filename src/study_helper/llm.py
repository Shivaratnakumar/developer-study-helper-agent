"""OpenAI-compatible chat completion (OpenAI, Ollama, and other local servers)."""

from __future__ import annotations

import os
from urllib.parse import urlparse

from openai import OpenAI

_DEFAULT_CLOUD_MODEL = "gpt-4o-mini"
_DEFAULT_OLLAMA_MODEL = "llama3.2"


def _truthy(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in ("1", "true", "yes", "on")


def _resolve_base_url() -> str | None:
    explicit = os.environ.get("OPENAI_BASE_URL")
    if explicit:
        return explicit.rstrip("/")
    if _truthy("STUDY_HELPER_OLLAMA"):
        host = os.environ.get("OLLAMA_HOST", "127.0.0.1:11434").rstrip("/")
        if not host.startswith("http"):
            host = f"http://{host}"
        return f"{host}/v1"
    return None


def _looks_like_ollama(base_url: str | None) -> bool:
    if not base_url:
        return _truthy("STUDY_HELPER_OLLAMA")
    try:
        parsed = urlparse(base_url)
        port = parsed.port
        if port == 11434:
            return True
    except ValueError:
        pass
    return "ollama" in (base_url or "").lower()


def get_client() -> OpenAI:
    base_url = _resolve_base_url()
    api_key = os.environ.get("OPENAI_API_KEY", "").strip() or None

    if not api_key:
        if base_url and _looks_like_ollama(base_url):
            api_key = "ollama"
        elif base_url:
            api_key = "local"
        else:
            msg = (
                "Set OPENAI_API_KEY, or use Ollama: "
                "STUDY_HELPER_OLLAMA=1 (and optional OLLAMA_HOST), "
                "or set OPENAI_BASE_URL to your OpenAI-compatible server."
            )
            raise RuntimeError(msg)

    if base_url:
        return OpenAI(api_key=api_key, base_url=base_url)
    return OpenAI(api_key=api_key)


def default_model() -> str:
    base = _resolve_base_url()
    if os.environ.get("STUDY_HELPER_MODEL"):
        return os.environ["STUDY_HELPER_MODEL"].strip()
    if _looks_like_ollama(base):
        return _DEFAULT_OLLAMA_MODEL
    return _DEFAULT_CLOUD_MODEL


def complete(system: str, user: str, model: str | None = None) -> str:
    return chat(
        [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        model=model,
    )


def chat(
    messages: list[dict[str, str]],
    model: str | None = None,
    temperature: float = 0.4,
) -> str:
    if not messages:
        return ""
    client = get_client()
    m = model or default_model()
    resp = client.chat.completions.create(
        model=m,
        messages=messages,
        temperature=temperature,
    )
    choice = resp.choices[0]
    if not choice.message.content:
        return ""
    return choice.message.content.strip()
