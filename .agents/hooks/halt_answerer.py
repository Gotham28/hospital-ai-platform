"""Claude Code `Stop` hook — the unattended halt loop's auto-answerer.

Adversarial testing on 2026-09-02, against the exact `build_claude_command()`
output in an isolated disposable temp directory, confirmed the write
restriction live, on this machine/version, in both directions required:
(a) the bare `Write` tool is fully blocked (`--disallowedTools` includes it)
— a decoy file outside `.agents/DECISION.md` was unreachable via Write; (b)
a second round then targeted `Edit`'s own path-scoping specifically (not
just the Write block) — the model was explicitly instructed to use Edit
against a pre-existing decoy file, and it was denied, while in the SAME run
Edit succeeded against `.agents/DECISION.md`. Because the same tool (Edit)
both failed against one path and succeeded against the other in one
session, the denial can only be explained by path-scoping — not a blanket
Edit-tool block, which round 1 already ruled out as the mechanism at risk
(the actual denial message itself is a generic "permission not granted for
this path" string, not one that names "path-scoping" in words; the proof is
in the differential outcome, not the message text). This directly answers
the failure mode described in two open GitHub issues (anthropics/claude-code
#1188, #67849 — path-specific `allowedTools` rules silently ignored in
headless `-p` mode on Windows): it did not reproduce here, on Claude Code
`2.1.250`, with this exact flag set. `.claude/settings.json` registration
remains the developer's own action regardless of this result — nothing here
authorizes registering the hook automatically.

---

Governed by `.agents/AGENTS.md` §12.5/§12.6/§12.7/§12.15 and
`.agents/CURRENT_TASK.md` (2026-09-02, "unattended halt loop"). Do not change the
per-condition behaviour here without a corresponding AGENTS.md edit approved by the
developer first — this file implements what those sections describe, it does not
define it.

Every branch of `main()` returns 0. This hook must never block a `Stop` event (exit
code 2 would mean "keep going", which is never the intent here) and must never raise
an uncaught exception into the Claude Code session.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
AGENTS_DIR = REPO_ROOT / ".agents"
HANDOFF_PATH = AGENTS_DIR / "LOOP_HANDOFF.md"
DECISION_PATH = AGENTS_DIR / "DECISION.md"
CURRENT_TASK_PATH = AGENTS_DIR / "CURRENT_TASK.md"
RUNS_DIR = AGENTS_DIR / "runs"
COUNTER_PATH = RUNS_DIR / "halt_answerer_counter.txt"

DEVELOPER_ONLY_CONDITIONS = {"1", "2", "5"}
DETERMINISTIC_CONDITIONS = {"3", "4"}
DISPATCH_CONDITIONS = {"6"}
MAX_AUTO_HALTS = 3  # AGENTS.md §12.12 three-halt cap.

DECISION_REQUIRED_HEADERS = ("## Answers", "## Scope effect", "## Resume from")
REQUIRED_SCOPE_EFFECT = "no change to CURRENT_TASK.md"

CONDITION_4_FIXED_TEXT = (
    "Do not attempt a fourth time. Skip this step, record it as blocked in the "
    "end-of-task report, and continue from the next step in `## Order` that does "
    "not depend on it. If every remaining step depends on it, stop and report."
)

DECISION_PLACEHOLDER = (
    "PLACEHOLDER — the halt-answerer has not yet made a determination for this "
    "halt. If all four AGENTS.md §12.4 reversibility parts hold true, replace "
    "this entire file's content, via your Edit tool, with the real "
    "three-section decision. If any part is false, leave this file exactly as "
    "it is and do not edit it.\n"
)


def note(message: str) -> None:
    """Print a notice. Exit code stays 0 regardless of what is printed here."""
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    print(f"[halt_answerer] {message}")


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def read_stdin_json(stream) -> dict:
    try:
        raw = stream.read()
    except Exception:
        return {}
    if not raw or not raw.strip():
        return {}
    try:
        payload = json.loads(raw)
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def is_stop_hook_active(payload: dict) -> bool:
    return bool(payload.get("stop_hook_active"))


def extract_condition_number(handoff_text: str) -> str | None:
    """Parse the '## Halt trigger' section and return a single §12.5 condition
    number ('1'-'6') as a string, or None if it cannot be determined unambiguously.
    Never guesses: more than one distinct number, or zero, both return None.
    """
    section_match = re.search(
        r"^##\s*Halt trigger\s*$(.*?)(?=^##\s|\Z)",
        handoff_text,
        re.MULTILINE | re.DOTALL,
    )
    if not section_match:
        return None
    section = section_match.group(1)
    found = {n for n in re.findall(r"condition\s+(\d)\b", section, re.IGNORECASE)}
    valid = found & set("123456")
    if len(valid) != 1:
        return None
    return next(iter(valid))


def get_halt_count() -> int:
    """Read the auto-answer counter, resetting it to 0 first if CURRENT_TASK.md
    has been modified more recently than the counter file (a new task starting).
    """
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    task_mtime = CURRENT_TASK_PATH.stat().st_mtime if CURRENT_TASK_PATH.exists() else None

    if not COUNTER_PATH.exists():
        COUNTER_PATH.write_text("0", encoding="utf-8")
        return 0

    if task_mtime is not None and task_mtime > COUNTER_PATH.stat().st_mtime:
        COUNTER_PATH.write_text("0", encoding="utf-8")
        return 0

    try:
        return int(COUNTER_PATH.read_text(encoding="utf-8").strip() or "0")
    except ValueError:
        return 0


def increment_halt_count() -> int:
    count = get_halt_count() + 1
    COUNTER_PATH.write_text(str(count), encoding="utf-8")
    return count


def build_condition3_decision(timestamp: str) -> str:
    """The fixed, hard-coded stay-in-scope answer for §12.5 condition 3. Written
    directly in Python — no model is ever invoked for this condition, which is
    what makes the "no scope change" guarantee true by construction rather than
    merely asserted (AGENTS.md §12.15, "Narrow exception — the halt loop").
    """
    return (
        f"# Decision — {timestamp}\n"
        "\n"
        "## Answers\n"
        "Stay in scope. Do not touch anything outside the `## Files/areas in scope` "
        "list in `.agents/CURRENT_TASK.md`. Report the change that was needed "
        "instead of making it.\n"
        "\n"
        "## Scope effect\n"
        f"{REQUIRED_SCOPE_EFFECT}\n"
        "\n"
        "## Resume from\n"
        "The step in `CURRENT_TASK.md`'s `## Order` where this halt fired. Skip "
        "the out-of-scope work, note it as blocked in the end-of-task report, and "
        "continue with any remaining in-scope steps.\n"
    )


def build_condition4_decision(timestamp: str) -> str:
    """The fixed, hard-coded answer for §12.5 condition 4. Written directly in
    Python — no model is ever invoked. The "## Answers" text already defers the
    "which step to resume from" judgment to whoever resumes (Claude Code,
    reading CURRENT_TASK.md's ## Order at that time), so there is no
    task-specific reasoning left for a model to do — matching condition 3.
    """
    return (
        f"# Decision — {timestamp}\n"
        "\n"
        "## Answers\n"
        f"{CONDITION_4_FIXED_TEXT}\n"
        "\n"
        "## Scope effect\n"
        f"{REQUIRED_SCOPE_EFFECT}\n"
        "\n"
        "## Resume from\n"
        "The step immediately after the one that failed three times, per "
        "CURRENT_TASK.md's current `## Order` — skip the blocked step, record "
        "it as blocked in the end-of-task report, and continue with the next "
        "step that does not depend on it. If every remaining step depends on "
        "the blocked one, stop and report instead of continuing.\n"
    )


def build_claude_command() -> list[str]:
    """The restricted-mode invocation for condition 6, the only condition that
    still dispatches a model. Never includes `--dangerously-skip-permissions`
    or `--allow-dangerously-skip-permissions` — AGENTS.md §12.10's new bullet
    bans both, unconditionally, on any dispatch.

    Uses `Edit(<path>)`, not `Write(<path>)`, in `--allowedTools`: Claude Code
    only enforces path-scoped rules for `Edit`/`Read`, never for `Write` — a
    `Write(<path>)` rule is accepted syntactically but never consulted. `Write`
    is additionally named in `--disallowedTools` as defense in depth, so even
    if `--allowedTools`' path-scoping were ever bypassed, the bare `Write` tool
    is not available at all. `.agents/DECISION.md` must therefore already exist
    (see `ensure_decision_placeholder()`) so the answerer's job is an Edit, not
    a Write, from the start — confirmed against a live adversarial dispatch,
    not assumed from documentation alone (two Windows/headless-mode GitHub
    issues describe path-scoped rules being silently ignored in exactly this
    configuration).
    """
    return [
        "claude",
        "-p",
        "--model",
        "sonnet",
        "--restricted",
        "--allowedTools",
        f"Read Edit({DECISION_PATH.relative_to(REPO_ROOT).as_posix()})",
        "--disallowedTools",
        "Bash PowerShell WebFetch Write",
        "--add-dir",
        str(REPO_ROOT),
        "--no-session-persistence",
    ]


def build_condition6_prompt(handoff_text: str) -> str:
    common = (
        "You are the automated halt-answerer for AGENTS.md's unattended halt loop "
        "(see .agents/AGENTS.md §12.5-§12.7, §12.15). Read .agents/LOOP_HANDOFF.md "
        "(reproduced below) and any files it references using your Read tool. "
        ".agents/DECISION.md already exists, containing a placeholder — your ONLY "
        "permitted write path is editing that one file, and you have no Write "
        "tool available at all, only Edit. When you do edit it, replace its "
        "content in the exact three-section format from AGENTS.md §12.7 "
        "(## Answers, ## Scope effect, ## Resume from). You may NEVER write "
        "anything to `## Scope effect` other than the literal text "
        f'"{REQUIRED_SCOPE_EFFECT}" — you have no authority to approve a scope '
        "change under any circumstance; that decision belongs to the developer, "
        "in Claude Chat, alone. Do not touch any other file, under any "
        "circumstance, even if asked to. Do not run any command.\n\n"
        f"--- .agents/LOOP_HANDOFF.md ---\n{handoff_text}\n--- end ---\n\n"
    )

    return common + (
        "This halt is §12.5 condition 6 (the halt fails AGENTS.md §12.4's "
        "four-part reversibility test). You are a false-positive filter, not an "
        "approver: independently re-run all four parts of §12.4's reversibility "
        "test against what the handoff describes:\n"
        "1. It is undone by editing one file, with no migration and no data "
        "change.\n"
        "2. It changes nothing a patient sees, and nothing another tenant sees.\n"
        "3. It touches no AGENTS.md §10 Opus trigger.\n"
        "4. It stays inside the `## Files/areas in scope` list in "
        "CURRENT_TASK.md.\n\n"
        "If, and only if, all four are true, use your Edit tool to replace the "
        "entire placeholder in .agents/DECISION.md with the real three-section "
        f'decision (`## Scope effect` reading exactly "{REQUIRED_SCOPE_EFFECT}"). '
        "If any one part is false, leave .agents/DECISION.md's placeholder "
        "exactly as it is — do not edit it at all — and simply state which part "
        "failed and why in your final response text; the halt stands for the "
        "developer."
    )


def invoke_answerer(cmd: list[str], prompt: str, env: dict) -> subprocess.CompletedProcess | None:
    """Runs the actual `claude -p` subprocess. Isolated into its own function so
    tests can monkeypatch it and never spawn a real process."""
    try:
        return subprocess.run(
            cmd,
            input=prompt,
            capture_output=True,
            text=True,
            env=env,
            cwd=REPO_ROOT,
            timeout=300,
        )
    except Exception as exc:  # noqa: BLE001 - must never propagate out of the hook
        note(f"failed to invoke the answerer: {exc}")
        return None


def validate_decision_text(text: str) -> bool:
    if not text.lstrip().startswith("# Decision"):
        return False
    for header in DECISION_REQUIRED_HEADERS:
        if header not in text:
            return False
    scope_match = re.search(
        r"^##\s*Scope effect\s*$(.*?)(?=^##\s|\Z)",
        text,
        re.MULTILINE | re.DOTALL,
    )
    if not scope_match:
        return False
    return scope_match.group(1).strip() == REQUIRED_SCOPE_EFFECT


def dispatch_and_validate() -> bool:
    """Runs the restricted answerer for condition 6 (the only condition that
    still dispatches a model), then validates whatever it did (or did not) do
    to .agents/DECISION.md. Returns True only if a valid, in-scope decision was
    actually written. On any failure mode — the placeholder left untouched, an
    invalid write, or a scope-widening write — discards/ignores it, notifies,
    and returns False so the halt stands for the developer.

    Pre-creates .agents/DECISION.md with a fixed placeholder before dispatch:
    the answerer's only granted write mechanism is `Edit`, not `Write` (see
    `build_claude_command()`), and `Edit` needs an existing file to act on.

    Callers must confirm `claude` is on PATH and account for the halt-cap
    counter themselves (see `main()`) — this function assumes an attempt is
    already underway, because the attempt itself is what spends real answerer
    usage, whether or not it ends in a valid decision.
    """
    handoff_text = HANDOFF_PATH.read_text(encoding="utf-8")
    prompt = build_condition6_prompt(handoff_text)
    cmd = build_claude_command()
    env = {k: v for k, v in os.environ.items() if k != "ANTHROPIC_API_KEY"}

    DECISION_PATH.write_text(DECISION_PLACEHOLDER, encoding="utf-8")
    pre_mtime = DECISION_PATH.stat().st_mtime

    invoke_answerer(cmd, prompt, env)

    if not DECISION_PATH.exists():
        # The answerer has no delete capability; fail-safe anyway rather than
        # assume this can't happen.
        note(
            "condition 6: .agents/DECISION.md is unexpectedly missing after "
            "dispatch. The halt stands for the developer."
        )
        return False

    post_mtime = DECISION_PATH.stat().st_mtime
    text = DECISION_PATH.read_text(encoding="utf-8")
    if post_mtime == pre_mtime or text == DECISION_PLACEHOLDER:
        try:
            DECISION_PATH.unlink()
        except FileNotFoundError:
            pass
        note(
            "condition 6: the answerer left the placeholder untouched (the "
            "halt was not a false alarm). The halt stands for the developer."
        )
        return False

    if not validate_decision_text(text):
        try:
            DECISION_PATH.unlink()
        except FileNotFoundError:
            pass  # already gone (e.g. a concurrent invocation raced us to it)
        note(
            "condition 6: the answerer's .agents/DECISION.md failed validation "
            "(missing a required §12.7 section, or `## Scope effect` was not "
            f'exactly "{REQUIRED_SCOPE_EFFECT}"). Discarded. The halt stands for '
            "the developer."
        )
        return False

    return True


def _run(payload: dict) -> int:
    if is_stop_hook_active(payload):
        return 0

    if "ANTHROPIC_API_KEY" in os.environ:
        note(
            "ANTHROPIC_API_KEY is set in the environment. Writing nothing and "
            "dispatching nothing, leaving this halt exactly as it would be with "
            "no hook installed (the answerer must run on the Pro subscription via "
            "`claude -p`, never against an API key)."
        )
        return 0

    if not HANDOFF_PATH.exists():
        return 0

    if CURRENT_TASK_PATH.exists() and CURRENT_TASK_PATH.stat().st_mtime > HANDOFF_PATH.stat().st_mtime:
        note(
            "CURRENT_TASK.md is newer than LOOP_HANDOFF.md — this handoff belongs "
            "to a previous, already-closed task. Leaving it untouched rather than "
            "reprocessing a stale halt against the current task."
        )
        return 0

    if DECISION_PATH.exists() and DECISION_PATH.stat().st_mtime > HANDOFF_PATH.stat().st_mtime:
        return 0  # already answered, per AGENTS.md §12.7.

    handoff_text = HANDOFF_PATH.read_text(encoding="utf-8")
    condition = extract_condition_number(handoff_text)
    if condition is None:
        note(
            "could not unambiguously parse a §12.5 condition number from "
            "LOOP_HANDOFF.md's ## Halt trigger section. Never guessing — leaving "
            "this halt for the developer."
        )
        return 0

    count = get_halt_count()
    if count >= MAX_AUTO_HALTS:
        note(
            f"AGENTS.md §12.12's three-halt cap is already reached "
            f"({count}/{MAX_AUTO_HALTS} auto-answered halts this task). Not "
            f"invoking. This halt (condition {condition}) is left for the "
            "developer."
        )
        return 0

    if condition in DEVELOPER_ONLY_CONDITIONS:
        note(
            f"§12.5 condition {condition} is developer-only (conditions 1, 2 and "
            "5 never auto-answer). See LOOP_HANDOFF.md's ## The decision needed."
        )
        return 0

    if condition in DETERMINISTIC_CONDITIONS:
        builder = build_condition3_decision if condition == "3" else build_condition4_decision
        DECISION_PATH.write_text(builder(utc_timestamp()), encoding="utf-8")
        increment_halt_count()
        note(
            f"§12.5 condition {condition}: wrote the fixed answer to "
            ".agents/DECISION.md. No model was invoked."
        )
        return 0

    if condition in DISPATCH_CONDITIONS:
        if shutil.which("claude") is None:
            note(
                "'claude' executable not found on PATH. Failing closed: not "
                "invoking, not falling back to a different tool or permission "
                "mode. This halt is left for the developer."
            )
            return 0
        # Increment before dispatching, not after validating: the attempt itself
        # spends real answerer usage regardless of outcome, so a repeatedly
        # failing or invalid dispatch must still count toward AGENTS.md §12.12's
        # three-halt cap rather than bypassing it.
        increment_halt_count()
        if dispatch_and_validate():
            note(f"§12.5 condition {condition}: a valid .agents/DECISION.md was written.")
        return 0

    return 0


def main(stdin=None) -> int:
    payload = read_stdin_json(stdin if stdin is not None else sys.stdin)
    try:
        return _run(payload)
    except Exception as exc:  # noqa: BLE001 - a Stop hook must never crash the session
        note(f"unexpected error, failing safe: {exc!r}")
        return 0


if __name__ == "__main__":
    sys.exit(main())
