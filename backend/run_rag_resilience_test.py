"""
Standalone test for the RAG-embedding-failure resilience fix.

Covers two independent guarantees added to fix the silent-empty-reply bug
(production, 2026-09-04): an OpenAI embeddings 429/RateLimitError inside
build_context() must degrade to "no retrieved documents" rather than raise,
and ANY unhandled exception inside chat_stream's event_generator must reach
the client as a well-formed SSE error event instead of just killing the
connection after 200 OK has already been sent.

No pytest. No real network — OpenAI, Redis (via the existing try/except in
_load_patient_ctx) and the DB session are all monkeypatched/mocked. Matches
the run_translation_test.py / run_chat_stream_sentinel_test.py convention.

ai.py is imported via importlib.import_module rather than a plain `import`,
because app/api/v1/endpoints/__init__.py does `from .ai import router as ai`,
which overwrites the package's own `ai` attribute with the router object —
`import app.api.v1.endpoints.ai as ai` resolves via attribute access and
would silently bind the router, not the module.
"""
import asyncio
import importlib
import json
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock

import httpx
import openai

ai = importlib.import_module("app.api.v1.endpoints.ai")
import app.services.rag as rag
from app.models.hospital import Hospital
from app.models.doctor import Doctor
from app.models.medicine import Medicine
from app.models.lab_test import LabTest
from app.models.knowledge import KnowledgeBase

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


def _make_query_chain(first=None, all_=None):
    m = MagicMock()
    m.filter.return_value = m
    m.order_by.return_value = m
    m.limit.return_value = m
    m.first.return_value = first
    m.all.return_value = all_ if all_ is not None else []
    return m


def _make_db(query_map):
    db = MagicMock()
    db.query.side_effect = lambda model: query_map[model]
    return db


def _make_rate_limit_error() -> openai.RateLimitError:
    request = httpx.Request("POST", "https://api.openai.com/v1/embeddings")
    response = httpx.Response(
        429,
        request=request,
        json={"error": {"message": "You exceeded your current quota.",
                         "type": "insufficient_quota", "code": "insufficient_quota"}},
    )
    return openai.RateLimitError("insufficient_quota", response=response, body=None)


class _RaisingEmbeddings:
    def create(self, **kwargs):
        raise _make_rate_limit_error()


class _RaisingClient:
    def with_options(self, **kwargs):
        return SimpleNamespace(embeddings=_RaisingEmbeddings())


async def _collect_frames(response) -> list:
    frames = []
    async for chunk in response.body_iterator:
        frames.append(chunk)
    return frames


def _frame_payload(frame: str) -> str:
    assert frame.startswith("data: ")
    assert frame.endswith("\n\n")
    return frame[len("data: "):-2]


# =============================================================================
# TEST 1 — build_context() degrades gracefully on embedding failure (A2, unit)
# =============================================================================

def test_build_context_degrades_on_embedding_failure():
    fake_hospital = SimpleNamespace(
        id=1, name="Test Hospital", system_prompt="", post_booking_disclaimer=None,
    )
    db = _make_db({
        Hospital: _make_query_chain(first=fake_hospital),
        Medicine: _make_query_chain(all_=[]),
        LabTest: _make_query_chain(all_=[]),
        Doctor: _make_query_chain(all_=[]),
        KnowledgeBase: _make_query_chain(all_=[]),
    })

    request = ai.ChatRequest(
        question="What tests do you offer for diabetes",
        hospital_id=1,
        language="en",
        session_token="test-rag-resilience",
    )

    original_client = rag.client
    rag.client = _RaisingClient()
    raised = False
    result = None
    try:
        result = rag.build_context(request, db, force_english=False, session_token="test-rag-resilience")
    except Exception as e:
        raised = True
        detail = f"{type(e).__name__}: {e}"
    finally:
        rag.client = original_client

    check("build_context_does_not_raise_on_embedding_429", not raised,
          detail if raised else "")

    if not raised:
        system_prompt, openai_messages, hospital = result
        check("build_context_returns_all_three_values", hospital is fake_hospital)
        check("build_context_has_no_retrieved_kb_documents",
              "ADDITIONAL KNOWLEDGE BASE:" not in system_prompt,
              f"system_prompt contains a KB section despite the embedding call failing:\n{system_prompt[:400]}")
        check("build_context_still_produced_a_user_message",
              openai_messages and openai_messages[-1]["role"] == "user")


# =============================================================================
# TEST 2 — chat-stream still answers when the KB embedding call fails (A2+A8)
# =============================================================================

class _FakeFunction:
    def __init__(self, name=None, arguments=None):
        self.name = name
        self.arguments = arguments


class _FakeDelta:
    def __init__(self, tool_calls=None, content=None):
        self.tool_calls = tool_calls
        self.content = content


class _FakeChoice:
    def __init__(self, delta):
        self.delta = delta


class _FakeChunk:
    def __init__(self, choices, usage=None):
        self.choices = choices
        self.usage = usage


async def _fake_content_stream():
    yield _FakeChunk(choices=[_FakeChoice(_FakeDelta(content="Hello"))])
    yield _FakeChunk(choices=[_FakeChoice(_FakeDelta(content=" there!"))])


async def _fake_openai_create(**kwargs):
    return _fake_content_stream()


async def _async_return(value):
    return value


async def _run_embedding_failure_scenario():
    fake_hospital = SimpleNamespace(
        id=1, name="Test Hospital", system_prompt="", relevance_criteria=None,
        post_booking_disclaimer=None,
    )
    db = _make_db({
        Hospital: _make_query_chain(first=fake_hospital),
        Medicine: _make_query_chain(all_=[]),
        LabTest: _make_query_chain(all_=[]),
        Doctor: _make_query_chain(all_=[]),
        KnowledgeBase: _make_query_chain(all_=[]),
    })

    request = ai.ChatRequest(
        question="What tests do you offer for diabetes",
        hospital_id=1,
        language="en",
        session_token="test-rag-resilience-e2e",
    )

    response = await ai.chat_stream(request, db)
    return await _collect_frames(response)


def test_chat_stream_still_answers_when_embedding_fails():
    original_classify = ai.classify_user_intent
    original_update_ctx = ai._update_patient_ctx
    original_create = ai.async_client.chat.completions.create
    original_rag_client = rag.client

    ai.classify_user_intent = lambda *a, **kw: _async_return("OTHER")
    ai._update_patient_ctx = lambda *a, **kw: {}
    ai.async_client.chat.completions.create = _fake_openai_create
    rag.client = _RaisingClient()
    try:
        frames = asyncio.run(_run_embedding_failure_scenario())
    finally:
        ai.classify_user_intent = original_classify
        ai._update_patient_ctx = original_update_ctx
        ai.async_client.chat.completions.create = original_create
        rag.client = original_rag_client

    check("no_stream_error_frame_emitted", "data: [STREAM_ERROR]\n\n" not in frames, f"frames={frames}")
    check("done_frame_present", "data: [DONE]\n\n" in frames, f"frames={frames}")

    content_frames = [
        f for f in frames
        if f != "data: [DONE]\n\n" and f.startswith("data: ")
    ]
    assembled = ""
    for f in content_frames:
        payload = _frame_payload(f)
        try:
            assembled += json.loads(payload)
        except json.JSONDecodeError:
            pass
    check("chat_stream_produced_non_empty_answer", assembled.strip() != "", f"assembled={assembled!r} frames={frames}")


# =============================================================================
# TEST 3 — a generic unhandled exception inside the generator still reaches
# the client as [STREAM_ERROR], and the stream still closes cleanly (A3+A8)
# =============================================================================

async def _run_generic_exception_scenario():
    fake_hospital = SimpleNamespace(id=1, name="Test Hospital", relevance_criteria=None)
    db = _make_db({
        Hospital: _make_query_chain(first=fake_hospital),
    })

    request = ai.ChatRequest(
        question="Trigger an unexpected backend failure",
        hospital_id=1,
        language="en",
        session_token="test-stream-boundary",
    )

    response = await ai.chat_stream(request, db)
    return await _collect_frames(response)


def test_stream_emits_error_event_on_unexpected_exception():
    original_classify = ai.classify_user_intent
    original_update_ctx = ai._update_patient_ctx
    original_build_context = ai.build_context

    ai.classify_user_intent = lambda *a, **kw: _async_return("OTHER")
    ai._update_patient_ctx = lambda *a, **kw: {}
    ai.build_context = MagicMock(side_effect=RuntimeError("simulated unexpected failure"))
    try:
        frames = asyncio.run(_run_generic_exception_scenario())
    finally:
        ai.classify_user_intent = original_classify
        ai._update_patient_ctx = original_update_ctx
        ai.build_context = original_build_context

    check("stream_error_frame_present", "data: [STREAM_ERROR]\n\n" in frames, f"frames={frames}")
    check("done_frame_present_after_error", "data: [DONE]\n\n" in frames, f"frames={frames}")
    check("stream_error_is_the_last_content_frame_before_done",
          frames and frames[-2:] == ["data: [STREAM_ERROR]\n\n", "data: [DONE]\n\n"],
          f"frames={frames}")

    error_payload = _frame_payload("data: [STREAM_ERROR]\n\n")
    raised = False
    try:
        json.loads(error_payload)
    except json.JSONDecodeError:
        raised = True
    check("stream_error_payload_is_a_raw_sentinel_not_json", raised, f"payload={error_payload!r}")


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    test_build_context_degrades_on_embedding_failure()
    test_chat_stream_still_answers_when_embedding_fails()
    test_stream_emits_error_event_on_unexpected_exception()

    print(f"\n{passed} passed, {failed} failed")
    if failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
