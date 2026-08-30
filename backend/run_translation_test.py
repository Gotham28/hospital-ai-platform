import asyncio
import sys
import time

import app.services.translation as translation
from app.services.translation import TranslationUnavailableError

passed = 0
failed = 0


def check(name, condition, detail=""):
    global passed, failed
    if condition:
        print(f"PASS {name}")
        passed += 1
    else:
        print(f"FAIL {name}" + (f" — {detail}" if detail else ""))
        failed += 1


def reset_breakers():
    for b in (translation._sarvam_breaker, translation._google_breaker):
        b._consecutive_failures = 0
        b._opened_at = None


def _fail(text, source, target):
    raise RuntimeError("simulated provider failure")


async def _fail_async(text, source, target):
    raise RuntimeError("simulated provider failure")


# =============================================================================
# CHUNK SPLITTING
# =============================================================================

def test_chunk_boundaries():
    text_1999 = "a" * 1999
    text_2000 = "a" * 2000
    text_2001 = "a" * 2001
    check("chunk_1999_single_chunk", translation._split_into_chunks(text_1999) == [text_1999])
    check("chunk_2000_single_chunk", translation._split_into_chunks(text_2000) == [text_2000])
    chunks_2001 = translation._split_into_chunks(text_2001)
    check("chunk_2001_splits_into_multiple", len(chunks_2001) > 1, f"got {len(chunks_2001)} chunk(s)")
    check("chunk_2001_all_under_or_at_limit", all(len(c) <= 2000 for c in chunks_2001))
    check("chunk_2001_rejoins_exactly", "".join(chunks_2001) == text_2001)


def test_hard_split_single_sentence_over_limit():
    long_sentence = "x" * 5000  # no separators at all
    chunks = translation._split_into_chunks(long_sentence)
    check("hard_split_terminates_and_splits", len(chunks) == 3, f"got {len(chunks)}")
    check("hard_split_all_under_or_at_limit", all(len(c) <= 2000 for c in chunks))
    check("hard_split_rejoins_exactly", "".join(chunks) == long_sentence)


def test_sentence_boundary_chunking_and_rejoin():
    sentence = "This is a test sentence. "
    text = sentence * 100  # 2600 chars, well-formed sentence boundaries throughout
    chunks = translation._split_into_chunks(text)
    check("sentence_chunking_produces_multiple", len(chunks) >= 2)
    check("sentence_chunking_all_under_or_at_limit", all(len(c) <= 2000 for c in chunks))
    check("sentence_chunking_rejoins_exactly", "".join(chunks) == text)


def test_sarvam_chunks_and_joins_translated_output():
    reset_breakers()
    original_key = translation.settings.SARVAM_API_KEY
    translation.settings.SARVAM_API_KEY = "fake-key-for-test"
    calls = []

    def fake_sarvam_one(text, source, target):
        calls.append(text)
        return text.upper()

    translation._sarvam_translate_one = fake_sarvam_one
    long_text = "Sentence number filler. " * 100  # > 2000 chars
    try:
        result = translation._translate(long_text, "en", "ml")
        check("sarvam_chunking_multiple_provider_calls", len(calls) > 1, f"got {len(calls)} call(s)")
        check("sarvam_chunking_result_matches_expected", result == long_text.upper())
    finally:
        translation.settings.SARVAM_API_KEY = original_key


def test_any_chunk_failure_falls_whole_call_to_google():
    reset_breakers()
    original_key = translation.settings.SARVAM_API_KEY
    translation.settings.SARVAM_API_KEY = "fake-key-for-test"
    call_count = {"n": 0}

    def fake_sarvam_one_fails_on_second_chunk(text, source, target):
        call_count["n"] += 1
        if call_count["n"] == 2:
            raise RuntimeError("simulated mid-chunk failure")
        return text.upper()

    translation._sarvam_translate_one = fake_sarvam_one_fails_on_second_chunk
    translation._google_translate = lambda t, s, tg: "GOOGLE_FULL_FALLBACK"
    long_text = "Sentence number filler. " * 100
    try:
        result = translation._translate(long_text, "en", "ml")
        check("partial_chunk_failure_never_returns_partial_result", result == "GOOGLE_FULL_FALLBACK")
    finally:
        translation.settings.SARVAM_API_KEY = original_key


# =============================================================================
# CIRCUIT BREAKER
# =============================================================================

def test_breaker_opens_on_third_consecutive_failure():
    reset_breakers()
    original_key = translation.settings.SARVAM_API_KEY
    translation.settings.SARVAM_API_KEY = "fake-key-for-test"
    translation._sarvam_translate_one = _fail
    translation._google_translate = lambda t, s, tg: "GOOGLE_OK"
    try:
        for i in range(3):
            result = translation._translate("hello", "en", "ml")
            check(f"breaker_call_{i+1}_falls_back_to_google", result == "GOOGLE_OK")
        check("breaker_opens_after_3rd_failure", translation._sarvam_breaker.is_open())
    finally:
        translation.settings.SARVAM_API_KEY = original_key


def test_fourth_call_skips_sarvam_while_breaker_open():
    # Self-contained: sets its own fake key and forces the breaker open.
    # Without a key, the guard short-circuits before consulting the breaker,
    # so this test would pass vacuously. Setting the key ensures the breaker
    # is the only thing blocking Sarvam.
    original_key = translation.settings.SARVAM_API_KEY
    translation.settings.SARVAM_API_KEY = "fake-key-for-test"
    translation._sarvam_breaker._consecutive_failures = 3
    translation._sarvam_breaker._opened_at = time.monotonic()
    call_count = {"n": 0}

    def fake_sarvam_should_not_be_called(text, source, target):
        call_count["n"] += 1
        return "SHOULD_NOT_HAPPEN"

    translation._sarvam_translate_one = fake_sarvam_should_not_be_called
    translation._google_translate = lambda t, s, tg: "GOOGLE_OK"
    try:
        result = translation._translate("hello2", "en", "ml")
        check("fourth_request_does_not_call_sarvam", call_count["n"] == 0)
        check("fourth_request_still_reaches_google", result == "GOOGLE_OK")
    finally:
        translation.settings.SARVAM_API_KEY = original_key


def test_breaker_closes_after_cooldown_and_tries_normally():
    # Simulate 60+ seconds having elapsed, rather than sleeping in a test run.
    translation._sarvam_breaker._opened_at = time.monotonic() - 61
    is_open_after_cooldown = translation._sarvam_breaker.is_open()
    check("breaker_closes_after_cooldown_elapses", is_open_after_cooldown is False)
    check("breaker_resets_failure_count_on_close", translation._sarvam_breaker._consecutive_failures == 0)

    call_count = {"n": 0}

    def fake_sarvam_ok(text, source, target):
        call_count["n"] += 1
        return "SARVAM_OK"

    translation._sarvam_translate_one = fake_sarvam_ok
    original_key = translation.settings.SARVAM_API_KEY
    translation.settings.SARVAM_API_KEY = "fake-key-for-test"
    try:
        result = translation._translate("hello3", "en", "ml")
        check("post_cooldown_call_attempts_sarvam_normally", call_count["n"] == 1)
        check("post_cooldown_result_is_from_sarvam", result == "SARVAM_OK")
    finally:
        translation.settings.SARVAM_API_KEY = original_key


def test_sarvam_breaker_open_google_still_independently_serves():
    reset_breakers()
    translation._sarvam_breaker._consecutive_failures = 3
    translation._sarvam_breaker._opened_at = time.monotonic()
    call_count = {"sarvam": 0}

    def fake_sarvam_should_not_be_called(text, source, target):
        call_count["sarvam"] += 1
        return "SHOULD_NOT_HAPPEN"

    translation._sarvam_translate_one = fake_sarvam_should_not_be_called
    translation._google_translate = lambda t, s, tg: "GOOGLE_SERVED"
    original_key = translation.settings.SARVAM_API_KEY
    translation.settings.SARVAM_API_KEY = "fake-key-for-test"
    try:
        result = translation._translate("test", "en", "ml")
        check("sarvam_open_result_served_by_google", result == "GOOGLE_SERVED")
        check("sarvam_open_provider_never_called", call_count["sarvam"] == 0)
        check("google_breaker_independent_of_sarvam", not translation._google_breaker.is_open())
    finally:
        translation.settings.SARVAM_API_KEY = original_key


# =============================================================================
# TOTAL FAILURE RAISES
# =============================================================================

def test_raises_on_total_failure_sync():
    reset_breakers()
    original_key = translation.settings.SARVAM_API_KEY
    translation.settings.SARVAM_API_KEY = "fake-key-for-test"
    translation._sarvam_translate_one = _fail
    translation._google_translate = _fail
    try:
        raised = False
        try:
            translation._translate("test", "en", "ml")
        except TranslationUnavailableError:
            raised = True
        check("sync_raises_translation_unavailable_on_total_failure", raised)
    finally:
        translation.settings.SARVAM_API_KEY = original_key


async def _async_total_failure():
    translation._sarvam_translate_one_async = _fail_async
    translation._google_translate_async = _fail_async
    try:
        await translation._translate_async("test", "en", "ml")
        return False
    except TranslationUnavailableError:
        return True


def test_raises_on_total_failure_async():
    reset_breakers()
    original_key = translation.settings.SARVAM_API_KEY
    translation.settings.SARVAM_API_KEY = "fake-key-for-test"
    try:
        result = asyncio.run(_async_total_failure())
        check("async_raises_translation_unavailable_on_total_failure", result)
    finally:
        translation.settings.SARVAM_API_KEY = original_key


# =============================================================================
# SARVAM_API_KEY UNSET
# =============================================================================

def test_sarvam_key_unset_skips_to_google_no_error():
    reset_breakers()
    original_key = translation.settings.SARVAM_API_KEY
    translation.settings.SARVAM_API_KEY = ""
    call_count = {"sarvam": 0}

    def fake_sarvam_should_not_be_called(text, source, target):
        call_count["sarvam"] += 1
        return "SHOULD_NOT_BE_CALLED"

    translation._sarvam_translate_one = fake_sarvam_should_not_be_called
    translation._google_translate = lambda t, s, tg: "GOOGLE_ONLY"
    try:
        result = translation._translate("test", "en", "ml")
        check("key_unset_sarvam_never_called", call_count["sarvam"] == 0)
        check("key_unset_google_serves_directly", result == "GOOGLE_ONLY")
        check("key_unset_sarvam_breaker_untouched", translation._sarvam_breaker._consecutive_failures == 0)
    finally:
        translation.settings.SARVAM_API_KEY = original_key


# =============================================================================
# CHUNK SEAM SPACING
# =============================================================================

def test_chunked_translation_preserves_seam_spacing():
    """Prove that trailing whitespace at chunk seams is preserved after translation.

    _split_into_chunks keeps each chunk's trailing separator (e.g. ". "),
    but Sarvam does not return trailing whitespace — it only translates the
    content. The fix strips trailing whitespace before the provider call and
    re-attaches it afterwards, so the rejoined result is identical to the
    original apart from the translated words themselves.
    """
    reset_breakers()
    original_key = translation.settings.SARVAM_API_KEY
    translation.settings.SARVAM_API_KEY = "fake-key-for-test"
    calls = []

    def fake_sarvam_one(text, source, target):
        # Simulate Sarvam: return uppercase of the stripped text (no trailing space).
        calls.append(text)
        return text.upper()

    translation._sarvam_translate_one = fake_sarvam_one
    # Build a multi-chunk input: repeat a sentence so total length > 2000.
    # Each chunk produced by _split_into_chunks will end with ". " (space included).
    sentence = "Hello world. "
    text = sentence * 200  # 2600 chars — forces at least two chunks
    try:
        result = translation._sarvam_translate(text, "en", "ml")
        # Every call to the fake provider must have received a stripped chunk
        # (no trailing space) so Sarvam's "no trailing space" behaviour is simulated.
        check(
            "seam_provider_receives_stripped_chunks",
            all(not c.endswith(" ") for c in calls),
            f"provider received trailing-space chunk: {calls!r}",
        )
        # The result must be a prefix of sentence * 200 uppercased; specifically
        # the spaces at every seam must be present.
        check(
            "seam_spacing_preserved_in_result",
            result == text.upper(),
            f"expected {text.upper()!r}, got {result!r}",
        )
    finally:
        translation.settings.SARVAM_API_KEY = original_key


def main():
    original_sarvam_one = translation._sarvam_translate_one
    original_sarvam_one_async = translation._sarvam_translate_one_async
    original_google = translation._google_translate
    original_google_async = translation._google_translate_async
    original_key = translation.settings.SARVAM_API_KEY

    try:
        test_chunk_boundaries()
        test_hard_split_single_sentence_over_limit()
        test_sentence_boundary_chunking_and_rejoin()
        test_sarvam_chunks_and_joins_translated_output()
        test_any_chunk_failure_falls_whole_call_to_google()

        test_breaker_opens_on_third_consecutive_failure()
        test_fourth_call_skips_sarvam_while_breaker_open()
        test_breaker_closes_after_cooldown_and_tries_normally()
        test_sarvam_breaker_open_google_still_independently_serves()

        test_raises_on_total_failure_sync()
        test_raises_on_total_failure_async()

        test_sarvam_key_unset_skips_to_google_no_error()

        test_chunked_translation_preserves_seam_spacing()
    finally:
        translation._sarvam_translate_one = original_sarvam_one
        translation._sarvam_translate_one_async = original_sarvam_one_async
        translation._google_translate = original_google
        translation._google_translate_async = original_google_async
        translation.settings.SARVAM_API_KEY = original_key
        reset_breakers()

    print(f"\n{passed} passed, {failed} failed")
    if failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
