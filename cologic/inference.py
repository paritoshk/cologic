"""Policy-model inference via Fireworks (OpenAI-compatible API).

Used for the zero-shot baseline and, later, for RL rollouts. Provider-agnostic:
point FIREWORKS_BASE_URL / FIREWORKS_API_KEY elsewhere (e.g. a local vLLM
server) and nothing else changes.

Env:
  FIREWORKS_API_KEY   (required)
  FIREWORKS_BASE_URL  (default https://api.fireworks.ai/inference/v1)
  RLHDL_MODEL         (default a Qwen-Coder 7B; the warm-start policy)
"""

from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor

from cologic.prompt import build_messages
from cologic.schema import Task

# Default backend: the HUD inference gateway. Fireworks serverless is not enabled
# on this account (every model 404s "not deployed"), so the gateway is the working
# path — it routes to Fireworks/Tinker under the hood. To hit Fireworks/vLLM
# directly, set FIREWORKS_BASE_URL (+ FIREWORKS_API_KEY), or a deployed model via
# RLHDL_MODEL.
HUD_GATEWAY_URL = "https://inference.beta.hud.ai/v1"
DEFAULT_BASE_URL = HUD_GATEWAY_URL
DEFAULT_MODEL = "Qwen/Qwen3-8B"


def _client():
    try:
        from openai import OpenAI
    except ImportError as e:  # pragma: no cover
        raise RuntimeError("pip install openai (or rl-hdl[eval]) to use inference.") from e
    base_url = os.environ.get("FIREWORKS_BASE_URL", DEFAULT_BASE_URL)
    # gateway -> HUD_API_KEY; direct Fireworks/vLLM (base_url overridden) -> FIREWORKS_API_KEY
    if "hud.ai" in base_url:
        api_key = os.environ.get("HUD_API_KEY")
        if not api_key:
            raise RuntimeError("set HUD_API_KEY for the HUD gateway.")
    else:
        api_key = os.environ.get("FIREWORKS_API_KEY")
        if not api_key:
            raise RuntimeError("set FIREWORKS_API_KEY for direct Fireworks/vLLM.")
    return OpenAI(api_key=api_key, base_url=base_url)


def model_id() -> str:
    return os.environ.get("RLHDL_MODEL", DEFAULT_MODEL)


def gateway_model_fn(model: str, *, temperature: float = 0.7, max_tokens: int = 2048):
    """Return a ModelFn (messages -> completion text) routed through the HUD gateway.

    Wires agents.loop's Plan/Forge to a gateway model by id, e.g.
    Forge = gateway_model_fn("Qwen/Qwen3-8B"); Plan = gateway_model_fn("gemma-4-31b-it").
    """
    from openai import OpenAI

    key = os.environ.get("HUD_API_KEY")
    if not key:
        raise RuntimeError("set HUD_API_KEY to use the HUD gateway.")
    client = OpenAI(api_key=key, base_url=os.environ.get("HUD_GATEWAY_URL", HUD_GATEWAY_URL))

    def _fn(messages: list[dict]) -> str:
        resp = client.chat.completions.create(
            model=model, messages=messages, temperature=temperature, max_tokens=max_tokens
        )
        return resp.choices[0].message.content or ""

    return _fn


def complete(
    task: Task,
    *,
    model: str | None = None,
    temperature: float = 0.7,
    top_p: float = 0.95,
    max_tokens: int = 1024,
) -> str:
    """One completion for one task."""
    resp = _client().chat.completions.create(
        model=model or model_id(),
        messages=build_messages(task),
        temperature=temperature,
        top_p=top_p,
        max_tokens=max_tokens,
    )
    return resp.choices[0].message.content or ""


def sample(tasks: list[Task], n: int, *, max_workers: int = 16, **kw) -> list[tuple[Task, str]]:
    """Sample `n` completions for each task, concurrently.

    Returns a flat list of (task, completion) pairs ready to hand to a grader's
    parallel map. Greedy (n==1) lowers temperature for a stable baseline read.
    """
    if n == 1:
        kw.setdefault("temperature", 0.0)
    jobs = [t for t in tasks for _ in range(n)]
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        completions = list(pool.map(lambda t: complete(t, **kw), jobs))
    return list(zip(jobs, completions))
