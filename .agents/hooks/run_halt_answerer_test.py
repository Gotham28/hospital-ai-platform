"""Standalone test script for `.agents/hooks/halt_answerer.py`.

No pytest, matching the `backend/run_*_test.py` convention in spirit (see
AGENTS.md §12.10a). Placed beside the hook rather than under `backend/` because
this is agent tooling, not production backend code (`.agents/CURRENT_TASK.md`,
"Files/areas in scope").

Every test builds synthetic fixture files under a fresh temporary directory and
monkeypatches the hook module's path constants to point there. No test ever
calls the real `claude` executable — the dispatch path is exercised through a
fake `invoke_answerer` that never spawns a subprocess. A test suite that spends
real Claude Pro usage on every run is a test nobody runs.

Fixture file mtimes are set explicitly via `os.utime()` rather than relied on
from real write order: two back-to-back `write_text()` calls can land on the
same timestamp on some filesystems, and the hook's own logic (an "already
answered" check, a "stale handoff from a previous task" check, and a halt-cap
reset check) all depend on precise mtime ordering between three separate
files. Explicit timestamps make that ordering unambiguous and reproducible.
"""

from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import os
import sys
import tempfile
import time
from pathlib import Path

HOOK_PATH = Path(__file__).resolve().parent / "halt_answerer.py"

passed = 0
failed = 0


def load_hook_module():
    """Fresh module instance per test, so module-level state (patched paths,
    monkeypatched functions) never bleeds between test cases."""
    spec = importlib.util.spec_from_file_location("halt_answerer_under_test", HOOK_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def patch_paths(module, tmp_path: Path):
    module.REPO_ROOT = tmp_path
    module.AGENTS_DIR = tmp_path / ".agents"
    module.HANDOFF_PATH = module.AGENTS_DIR / "LOOP_HANDOFF.md"
    module.DECISION_PATH = module.AGENTS_DIR / "DECISION.md"
    module.CURRENT_TASK_PATH = module.AGENTS_DIR / "CURRENT_TASK.md"
    module.RUNS_DIR = module.AGENTS_DIR / "runs"
    module.COUNTER_PATH = module.RUNS_DIR / "halt_answerer_counter.txt"


def write_current_task(module, body: str = "# Current Task\nFixture.\n") -> None:
    module.AGENTS_DIR.mkdir(parents=True, exist_ok=True)
    module.CURRENT_TASK_PATH.write_text(body, encoding="utf-8")


def write_handoff(module, trigger_body: str) -> None:
    module.AGENTS_DIR.mkdir(parents=True, exist_ok=True)
    module.HANDOFF_PATH.write_text(
        "# Handoff — 2026-09-02 (test fixture)\n\n"
        "## Task\nSynthetic fixture task.\n\n"
        f"## Halt trigger\n{trigger_body}\n\n"
        "## Where execution stopped\nStep 3 of ## Order.\n\n"
        "## The decision needed\nIs this a false alarm?\n",
        encoding="utf-8",
    )


def set_mtime(path: Path, when: float) -> None:
    os.utime(path, (when, when))


def setup_live_fixture(module, trigger_body: str, current_task_body: str | None = None) -> float:
    """The common case: CURRENT_TASK.md is scoped first, then a halt happens
    within that same task, so LOOP_HANDOFF.md ends up unambiguously newer than
    CURRENT_TASK.md (the hook's "stale handoff from a previous task" guard
    must NOT fire here). Returns the base timestamp used, so callers can build
    further mtimes (e.g. a DECISION.md) relative to it.
    """
    base = time.time() - 10_000
    write_current_task(module, current_task_body or "# Current Task\nFixture.\n")
    set_mtime(module.CURRENT_TASK_PATH, base)
    write_handoff(module, trigger_body)
    set_mtime(module.HANDOFF_PATH, base + 100)
    return base


def stdin_for(payload: dict) -> io.StringIO:
    return io.StringIO(json.dumps(payload))


def run_case(name: str, fn):
    global passed, failed
    try:
        fn()
    except AssertionError as exc:
        print(f"FAIL {name}")
        print(f"  {exc}")
        failed += 1
        return
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL {name}")
        print(f"  Unexpected exception: {exc!r}")
        failed += 1
        return
    print(f"PASS {name}")
    passed += 1


class ExplodingPath:
    """Stands in for a Path that must never be touched. Any attribute access
    fails the test loudly, proving the code path under test short-circuited
    before reaching it."""

    def __getattr__(self, name):
        raise AssertionError(f"HANDOFF_PATH.{name} was accessed — guard did not short-circuit first")


# ---------------------------------------------------------------------------
# stop_hook_active guard
# ---------------------------------------------------------------------------

def test_stop_hook_active_short_circuits():
    with tempfile.TemporaryDirectory() as tmp:
        module = load_hook_module()
        patch_paths(module, Path(tmp))
        module.HANDOFF_PATH = ExplodingPath()  # must never be read
        module.invoke_answerer = lambda *a, **k: (_ for _ in ()).throw(
            AssertionError("invoke_answerer must not be called")
        )
        result = module.main(stdin=stdin_for({"stop_hook_active": True}))
        assert result == 0, f"expected exit 0, got {result}"


# ---------------------------------------------------------------------------
# Missing handoff / already-answered / stale-handoff guards
# ---------------------------------------------------------------------------

def test_missing_handoff_exits():
    with tempfile.TemporaryDirectory() as tmp:
        module = load_hook_module()
        patch_paths(module, Path(tmp))
        # No LOOP_HANDOFF.md written at all.
        result = module.main(stdin=stdin_for({}))
        assert result == 0
        assert not module.DECISION_PATH.exists()


def test_newer_decision_already_answered_exits():
    with tempfile.TemporaryDirectory() as tmp:
        module = load_hook_module()
        patch_paths(module, Path(tmp))
        base = setup_live_fixture(module, "§12.5 condition 4 (same error hit three times).")
        original = "# Decision — already here\n\n## Answers\nX\n\n## Scope effect\nno change to CURRENT_TASK.md\n\n## Resume from\nY\n"
        module.DECISION_PATH.write_text(original, encoding="utf-8")
        set_mtime(module.DECISION_PATH, base + 200)  # newer than the handoff (base + 100)

        module.invoke_answerer = lambda *a, **k: (_ for _ in ()).throw(
            AssertionError("invoke_answerer must not be called when already answered")
        )
        result = module.main(stdin=stdin_for({}))
        assert result == 0
        assert module.DECISION_PATH.read_text(encoding="utf-8") == original, "DECISION.md must not be touched"


def test_stale_handoff_from_previous_task_is_skipped():
    """CURRENT_TASK.md is newer than LOOP_HANDOFF.md: this handoff predates the
    current task and must be left alone, not silently reprocessed."""
    with tempfile.TemporaryDirectory() as tmp:
        module = load_hook_module()
        patch_paths(module, Path(tmp))
        base = time.time() - 10_000
        write_handoff(module, "§12.5 condition 3 (scope change beyond ## Files/areas in scope).")
        set_mtime(module.HANDOFF_PATH, base)
        write_current_task(module)
        set_mtime(module.CURRENT_TASK_PATH, base + 100)  # newer: a new task started since

        module.invoke_answerer = lambda *a, **k: (_ for _ in ()).throw(
            AssertionError("must never dispatch on a stale, pre-task handoff")
        )
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            result = module.main(stdin=stdin_for({}))
        assert result == 0
        assert not module.DECISION_PATH.exists(), "a stale handoff must never be auto-answered"
        assert module.get_halt_count() == 0
        assert "previous, already-closed task" in buf.getvalue()


# ---------------------------------------------------------------------------
# Condition parsing
# ---------------------------------------------------------------------------

def test_unparseable_trigger_no_mention_exits_without_guessing():
    with tempfile.TemporaryDirectory() as tmp:
        module = load_hook_module()
        patch_paths(module, Path(tmp))
        setup_live_fixture(module, "The build broke for reasons unrelated to any numbered condition.")
        module.invoke_answerer = lambda *a, **k: (_ for _ in ()).throw(
            AssertionError("must never dispatch on an unparseable trigger")
        )
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            result = module.main(stdin=stdin_for({}))
        assert result == 0
        assert not module.DECISION_PATH.exists()
        assert "could not unambiguously parse" in buf.getvalue()


def test_unparseable_trigger_ambiguous_two_numbers_exits_without_guessing():
    with tempfile.TemporaryDirectory() as tmp:
        module = load_hook_module()
        patch_paths(module, Path(tmp))
        setup_live_fixture(
            module,
            "Unclear whether this is §12.5 condition 3 or condition 4 — both patterns matched.",
        )
        module.invoke_answerer = lambda *a, **k: (_ for _ in ()).throw(
            AssertionError("must never dispatch on an ambiguous trigger")
        )
        result = module.main(stdin=stdin_for({}))
        assert result == 0
        assert not module.DECISION_PATH.exists()


def test_extract_condition_number_direct():
    module = load_hook_module()
    text = "## Halt trigger\n§12.5 condition 6 (fails the §12.4 reversibility test).\n\n## Next\nirrelevant condition 2 mention here\n"
    assert module.extract_condition_number(text) == "6"
    assert module.extract_condition_number("## Halt trigger\nno numbers here\n") is None
    assert module.extract_condition_number("no heading at all") is None


# ---------------------------------------------------------------------------
# Conditions 1, 2, 5 — developer-only, never dispatched
# ---------------------------------------------------------------------------

def _assert_developer_only(condition_label: str, trigger_body: str):
    with tempfile.TemporaryDirectory() as tmp:
        module = load_hook_module()
        patch_paths(module, Path(tmp))
        setup_live_fixture(module, trigger_body)
        module.invoke_answerer = lambda *a, **k: (_ for _ in ()).throw(
            AssertionError(f"condition {condition_label} must never dispatch")
        )
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            result = module.main(stdin=stdin_for({}))
        assert result == 0
        assert not module.DECISION_PATH.exists()
        assert "developer-only" in buf.getvalue()


def test_condition_1_developer_only():
    _assert_developer_only("1", "§12.5 condition 1 (any Alembic migration, drafted or applied).")


def test_condition_2_developer_only():
    _assert_developer_only("2", "§12.5 condition 2 (a §10 Opus trigger fired: a hospital_id filter changed).")


def test_condition_5_developer_only():
    _assert_developer_only("5", "§12.5 condition 5 (anything in §9 — non-local database command).")


# ---------------------------------------------------------------------------
# Condition 3 — deterministic, no dispatch, one-way door
# ---------------------------------------------------------------------------

def test_condition_3_writes_fixed_answer_no_dispatch():
    with tempfile.TemporaryDirectory() as tmp:
        module = load_hook_module()
        patch_paths(module, Path(tmp))
        setup_live_fixture(module, "§12.5 condition 3 (scope change beyond ## Files/areas in scope).")
        module.invoke_answerer = lambda *a, **k: (_ for _ in ()).throw(
            AssertionError("condition 3 must never invoke a model")
        )
        result = module.main(stdin=stdin_for({}))
        assert result == 0
        assert module.DECISION_PATH.exists(), "condition 3 must write DECISION.md itself"
        text = module.DECISION_PATH.read_text(encoding="utf-8")
        assert module.validate_decision_text(text)
        assert text.count("## Scope effect") == 1
        assert module.get_halt_count() == 1


def test_condition_3_scope_effect_can_never_widen():
    module = load_hook_module()
    for _ in range(5):
        text = module.build_condition3_decision(module.utc_timestamp())
        assert module.validate_decision_text(text)
        assert "no change to CURRENT_TASK.md" in text
        assert "widen" not in text.lower()


# ---------------------------------------------------------------------------
# Condition 4 — deterministic, no dispatch, same pattern as condition 3
# ---------------------------------------------------------------------------

def test_condition_4_writes_fixed_answer_no_dispatch():
    with tempfile.TemporaryDirectory() as tmp:
        module = load_hook_module()
        patch_paths(module, Path(tmp))
        setup_live_fixture(module, "§12.5 condition 4 (same error hit three times).")
        module.invoke_answerer = lambda *a, **k: (_ for _ in ()).throw(
            AssertionError("condition 4 must never invoke a model")
        )
        result = module.main(stdin=stdin_for({}))
        assert result == 0
        assert module.DECISION_PATH.exists(), "condition 4 must write DECISION.md itself"
        text = module.DECISION_PATH.read_text(encoding="utf-8")
        assert module.validate_decision_text(text)
        assert module.CONDITION_4_FIXED_TEXT in text
        assert module.get_halt_count() == 1


# ---------------------------------------------------------------------------
# Condition 6 — the only condition that still dispatches a model
# ---------------------------------------------------------------------------

VALID_DECISION_TEXT = (
    "# Decision — 2026-09-02 00:00:00 UTC\n\n"
    "## Answers\nFixed answer text.\n\n"
    "## Scope effect\nno change to CURRENT_TASK.md\n\n"
    "## Resume from\nStep 4.\n"
)

SCOPE_WIDENING_DECISION_TEXT = (
    "# Decision — 2026-09-02 00:00:00 UTC\n\n"
    "## Answers\nWiden scope to also touch backend/app/services/security.py.\n\n"
    "## Scope effect\nAdd services/security.py to ## Files/areas in scope.\n\n"
    "## Resume from\nStep 4.\n"
)


def _fake_invoke_writing(module, content):
    """Simulates the answerer editing the placeholder to real content. Bumps
    the mtime explicitly forward rather than relying on real wall-clock delta
    between the placeholder write (in `dispatch_and_validate`) and this fake's
    write landing in the same test call — avoids flakiness on filesystems with
    coarser mtime resolution."""
    calls = []

    def fake(cmd, prompt, env):
        calls.append(cmd)
        pre = module.DECISION_PATH.stat().st_mtime if module.DECISION_PATH.exists() else time.time()
        module.DECISION_PATH.write_text(content, encoding="utf-8")
        set_mtime(module.DECISION_PATH, pre + 5)
        return None

    return fake, calls


def _fake_invoke_writing_nothing():
    """Simulates the answerer correctly leaving the placeholder untouched."""
    calls = []

    def fake(cmd, prompt, env):
        calls.append(cmd)
        return None

    return fake, calls


def test_condition_6_valid_dispatch_writes_and_counts():
    with tempfile.TemporaryDirectory() as tmp:
        module = load_hook_module()
        patch_paths(module, Path(tmp))
        setup_live_fixture(module, "§12.5 condition 6 (fails the §12.4 reversibility test).")
        fake, calls = _fake_invoke_writing(module, VALID_DECISION_TEXT)
        module.invoke_answerer = fake
        result = module.main(stdin=stdin_for({}))
        assert result == 0
        assert len(calls) == 1, "answerer should be dispatched exactly once"
        cmd = calls[0]
        assert "--dangerously-skip-permissions" not in cmd
        assert "--allow-dangerously-skip-permissions" not in cmd
        assert "--add-dir" in cmd
        assert module.DECISION_PATH.read_text(encoding="utf-8") == VALID_DECISION_TEXT
        assert module.get_halt_count() == 1


def test_condition_6_false_alarm_not_confirmed_writes_nothing():
    """One of the four §12.4 reversibility parts is false: the answerer correctly
    writes nothing. The halt stands for the developer, but the dispatch still
    happened and real usage was still spent, so it still counts toward the cap.
    """
    with tempfile.TemporaryDirectory() as tmp:
        module = load_hook_module()
        patch_paths(module, Path(tmp))
        setup_live_fixture(module, "§12.5 condition 6 (fails the §12.4 reversibility test).")
        fake, calls = _fake_invoke_writing_nothing()
        module.invoke_answerer = fake
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            result = module.main(stdin=stdin_for({}))
        assert result == 0
        assert len(calls) == 1, "the answerer is still dispatched to make the determination"
        assert not module.DECISION_PATH.exists()
        assert module.get_halt_count() == 1, "a real dispatch attempt still spends usage and counts toward the cap"
        assert "stands for the developer" in buf.getvalue()


def test_scope_widening_output_is_discarded():
    with tempfile.TemporaryDirectory() as tmp:
        module = load_hook_module()
        patch_paths(module, Path(tmp))
        setup_live_fixture(module, "§12.5 condition 6 (fails the §12.4 reversibility test).")
        fake, calls = _fake_invoke_writing(module, SCOPE_WIDENING_DECISION_TEXT)
        module.invoke_answerer = fake
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            result = module.main(stdin=stdin_for({}))
        assert result == 0
        assert not module.DECISION_PATH.exists(), "a scope-widening decision must be discarded, not left in place"
        assert module.get_halt_count() == 1, "the attempt itself still spends usage and counts toward the cap"
        assert "Discarded" in buf.getvalue()


def test_missing_claude_executable_fails_closed():
    with tempfile.TemporaryDirectory() as tmp:
        module = load_hook_module()
        patch_paths(module, Path(tmp))
        setup_live_fixture(module, "§12.5 condition 6 (fails the §12.4 reversibility test).")
        module.shutil.which = lambda name: None
        module.invoke_answerer = lambda *a, **k: (_ for _ in ()).throw(
            AssertionError("must not invoke when claude is not on PATH")
        )
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            result = module.main(stdin=stdin_for({}))
        assert result == 0
        assert not module.DECISION_PATH.exists()
        assert module.get_halt_count() == 0, "no real dispatch was attempted, so it must not count toward the cap"
        assert "not found on PATH" in buf.getvalue()
        assert "Failing closed" in buf.getvalue()


# ---------------------------------------------------------------------------
# ANTHROPIC_API_KEY cost guard
# ---------------------------------------------------------------------------

def test_anthropic_api_key_set_refuses_everything():
    with tempfile.TemporaryDirectory() as tmp:
        module = load_hook_module()
        patch_paths(module, Path(tmp))
        setup_live_fixture(module, "§12.5 condition 3 (scope change beyond ## Files/areas in scope).")
        module.invoke_answerer = lambda *a, **k: (_ for _ in ()).throw(
            AssertionError("must not dispatch when ANTHROPIC_API_KEY is set")
        )
        sentinel = "sk-ant-fixture-do-not-use"
        old = os.environ.get("ANTHROPIC_API_KEY")
        os.environ["ANTHROPIC_API_KEY"] = sentinel
        try:
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                result = module.main(stdin=stdin_for({}))
        finally:
            if old is None:
                del os.environ["ANTHROPIC_API_KEY"]
            else:
                os.environ["ANTHROPIC_API_KEY"] = old
        assert result == 0
        assert not module.DECISION_PATH.exists(), "condition 3 would normally write a decision; the guard must pre-empt it"
        assert sentinel not in buf.getvalue(), "the key's value must never be printed"


# ---------------------------------------------------------------------------
# Three-halt cap
# ---------------------------------------------------------------------------

def test_halt_cap_stops_at_three():
    with tempfile.TemporaryDirectory() as tmp:
        module = load_hook_module()
        patch_paths(module, Path(tmp))
        base = setup_live_fixture(module, "§12.5 condition 3 (scope change beyond ## Files/areas in scope).")
        module.RUNS_DIR.mkdir(parents=True, exist_ok=True)
        module.COUNTER_PATH.write_text("3", encoding="utf-8")
        set_mtime(module.COUNTER_PATH, base + 50)  # newer than CURRENT_TASK.md: cap holds

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            result = module.main(stdin=stdin_for({}))
        assert result == 0
        assert not module.DECISION_PATH.exists(), "cap reached: must not auto-answer even a deterministic condition 3"
        assert module.get_halt_count() == 3, "cap check must not itself increment the counter"
        assert "three-halt cap" in buf.getvalue()


def test_halt_cap_resets_on_new_task_and_handoff_is_still_live():
    """A new task starts (CURRENT_TASK.md rewritten after the old counter),
    which must reset the cap — and separately, LOOP_HANDOFF.md is written
    within that same new task (after CURRENT_TASK.md), so it is NOT stale and
    must still be processed. This isolates the cap-reset behaviour from the
    stale-handoff guard: they key off two different file pairs.
    """
    with tempfile.TemporaryDirectory() as tmp:
        module = load_hook_module()
        patch_paths(module, Path(tmp))
        base = time.time() - 10_000

        module.RUNS_DIR.mkdir(parents=True, exist_ok=True)
        module.COUNTER_PATH.write_text("3", encoding="utf-8")
        set_mtime(module.COUNTER_PATH, base)  # oldest: predates the new task

        write_current_task(module)
        set_mtime(module.CURRENT_TASK_PATH, base + 50)  # newer than counter -> cap resets

        write_handoff(module, "§12.5 condition 3 (scope change beyond ## Files/areas in scope).")
        set_mtime(module.HANDOFF_PATH, base + 100)  # newer than task -> not stale

        result = module.main(stdin=stdin_for({}))
        assert result == 0
        assert module.DECISION_PATH.exists(), "a new task must reset the cap and still process its own live handoff"
        assert module.get_halt_count() == 1


# ---------------------------------------------------------------------------
# Crash safety — a Stop hook must never raise
# ---------------------------------------------------------------------------

def test_non_utf8_handoff_fails_safe_instead_of_crashing():
    with tempfile.TemporaryDirectory() as tmp:
        module = load_hook_module()
        patch_paths(module, Path(tmp))
        write_current_task(module)
        module.AGENTS_DIR.mkdir(parents=True, exist_ok=True)
        # Invalid UTF-8 bytes (a lone continuation byte) — read_text(encoding="utf-8") raises.
        module.HANDOFF_PATH.write_bytes(b"# Handoff\n\n## Halt trigger\ncondition 4 \xff\xfe garbage\n")
        set_mtime(module.CURRENT_TASK_PATH, time.time() - 10_000)
        set_mtime(module.HANDOFF_PATH, time.time() - 9_900)  # newer than task -> not "stale"

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            result = module.main(stdin=stdin_for({}))
        assert result == 0, "a Stop hook must exit 0 even when a fixture file can't be decoded"
        assert not module.DECISION_PATH.exists()
        assert "unexpected error" in buf.getvalue()


# ---------------------------------------------------------------------------
# build_claude_command — static safety assertions
# ---------------------------------------------------------------------------

def test_build_claude_command_never_bypasses_permissions():
    module = load_hook_module()
    cmd = module.build_claude_command()
    joined = " ".join(cmd)
    assert "--dangerously-skip-permissions" not in joined
    assert "--allow-dangerously-skip-permissions" not in joined
    assert "--add-dir" in cmd
    assert "--restricted" in cmd
    assert "sonnet" in cmd
    # Defense in depth: Write is disallowed outright (path-scoped Write rules
    # are not enforced by Claude Code — Edit is used for the one permitted
    # write instead), alongside the code-execution/network tools --restricted
    # already strips.
    assert "--disallowedTools" in cmd
    disallowed_index = cmd.index("--disallowedTools")
    disallowed_value = cmd[disallowed_index + 1]
    for tool in ("Bash", "PowerShell", "WebFetch", "Write"):
        assert tool in disallowed_value, f"{tool} missing from --disallowedTools"
    # And the one permitted write path uses Edit, never Write, with a path scope.
    allowed_index = cmd.index("--allowedTools")
    allowed_value = cmd[allowed_index + 1]
    assert "Edit(" in allowed_value
    assert "Write(" not in allowed_value


def main():
    tests = [
        test_stop_hook_active_short_circuits,
        test_missing_handoff_exits,
        test_newer_decision_already_answered_exits,
        test_stale_handoff_from_previous_task_is_skipped,
        test_unparseable_trigger_no_mention_exits_without_guessing,
        test_unparseable_trigger_ambiguous_two_numbers_exits_without_guessing,
        test_extract_condition_number_direct,
        test_condition_1_developer_only,
        test_condition_2_developer_only,
        test_condition_5_developer_only,
        test_condition_3_writes_fixed_answer_no_dispatch,
        test_condition_3_scope_effect_can_never_widen,
        test_condition_4_writes_fixed_answer_no_dispatch,
        test_condition_6_valid_dispatch_writes_and_counts,
        test_condition_6_false_alarm_not_confirmed_writes_nothing,
        test_scope_widening_output_is_discarded,
        test_missing_claude_executable_fails_closed,
        test_anthropic_api_key_set_refuses_everything,
        test_halt_cap_stops_at_three,
        test_halt_cap_resets_on_new_task_and_handoff_is_still_live,
        test_non_utf8_handoff_fails_safe_instead_of_crashing,
        test_build_claude_command_never_bypasses_permissions,
    ]
    for test in tests:
        run_case(test.__name__, test)

    print(f"\n{passed} passed, {failed} failed")
    if failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
