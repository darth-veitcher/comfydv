"""Shared retry-on-empty-output helpers for chat()/chat_structured().

Both providers' chat() calls (ADR-007) and the shared chat_structured()
helper (_llm/chat.py) hit the same class of failure, confirmed live against
a freshly-started Ollama instance on a fresh runpod: the model's first
response after loading is sometimes blank or fails structured-output
validation outright, then behaves normally on the very next call. Centralized
here so both providers and both chat modes retry the same way rather than
each re-deriving the policy.

Only blank/whitespace-only responses trigger a retry for plain chat() —
not merely "short" ones — because a fixed length threshold would misfire on
legitimately short, valid answers (single-word replies, labels, "yes"/"no").
"""

RETRY_BACKOFF_SECS = 1.5
"""Flat delay between retries — gives a still-loading model time to finish
before the next attempt, rather than hammering it with identical requests
back-to-back."""


def next_seed(options: dict | None, attempt: int) -> int:
    """Deterministic seed for retry ``attempt`` (1-indexed).

    Attempt 1 is the caller's original request and is never touched by this
    function — callers only call it for attempt >= 2. Starts from
    ``options["seed"]`` if the caller pinned one, else 0, and increments by
    ``attempt - 1`` so each retry is a new, reproducible value instead of
    repeating the exact same request that just failed.
    """
    base = 0
    if options and isinstance(options.get("seed"), int):
        base = options["seed"]
    return base + (attempt - 1)
