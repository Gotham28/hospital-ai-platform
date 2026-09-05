"""
Standalone test for the CORS ALLOWED_ORIGINS hardening fix.

Covers the Settings.ALLOWED_ORIGINS field (backend/app/core/config.py) added to
move CORS origin parsing off raw os.getenv() and onto pydantic-settings, plus the
list-parsing expression backend/app/main.py applies to it:

    ALLOWED_ORIGINS = [o.strip() for o in settings.ALLOWED_ORIGINS.split(",") if o.strip()]

Each test constructs Settings directly, pointing `_env_file` at either a
guaranteed-nonexistent path (to isolate the class default / an env var from any
real dotenv file) or a throwaway temp file (to test dotenv-vs-env-var precedence).
No test reads, depends on, or modifies the real backend/.env. Matches the
run_rag_resilience_test.py / run_translation_test.py convention: no pytest,
plain checks, exit 1 on failure.
"""
import os
import sys
import tempfile
from pathlib import Path

from app.core.config import Settings

passed = 0
failed = 0

# A path guaranteed not to exist, so Settings(_env_file=_NO_DOTENV) never reads
# any real dotenv file -- isolates a test from backend/.env entirely.
_NO_DOTENV = str(Path(tempfile.gettempdir()) / "cors_config_test_no_such_file.env")


def check(name, condition, detail=""):
    global passed, failed
    if condition:
        print(f"PASS {name}")
        passed += 1
    else:
        print(f"FAIL {name}" + (f" — {detail}" if detail else ""))
        failed += 1


def parse_origins(raw: str) -> list:
    # Mirrors the exact expression in backend/app/main.py.
    return [o.strip() for o in raw.split(",") if o.strip()]


class _EnvVar:
    """Context manager: set/unset one os.environ key, restore prior state on exit."""

    def __init__(self, key, value):
        self.key = key
        self.value = value
        self._had_prior = key in os.environ
        self._prior = os.environ.get(key)

    def __enter__(self):
        if self.value is None:
            os.environ.pop(self.key, None)
        else:
            os.environ[self.key] = self.value
        return self

    def __exit__(self, *exc):
        if self._had_prior:
            os.environ[self.key] = self._prior
        else:
            os.environ.pop(self.key, None)


# =============================================================================
# TEST 1 -- class default (no env var, no .env file) has NO production origin
# =============================================================================

def test_default_has_no_production_origin():
    with _EnvVar("ALLOWED_ORIGINS", None):
        s = Settings(_env_file=_NO_DOTENV)

    check("default_allowed_origins_is_nonempty", bool(s.ALLOWED_ORIGINS))
    check("default_allowed_origins_excludes_vercel_app",
          "vercel.app" not in s.ALLOWED_ORIGINS,
          f"default={s.ALLOWED_ORIGINS!r}")

    parsed = parse_origins(s.ALLOWED_ORIGINS)
    check("default_parsed_list_excludes_vercel_app",
          not any("vercel.app" in o for o in parsed),
          f"parsed={parsed}")


# =============================================================================
# TEST 2 -- a comma-separated env var value parses into the expected list
# =============================================================================

def test_comma_separated_value_parses():
    with _EnvVar("ALLOWED_ORIGINS", "http://a.example.com,http://b.example.com"):
        s = Settings(_env_file=_NO_DOTENV)

    parsed = parse_origins(s.ALLOWED_ORIGINS)
    check("comma_separated_parses_to_expected_list",
          parsed == ["http://a.example.com", "http://b.example.com"],
          f"parsed={parsed}")


# =============================================================================
# TEST 3 -- whitespace around entries is stripped
# =============================================================================

def test_whitespace_is_stripped():
    with _EnvVar("ALLOWED_ORIGINS", "  http://a.example.com ,  http://b.example.com  "):
        s = Settings(_env_file=_NO_DOTENV)

    parsed = parse_origins(s.ALLOWED_ORIGINS)
    check("whitespace_stripped_from_each_entry",
          parsed == ["http://a.example.com", "http://b.example.com"],
          f"parsed={parsed}")


# =============================================================================
# TEST 4 -- an empty env var value produces [], never [""] and never a wildcard
# =============================================================================

def test_empty_value_produces_empty_list_never_wildcard():
    with _EnvVar("ALLOWED_ORIGINS", ""):
        s = Settings(_env_file=_NO_DOTENV)

    parsed = parse_origins(s.ALLOWED_ORIGINS)
    check("empty_string_parses_to_empty_list", parsed == [], f"parsed={parsed}")
    check("empty_string_never_parses_to_list_with_blank_entry", parsed != [""], f"parsed={parsed}")
    check("empty_string_never_produces_wildcard", "*" not in parsed, f"parsed={parsed}")


# =============================================================================
# TEST 5 -- a real environment variable overrides a .env file value
# (the property Render's deployment depends on)
# =============================================================================

def test_env_var_overrides_dotenv_file():
    with tempfile.TemporaryDirectory() as tmpdir:
        dotenv_path = Path(tmpdir) / ".env"
        dotenv_path.write_text("ALLOWED_ORIGINS=http://from-dotenv.example.com\n")

        with _EnvVar("ALLOWED_ORIGINS", "http://from-real-env-var.example.com"):
            overridden = Settings(_env_file=str(dotenv_path))

        with _EnvVar("ALLOWED_ORIGINS", None):
            not_overridden = Settings(_env_file=str(dotenv_path))

    check("real_env_var_wins_over_dotenv_file_value",
          overridden.ALLOWED_ORIGINS == "http://from-real-env-var.example.com",
          f"resolved={overridden.ALLOWED_ORIGINS!r}")

    # Sanity check the other direction: with no OS env var, the .env file value IS
    # used -- proves the file was genuinely consulted, so the check above is a real
    # override rather than a no-op where the file was never read at all.
    check("dotenv_file_value_used_when_no_env_var_set",
          not_overridden.ALLOWED_ORIGINS == "http://from-dotenv.example.com",
          f"resolved={not_overridden.ALLOWED_ORIGINS!r}")


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    test_default_has_no_production_origin()
    test_comma_separated_value_parses()
    test_whitespace_is_stripped()
    test_empty_value_produces_empty_list_never_wildcard()
    test_env_var_overrides_dotenv_file()

    print(f"\n{passed} passed, {failed} failed")
    if failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
