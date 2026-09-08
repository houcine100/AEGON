# core/orchestration/llm_client.py
# Single shared LLM client for all nodes.
# Every node imports from here. No node creates its own client.
# When Phase 6 comes, change PRIMARY_BACKEND to "local" — one line.
# Automatic failover: if primary hits rate limit, switches to backup.

import os
import requests
from ollama import Client as OllamaClient

# --- Backend config ---
# Tried in this order; each falls through to the next on a rate limit (429).
# Change PRIMARY_BACKEND to "local" in Phase 6.
#
# NVIDIA is primary as of 2026-08-07: OpenRouter's free tier is 50 requests/day, and
# Aegon spends ~4-5 calls per turn (classifier -> orchestrator -> worker -> synthesizer),
# so that cap is ~12 turns/day — unusable. Same model, benchmarked at the same speed
# (1.38s vs 1.35s median). OpenRouter stays in the chain: its quota resets daily.
PRIMARY_BACKEND = "nvidia"
# Two NVIDIA models, not one: 2026-08-07 nemotron-3-nano-30b-a3b returned 503 while
# three other models on the SAME endpoint and key served fine. Outages there are
# per-model, so a single NVIDIA entry gives no real redundancy.
BACKEND_ORDER = ("nvidia", "nvidia_alt", "openrouter", "ollama")

# --- Model names ---
# nano-30b-a3b, not super-120b: measured 2026-08-07 with Aegon's real ~2.4k-char system
# prompt, super-120b ran 1.6-17.2s (median 2.7s) — the 17s tail blew the 30s timeout on
# a live turn. nano-30b-a3b ran 1.3-1.9s (median 1.6s). Bigger models queue worse on
# NVIDIA's shared endpoint, so scaling UP makes latency worse, not better.
# It activates only 3B of 30B params (MoE) — ample for classify/route/reply work.
NVIDIA_MODEL = "nvidia/nemotron-3-nano-30b-a3b"
# Sibling on the same endpoint/key, for when the primary model 503s.
# Measured 2026-08-07: 1.9-2.0s, the tightest spread of any model tested.
NVIDIA_ALT_MODEL = "nvidia/nvidia-nemotron-nano-9b-v2"
OPENROUTER_MODEL = "nvidia/nemotron-3-super-120b-a12b:free"  # same model, free-tier route
OLLAMA_MODEL = "gpt-oss:120b-cloud"

# --- Endpoints (both OpenAI-compatible) ---
_NVIDIA_URL = "https://integrate.api.nvidia.com/v1/chat/completions"
_OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
_ollama_client = OllamaClient(host="http://localhost:11434")

# --- Current active backend ---
# Starts on primary. Advances down BACKEND_ORDER on rate limit.
# Resets to primary at next session start.
_active_backend = PRIMARY_BACKEND


class LLMRateLimitError(Exception):
    """Raised when a backend returns 429 (rate limit / free-tier cap hit)."""


def _call_openai_compatible(
    url: str, api_key: str, model: str,
    system_prompt: str, user_message: str, temperature: float,
) -> str:
    """Shared caller — NVIDIA NIM and OpenRouter both speak the OpenAI chat schema."""
    response = requests.post(
        url=url,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": model,
            "temperature": temperature,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
        },
        timeout=60,  # raised from 30 — shared endpoints have long tails under load
    )
    if response.status_code == 429:
        raise LLMRateLimitError(response.text)
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"].strip()


def _call_nvidia(system_prompt: str, user_message: str, temperature: float) -> str:
    return _call_openai_compatible(
        _NVIDIA_URL, os.environ.get("NVIDIA_LLM_API_KEY", ""), NVIDIA_MODEL,
        system_prompt, user_message, temperature,
    )


def _call_nvidia_alt(system_prompt: str, user_message: str, temperature: float) -> str:
    return _call_openai_compatible(
        _NVIDIA_URL, os.environ.get("NVIDIA_LLM_API_KEY", ""), NVIDIA_ALT_MODEL,
        system_prompt, user_message, temperature,
    )


def _call_openrouter(system_prompt: str, user_message: str, temperature: float) -> str:
    return _call_openai_compatible(
        _OPENROUTER_URL, os.environ.get("OPENROUTER_API_KEY", ""), OPENROUTER_MODEL,
        system_prompt, user_message, temperature,
    )


def _call_ollama(system_prompt: str, user_message: str, temperature: float) -> str:
    response = _ollama_client.chat(
        model=OLLAMA_MODEL,
        options={"temperature": temperature},
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
    )
    return response["message"]["content"].strip()


def call_llm(system_prompt: str, user_message: str, temperature: float = 0.2) -> str:
    """
    Single entry point for all LLM calls across every node.
    Automatically switches to fallback if primary hits rate limit.

    Args:
        system_prompt: the node-specific instructions.
        user_message: the content to process.
        temperature: default 0.2 for structured calls.

    Returns:
        Response as a plain string.
    """
    global _active_backend

    callers = {
        "nvidia": _call_nvidia,
        "nvidia_alt": _call_nvidia_alt,
        "openrouter": _call_openrouter,
        "ollama": _call_ollama,
    }
    if _active_backend not in callers:
        raise ValueError(f"Unknown backend: {_active_backend}")

    # Walk the chain from wherever we currently are. A 429 demotes to the next
    # backend permanently for this session — reset_to_primary() at session start
    # retries the top of the chain after daily quotas roll over.
    start = BACKEND_ORDER.index(_active_backend)
    last_error = None
    for backend in BACKEND_ORDER[start:]:
        try:
            result = callers[backend](system_prompt, user_message, temperature)
            _active_backend = backend
            return result
        except LLMRateLimitError:
            print(f"[llm_client] {backend} rate limit hit — trying next backend.")
            last_error = LLMRateLimitError(f"{backend} rate limited")
            continue
        except Exception as e:
            # A non-rate-limit failure (network, bad key, backend down) should also
            # fall through rather than kill the turn — Ollama being absent is normal.
            print(f"[llm_client] {backend} failed: {e}")
            last_error = e
            continue

    raise last_error or RuntimeError("All LLM backends failed.")


def reset_to_primary() -> None:
    """
    Resets the active backend to primary.
    Call this at session start to retry the top of the chain after quotas reset.
    """
    global _active_backend
    _active_backend = PRIMARY_BACKEND
    print(f"[llm_client] Reset to primary backend: {PRIMARY_BACKEND}")


def get_active_backend() -> str:
    """Returns the currently active backend name."""
    return _active_backend