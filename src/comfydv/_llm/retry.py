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

Refusal/deflection detection (below) is a separate, opt-in trigger for the
same retry-with-a-new-seed mechanism: some models (observed with an
abliterated Qwen variant) answer with a soft refusal on a topic they judge
"sensitive" instead of erroring or returning blank, so neither of the above
checks catches it. This is deliberately a model-behavior concern, not a
backend one — every ``LLMProvider`` implementation (Ollama, llama.cpp, and
whatever comes next) wires the same detector into its own retry loop via its
own ``embed()``, rather than each backend inventing its own heuristic.
"""

import math
import re
from collections.abc import Awaitable, Callable

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


# ---------------------------------------------------------------------------
# Refusal/deflection detection
# ---------------------------------------------------------------------------
#
# Hybrid, cheapest-check-first: a fast, free lexical pass catches the blatant
# majority ("I cannot generate...") without ever touching the network; only
# a response that's short and/or hedge-y enough to be genuinely ambiguous
# pays for an embedding call. A long, on-topic response never reaches the
# embedding step at all.

REFUSAL_LEXICAL_PATTERNS: tuple[re.Pattern, ...] = tuple(
    re.compile(p, re.IGNORECASE)
    for p in (
        r"\bI\s*(?:'m|\s+am)?\s*(?:cannot|can't|won't|will not)\b[^.]{0,60}?\b"
        r"(?:generate|create|produce|write|provide|help|assist|describe|depict|continue)\b",
        r"\bI(?:'m|\s+am) (?:not able|unable) to\b",
        r"\bI don't feel comfortable\b",
        r"\bI'm sorry,?\s*(?:but\s+)?I\s*(?:can't|cannot)\b",
        r"\bas an AI\b[^.]{0,60}?\b(?:cannot|can't|unable|not able)\b",
        r"\bI must (?:decline|refuse)\b",
        r"\bthis (?:request|content|image|prompt) (?:violates|goes against)\b",
        r"\bnot something I(?:'m| am)? (?:able to|going to) (?:help with|generate|create|provide)\b",
        r"\bI (?:won't|will not) be (?:able to )?(?:generat|creat|provid)",
    )
)

_SOFT_HEDGE_KEYWORDS: tuple[str, ...] = (
    "sensitive",
    "unfortunately",
    "i must",
    "policy",
    "guideline",
    "responsible ai",
    "not appropriate",
    "inappropriate",
    "instead, i",
    "i'd rather",
    "i would rather",
    "controversial",
    "harmful",
    "offensive",
    "disturbing",
    "explicit content",
    "nsfw",
    "consider an alternative",
)

_AMBIGUOUS_LENGTH_THRESHOLD = 600
"""Below this many characters, a response is short enough that a soft
refusal is plausible and worth the extra embedding check — chosen well
under this pipeline's normal structured-JSON response sizes (typically
1000+ characters), not a tuned/validated threshold.

Note: ``is_refusal`` no longer applies this gate when the caller supplies
``embed_fn`` (see below) — an explicitly configured embedding model always
runs the check regardless of length/keywords. ``is_ambiguous`` is kept as a
standalone, independently tested heuristic for other callers (e.g. logging
"why was this worth embedding-checking") rather than wired into the hybrid
detector itself."""

REFUSAL_EXEMPLARS: tuple[str, ...] = (
    "I cannot generate an image or description involving this topic.",
    "I'm not able to help with this request as it involves a politically sensitive subject.",
    "I don't feel comfortable creating content related to this figure or event.",
    "This request touches on a sensitive political topic that I must decline to engage with.",
    "As an AI, I'm unable to produce content depicting this scenario.",
    "I'd rather not generate this — it involves content I'm not comfortable with.",
)


def is_lexical_refusal(text: str) -> bool:
    """Cheap, free regex pass — catches the blatant majority of refusals."""
    return any(p.search(text) for p in REFUSAL_LEXICAL_PATTERNS)


def is_ambiguous(text: str) -> bool:
    """Whether ``text`` is short/hedge-y enough to be worth the pricier
    embedding check, having already failed the free lexical pass.

    Deliberately cheap and approximate — false positives here only cost one
    extra embedding call, false negatives skip a refusal that a real
    similarity check might have caught. Not meant to be a precise signal on
    its own, just a gate on when the more expensive check runs at all.
    """
    stripped = text.strip()
    if not stripped:
        return False
    if len(stripped) < _AMBIGUOUS_LENGTH_THRESHOLD:
        return True
    lowered = stripped.lower()
    return any(keyword in lowered for keyword in _SOFT_HEDGE_KEYWORDS)


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Standard cosine similarity, no numpy dependency (comfydv has none)."""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


EmbedFn = Callable[[str], Awaitable[list[float] | None]]

_exemplar_embedding_cache: dict[str, list[list[float]]] = {}


async def _exemplar_embeddings(embed_fn: EmbedFn, cache_key: str) -> list[list[float]]:
    """Embed ``REFUSAL_EXEMPLARS`` once per ``cache_key`` (an embedding-model
    identifier) and reuse — the exemplars never change, only the embedding
    space (i.e. which model produced the vectors) does.
    """
    cached = _exemplar_embedding_cache.get(cache_key)
    if cached is not None:
        return cached
    embeddings = []
    for exemplar in REFUSAL_EXEMPLARS:
        vec = await embed_fn(exemplar)
        if not vec:
            # An embedding call failing for one exemplar almost certainly
            # means embeddings aren't usable at all right now (wrong/missing
            # embedding model, unreachable server) — bail out rather than
            # caching a partial, unusable exemplar set.
            return []
        embeddings.append(vec)
    _exemplar_embedding_cache[cache_key] = embeddings
    return embeddings


async def is_refusal(
    text: str,
    *,
    embed_fn: EmbedFn | None = None,
    embed_cache_key: str = "",
    threshold: float = 0.82,
) -> bool:
    """Hybrid refusal/deflection detector: free lexical pass first, then an
    embedding-similarity fallback whenever the caller has configured one.

    ``embed_fn`` is supplied by the caller's own ``LLMProvider.embed()`` —
    this function has no idea which backend or model produced ``text``, by
    design (ADR: refusal detection is a model-behavior concern, not a
    backend one). ``embed_fn=None`` (no embedding model configured) degrades
    to lexical-only detection rather than erroring; ``embed_fn`` present
    means the caller already opted in to the extra cost, so every non-blank,
    non-lexically-caught response gets checked — no further length/keyword
    gating. Any failure while embedding (unreachable server, no
    embedding-capable model loaded) is swallowed the same way — an optional
    enhancement failing shouldn't take down the retry loop it's assisting.
    """
    if not text or not text.strip():
        return False  # blank responses are the *other* retry trigger, not this one
    if is_lexical_refusal(text):
        return True
    if embed_fn is None:
        return False
    # embed_fn only exists when the caller explicitly configured an
    # embedding_model — that's an opt-in to pay for the check, so run it on
    # every non-blank, non-lexically-caught response rather than gating
    # further on is_ambiguous. The length/keyword heuristic exists to avoid
    # *unwanted* embedding calls when no embedding model is configured (see
    # the embed_fn is None branch above); it has no reason to also suppress
    # calls once the caller has already asked for them, and doing so was
    # exactly what let the subtle/on-topic-looking deflections this feature
    # targets slip through undetected.
    try:
        exemplar_vecs = await _exemplar_embeddings(embed_fn, embed_cache_key)
        if not exemplar_vecs:
            return False
        text_vec = await embed_fn(text)
        if not text_vec:
            return False
    except Exception:
        return False
    return max(cosine_similarity(text_vec, vec) for vec in exemplar_vecs) >= threshold
