"""Tests for comfydv._llm.retry — shared retry-on-blank-output helpers used
by both providers' chat() and the shared chat_structured() helper, plus the
refusal/deflection detector that rides the same retry-with-a-new-seed
mechanism.

Refusal-detection tests here are pure-logic only — no provider/HTTP
involved. See test_ollama_provider.py, test_llamacpp_provider.py, and
test_llm_chat_structured.py for the retry-loop integration (does a detected
refusal actually trigger a reseeded retry).
"""

import pytest

from comfydv._llm.ollama_provider import _run_async
from comfydv._llm.retry import (
    REFUSAL_EXEMPLARS,
    cosine_similarity,
    is_ambiguous,
    is_lexical_refusal,
    is_refusal,
    next_seed,
)


def test_next_seed_attempt_one_is_zero_by_default():
    assert next_seed(None, 1) == 0


def test_next_seed_increments_from_zero_when_unset():
    assert next_seed(None, 2) == 1
    assert next_seed({}, 3) == 2


def test_next_seed_starts_from_pinned_base():
    assert next_seed({"seed": 42}, 1) == 42
    assert next_seed({"seed": 42}, 2) == 43
    assert next_seed({"seed": 42}, 3) == 44


def test_next_seed_ignores_non_int_seed():
    assert next_seed({"seed": "not-an-int"}, 2) == 1


# ---------------------------------------------------------------------------
# Refusal/deflection detection
# ---------------------------------------------------------------------------


class TestLexicalDetection:
    def test_blatant_refusal_openers_match(self):
        blatant = [
            "I cannot generate that image for you.",
            "I'm not able to help with this request.",
            "I am unable to comply with your instruction.",
            "Cannot generate this image due to the sensitive content.",
            '{"error": "cannot generate this content"}',
            "I don't feel comfortable creating this content.",
            "I'm sorry, but I can't produce that description.",
            "As an AI, I'm unable to depict this scenario.",
            "I must decline this request.",
            "This request violates my usage policies.",
            "That's not something I'm able to help with right now.",
        ]
        for text in blatant:
            assert is_lexical_refusal(text), f"expected refusal match: {text!r}"

    def test_ordinary_content_does_not_match(self):
        ordinary = [
            "The subject turns to face the camera and smiles warmly.",
            "A person cannot simply walk into Mordor, the guide joked.",
            "I can help you plan a birthday party for your dog.",
            "",
        ]
        for text in ordinary:
            assert not is_lexical_refusal(text), f"unexpected match: {text!r}"


class TestAmbiguityHeuristic:
    def test_short_response_is_ambiguous(self):
        assert is_ambiguous("Sorry, can't do that one.")

    def test_long_response_without_hedge_keywords_is_not_ambiguous(self):
        long_text = "The subject rotates smoothly toward the lens. " * 20
        assert len(long_text) >= 400
        assert not is_ambiguous(long_text)

    def test_long_response_with_hedge_keyword_is_ambiguous(self):
        long_text = "Unfortunately, " + "this touches on a sensitive area. " * 20
        assert len(long_text) >= 400
        assert is_ambiguous(long_text)

    def test_blank_text_is_not_ambiguous(self):
        assert not is_ambiguous("   ")


class TestCosineSimilarity:
    def test_identical_vectors_score_one(self):
        assert cosine_similarity([1.0, 0.0], [1.0, 0.0]) == pytest.approx(1.0)

    def test_orthogonal_vectors_score_zero(self):
        assert cosine_similarity([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)

    def test_opposite_vectors_score_negative_one(self):
        assert cosine_similarity([1.0, 0.0], [-1.0, 0.0]) == pytest.approx(-1.0)

    def test_mismatched_lengths_return_zero(self):
        assert cosine_similarity([1.0, 0.0], [1.0, 0.0, 0.0]) == 0.0

    def test_empty_vectors_return_zero(self):
        assert cosine_similarity([], []) == 0.0


class TestIsRefusalHybrid:
    def test_blank_text_is_never_a_refusal(self):
        assert not _run_async(is_refusal(""))
        assert not _run_async(is_refusal("   "))

    def test_lexical_match_short_circuits_without_embedding(self):
        calls = []

        async def embed_fn(text):
            calls.append(text)
            return [1.0, 0.0]

        result = _run_async(
            is_refusal("I cannot generate that image for you.", embed_fn=embed_fn)
        )
        assert result is True
        assert calls == []  # never reached the embedding step

    def test_long_clean_response_is_still_embedding_checked_but_not_a_refusal(self):
        # embed_fn present means the caller opted in to the embedding check
        # regardless of length/hedge-keywords (is_ambiguous no longer gates
        # this) — a long, on-topic response should still be embedding-
        # checked, it just shouldn't score as similar to the refusal
        # exemplars.
        calls = []

        async def embed_fn(text):
            calls.append(text)
            if text == long_text:
                return [0.0, 1.0]  # orthogonal to the exemplar vector below
            return [1.0, 0.0]  # exemplars

        long_text = "The subject rotates smoothly toward the lens. " * 20
        result = _run_async(is_refusal(long_text, embed_fn=embed_fn))
        assert result is False
        assert long_text in calls  # embedding check DID run, just scored low

    def test_no_embed_fn_degrades_to_lexical_only(self):
        # Ambiguous (short), no lexical match, no embed_fn -> can't check further
        assert not _run_async(is_refusal("Not today, sorry.", embed_fn=None))

    def test_ambiguous_response_above_threshold_is_refusal(self):
        async def embed_fn(text):
            # Exemplars and a near-identical short "refusal-ish" probe get a
            # high similarity score; distinguish by a marker substring.
            if "PROBE" in text:
                return [1.0, 0.0]
            return [0.99, 0.14]  # cos-sim with [1,0] is ~0.99

        result = _run_async(
            is_refusal(
                "PROBE: not comfortable with this one",
                embed_fn=embed_fn,
                embed_cache_key="test-model",
                threshold=0.8,
            )
        )
        assert result is True

    def test_ambiguous_response_below_threshold_is_not_refusal(self):
        async def embed_fn(text):
            if "PROBE" in text:
                return [1.0, 0.0]
            return [0.0, 1.0]  # orthogonal -> cos-sim 0.0

        result = _run_async(
            is_refusal(
                "PROBE: a short reply",
                embed_fn=embed_fn,
                embed_cache_key="test-model-2",
                threshold=0.8,
            )
        )
        assert result is False

    def test_long_json_shaped_soft_refusal_without_hedge_keywords_is_caught(self):
        # Regression case: a structured-output-shaped response (>600 chars
        # once you count JSON braces/field names) whose deflection doesn't
        # use any of the canned hedge keywords used to be invisible to the
        # embedding check entirely, because is_ambiguous gated on length
        # and keywords. embed_fn now runs unconditionally once configured.
        soft_refusal = (
            '{"prompt": "'
            + "Let's take this in a different creative direction that everyone can enjoy. "
            * 8
            + '"}'
        )
        assert len(soft_refusal) >= 600
        assert not is_lexical_refusal(soft_refusal)

        async def embed_fn(text):
            if text == soft_refusal:
                return [1.0, 0.0]
            return [0.97, 0.24]  # exemplars: cos-sim with [1,0] is ~0.97

        result = _run_async(
            is_refusal(
                soft_refusal,
                embed_fn=embed_fn,
                embed_cache_key="regression-model",
                threshold=0.8,
            )
        )
        assert result is True

    def test_exemplar_embeddings_cached_across_calls(self):
        exemplar_calls = {"n": 0}

        async def embed_fn(text):
            if "PROBE" in text:
                return [1.0, 0.0]
            exemplar_calls["n"] += 1
            return [1.0, 0.0]

        _run_async(
            is_refusal(
                "PROBE: first ambiguous call",
                embed_fn=embed_fn,
                embed_cache_key="cache-key-shared",
                threshold=0.5,
            )
        )
        first_count = exemplar_calls["n"]
        assert first_count > 0

        _run_async(
            is_refusal(
                "PROBE: second ambiguous call",
                embed_fn=embed_fn,
                embed_cache_key="cache-key-shared",
                threshold=0.5,
            )
        )
        # Exemplar embeddings reused from cache -> no additional exemplar calls
        assert exemplar_calls["n"] == first_count

    def test_embed_fn_failure_degrades_to_not_refused(self):
        async def failing_embed_fn(text):
            raise RuntimeError("server unreachable")

        result = _run_async(
            is_refusal(
                "Not comfortable with this one, sorry.",
                embed_fn=failing_embed_fn,
                embed_cache_key="unreachable-model",
            )
        )
        assert result is False

    def test_embed_fn_returning_none_degrades_to_not_refused(self):
        async def none_embed_fn(text):
            return None

        result = _run_async(
            is_refusal(
                "Not comfortable with this one, sorry.",
                embed_fn=none_embed_fn,
                embed_cache_key="no-embeddings-model",
            )
        )
        assert result is False


class TestCustomPhrases:
    def test_custom_phrase_substring_match_needs_no_embed_fn(self):
        # A phrase the user added at runtime that the shipped lexical
        # patterns don't cover — should be caught for free, no embedding
        # model required.
        result = _run_async(
            is_refusal(
                "I am restricted from producing that kind of content.",
                custom_phrases=("restricted from",),
            )
        )
        assert result is True

    def test_custom_phrase_match_is_case_insensitive(self):
        result = _run_async(
            is_refusal(
                "SORRY, THAT'S OFF LIMITS FOR ME.",
                custom_phrases=("off limits",),
            )
        )
        assert result is True

    def test_unrelated_custom_phrase_does_not_match(self):
        result = _run_async(
            is_refusal(
                "The subject walks calmly toward the horizon.",
                custom_phrases=("restricted from", "off limits"),
            )
        )
        assert result is False

    def test_blank_and_whitespace_custom_phrases_are_ignored(self):
        # A stray empty entry must never become a universal substring match.
        result = _run_async(
            is_refusal(
                "The subject walks calmly toward the horizon.",
                custom_phrases=("", "   "),
            )
        )
        assert result is False

    def test_custom_phrase_folded_into_embedding_exemplars(self):
        # No exact substring match, but embed_fn scores the response as
        # similar to the custom phrase (not one of the shipped exemplars).
        custom = "my creators have limited what I can show you"

        async def embed_fn(text):
            if text == custom:
                return [1.0, 0.0]
            if text in REFUSAL_EXEMPLARS:
                return [0.0, 1.0]  # shipped exemplars score orthogonal
            return [0.99, 0.14]  # the probe response is near the custom one

        result = _run_async(
            is_refusal(
                "There are limits my creators placed on what I can show.",
                embed_fn=embed_fn,
                embed_cache_key="custom-exemplar-model",
                threshold=0.8,
                custom_phrases=(custom,),
            )
        )
        assert result is True

    def test_different_custom_phrase_sets_do_not_share_exemplar_cache(self):
        # Regression guard: if the exemplar cache key ignored custom_phrases,
        # a second call with a different custom phrase set would incorrectly
        # reuse the first call's cached (and now stale) exemplar vectors.
        calls = []

        async def embed_fn(text):
            calls.append(text)
            return [1.0, 0.0]

        _run_async(
            is_refusal(
                "short reply",
                embed_fn=embed_fn,
                embed_cache_key="shared-model",
                custom_phrases=("phrase one",),
            )
        )
        first_call_count = len(calls)

        _run_async(
            is_refusal(
                "short reply",
                embed_fn=embed_fn,
                embed_cache_key="shared-model",
                custom_phrases=("phrase two",),
            )
        )
        # A fresh custom phrase set re-embeds the exemplars (including the
        # new phrase) rather than reusing the first set's cached vectors.
        assert len(calls) > first_call_count
