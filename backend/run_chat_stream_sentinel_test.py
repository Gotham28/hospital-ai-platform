"""
Standalone test for the [TRANSLATION_UNAVAILABLE] SSE sentinel added to the two
English-to-Malayalam TranslationUnavailableError branches inside /chat-stream's
event_generator (STATUS reply site, booking-validation-error site).

No pytest. No real network — OpenAI, the translation call, and the DB session
are all monkeypatched/mocked. Matches the run_translation_test.py /
run_ml_postprocess_test.py convention.

ai.py is imported via importlib.import_module rather than a plain `import`,
because app/api/v1/endpoints/__init__.py does `from .ai import router as ai`,
which overwrites the package's own `ai` attribute with the router object —
`import app.api.v1.endpoints.ai as ai` resolves via attribute access and would
silently bind the router, not the module.
"""
import asyncio
import importlib
import json
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock

ai = importlib.import_module("app.api.v1.endpoints.ai")
from app.services.translation import TranslationUnavailableError
from app.models.hospital import Hospital
from app.models.doctor import Doctor
from app.models.appointment import Appointment
import app.services.booking_rules as booking_rules

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


SENTINEL_FRAME = "data: [TRANSLATION_UNAVAILABLE]\n\n"


def _frame_payload(frame: str) -> str:
    """Strip the SSE 'data: ' prefix and trailing '\\n\\n'."""
    assert frame.startswith("data: ")
    assert frame.endswith("\n\n")
    return frame[len("data: "):-2]


async def fake_translate(text, source, target):
    if source == "ml" and target == "en":
        return "check status for 9876543210"
    if source == "en" and target == "ml":
        raise TranslationUnavailableError("simulated failure")
    raise AssertionError(f"unexpected translate call direction: {source}->{target}")


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


async def _collect_frames(response) -> list:
    frames = []
    async for chunk in response.body_iterator:
        frames.append(chunk)
    return frames


# =============================================================================
# SCENARIO 1 — STATUS reply site
# =============================================================================

async def _run_status_scenario():
    fake_doctor = SimpleNamespace(name="Dr. Test")
    fake_appt = SimpleNamespace(
        doctor_id=1,
        preferred_date="2026-09-10",
        time_of_day="morning",
        status="approved",
        confirmed_time="10:00 AM",
        rejection_reason=None,
        reference_number="REF123",
    )
    db = _make_db({
        Appointment: _make_query_chain(all_=[fake_appt]),
        Doctor: _make_query_chain(first=fake_doctor),
    })

    request = ai.ChatRequest(
        question="What is my appointment status",
        hospital_id=1,
        language="ml",
        session_token="test-status-sentinel",
    )

    response = await ai.chat_stream(request, db)
    return await _collect_frames(response)


def test_status_site_emits_sentinel():
    original_translate = ai._translate_async
    original_classify = ai.classify_user_intent
    original_update_ctx = ai._update_patient_ctx
    ai._translate_async = fake_translate
    ai.classify_user_intent = lambda *a, **kw: _async_return("STATUS")
    ai._update_patient_ctx = lambda *a, **kw: {}
    try:
        frames = asyncio.run(_run_status_scenario())
    finally:
        ai._translate_async = original_translate
        ai.classify_user_intent = original_classify
        ai._update_patient_ctx = original_update_ctx

    check("status_site_sentinel_frame_present", SENTINEL_FRAME in frames, f"frames={frames}")

    other_json_frames = [
        f for f in frames
        if f != SENTINEL_FRAME and f != "data: [DONE]\n\n" and f.startswith("data: ")
    ]
    check("status_site_has_a_normal_frame_too", len(other_json_frames) >= 1, f"frames={frames}")
    if other_json_frames:
        payload = _frame_payload(other_json_frames[0])
        parsed_ok = True
        try:
            json.loads(payload)
        except json.JSONDecodeError:
            parsed_ok = False
        check("status_site_normal_frame_is_valid_json", parsed_ok, f"payload={payload!r}")

    sentinel_payload = _frame_payload(SENTINEL_FRAME)
    raised = False
    try:
        json.loads(sentinel_payload)
    except json.JSONDecodeError:
        raised = True
    check("status_site_sentinel_payload_is_invalid_json", raised, f"payload={sentinel_payload!r}")


# =============================================================================
# SCENARIO 2 — booking-validation-error site
# =============================================================================

class _FakeFunction:
    def __init__(self, name=None, arguments=None):
        self.name = name
        self.arguments = arguments


class _FakeToolCall:
    def __init__(self, function):
        self.function = function


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


async def _fake_stream_gen():
    booking_args = json.dumps({
        "doctor_id": 1,
        "preferred_date": "2026-09-10",
        "time_of_day": "morning",
        "patient_name": "Test Patient",
        "patient_age": "30",
        "patient_phone": "9876543210",
    })
    yield _FakeChunk(choices=[_FakeChoice(_FakeDelta(
        tool_calls=[_FakeToolCall(_FakeFunction(name="book_appointment", arguments=""))]
    ))])
    yield _FakeChunk(choices=[_FakeChoice(_FakeDelta(
        tool_calls=[_FakeToolCall(_FakeFunction(name=None, arguments=booking_args))]
    ))])


async def _fake_openai_create(**kwargs):
    return _fake_stream_gen()


def _fake_build_context(*args, **kwargs):
    system_prompt = "system prompt"
    openai_messages = [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "hi"},
    ]
    hospital = SimpleNamespace(relevance_criteria=None)
    return system_prompt, openai_messages, hospital


def _fake_validate_booking(hospital, doctor, preferred_date, db):
    return False, "The requested slot is no longer available."


async def _async_return(value):
    return value


async def _run_booking_scenario():
    fake_hospital = SimpleNamespace(relevance_criteria=None)
    fake_doctor = SimpleNamespace(id=1)
    db = _make_db({
        Hospital: _make_query_chain(first=fake_hospital),
        Doctor: _make_query_chain(first=fake_doctor),
    })

    request = ai.ChatRequest(
        question="I would like to book an appointment",
        hospital_id=1,
        language="ml",
        session_token="test-booking-sentinel",
    )

    response = await ai.chat_stream(request, db)
    return await _collect_frames(response)


def test_booking_site_emits_sentinel():
    original_translate = ai._translate_async
    original_classify = ai.classify_user_intent
    original_update_ctx = ai._update_patient_ctx
    original_build_context = ai.build_context
    original_create = ai.async_client.chat.completions.create
    original_validate_booking = booking_rules.validate_booking

    ai._translate_async = fake_translate
    ai.classify_user_intent = lambda *a, **kw: _async_return("BOOKING")
    ai._update_patient_ctx = lambda *a, **kw: {}
    ai.build_context = _fake_build_context
    ai.async_client.chat.completions.create = _fake_openai_create
    booking_rules.validate_booking = _fake_validate_booking
    try:
        frames = asyncio.run(_run_booking_scenario())
    finally:
        ai._translate_async = original_translate
        ai.classify_user_intent = original_classify
        ai._update_patient_ctx = original_update_ctx
        ai.build_context = original_build_context
        ai.async_client.chat.completions.create = original_create
        booking_rules.validate_booking = original_validate_booking

    check("booking_site_sentinel_frame_present", SENTINEL_FRAME in frames, f"frames={frames}")

    other_json_frames = [
        f for f in frames
        if f != SENTINEL_FRAME and f != "data: [DONE]\n\n" and f.startswith("data: ")
    ]
    check("booking_site_has_a_normal_frame_too", len(other_json_frames) >= 1, f"frames={frames}")
    if other_json_frames:
        payload = _frame_payload(other_json_frames[0])
        parsed_ok = True
        try:
            json.loads(payload)
        except json.JSONDecodeError:
            parsed_ok = False
        check("booking_site_normal_frame_is_valid_json", parsed_ok, f"payload={payload!r}")

    sentinel_payload = _frame_payload(SENTINEL_FRAME)
    raised = False
    try:
        json.loads(sentinel_payload)
    except json.JSONDecodeError:
        raised = True
    check("booking_site_sentinel_payload_is_invalid_json", raised, f"payload={sentinel_payload!r}")


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    test_status_site_emits_sentinel()
    test_booking_site_emits_sentinel()

    print(f"\n{passed} passed, {failed} failed")
    if failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
