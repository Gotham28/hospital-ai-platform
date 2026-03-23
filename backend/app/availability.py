import logging
from datetime import datetime
from pathlib import Path

import gspread
from google.oauth2.service_account import Credentials

logger = logging.getLogger(__name__)

CREDENTIALS_PATH = Path(__file__).resolve().parent.parent / "google_credentials.json"

_cache: dict = {}
_cache_time: dict = {}

# Cache TTL in seconds — 5 minutes is a good balance between freshness
# and not hammering the Sheets API on every chat message.
CACHE_TTL_SECONDS = 300


class AvailabilityError(Exception):
    """
    Raised when the Google Sheets availability fetch fails for any reason:
    missing credentials, network error, quota exceeded, invalid sheet ID,
    or permission denied.

    Callers (ai.py) catch this specifically to distinguish a real failure
    from an intentionally empty sheet, and to set a safe, directive
    fallback message in the system prompt rather than a vague string
    the LLM might ignore.
    """
    pass


def get_sheet_client() -> gspread.Client:
    """
    Authenticate and return a gspread client using the service account
    credentials file.

    Raises AvailabilityError if the credentials file is missing or
    authentication fails, so the caller gets a typed exception rather
    than a raw FileNotFoundError or google.auth exception.
    """
    if not CREDENTIALS_PATH.exists():
        raise AvailabilityError(
            f"Google credentials file not found at {CREDENTIALS_PATH}. "
            "Download your service account key from Google Cloud Console "
            "and place it at backend/google_credentials.json."
        )

    try:
        scopes = ["https://www.googleapis.com/auth/spreadsheets"]
        creds = Credentials.from_service_account_file(
            str(CREDENTIALS_PATH), scopes=scopes
        )
        return gspread.authorize(creds)
    except Exception as e:
        raise AvailabilityError(
            f"Failed to authenticate with Google Sheets API: {e}"
        ) from e


def get_doctor_availability(
    sheet_id: str,
    force_refresh: bool = False
) -> dict:
    """
    Fetch doctor availability data from a Google Sheet, with in-process
    per-hospital caching (TTL: CACHE_TTL_SECONDS).

    Returns a dict keyed by doctor_id:
        {
            "H1-D-A1B2": {
                "id": "H1-D-A1B2",
                "name": "Dr. Rajesh Kumar",
                "department": "Cardiology",
                "schedule": "Mon-Fri 9am-1pm",
                "absent_dates": "22-03-2026,23-03-2026",
            },
            ...
        }

    Returns {} if sheet_id is falsy (no sheet configured for this hospital).

    Raises AvailabilityError if the fetch fails for any reason so callers
    can provide a safe, explicit fallback rather than silently getting
    stale or empty data.

    Cache behaviour:
        - On a successful fetch, the result is cached and the timestamp updated.
        - On a failed fetch, the exception is raised immediately — we do NOT
          silently return stale cache. The caller decides whether to use stale
          data or show a safe fallback message. Serving stale data for
          availability is safer than hallucinating, but the caller should know
          it's stale.
    """
    if not sheet_id:
        return {}

    now = datetime.now()
    last_refresh = _cache_time.get(sheet_id)
    cache_is_fresh = (
        sheet_id in _cache
        and last_refresh is not None
        and (now - last_refresh).total_seconds() < CACHE_TTL_SECONDS
    )

    if not force_refresh and cache_is_fresh:
        logger.debug(
            "[Availability] Cache hit for sheet_id=%s (%d doctors)",
            sheet_id, len(_cache[sheet_id])
        )
        return _cache[sheet_id]

    # Cache is stale or missing — attempt a live fetch
    logger.info("[Availability] Fetching sheet_id=%s from Google Sheets API", sheet_id)

    try:
        client = get_sheet_client()
        sheet = client.open_by_key(sheet_id).sheet1
        records = sheet.get_all_records()
    except AvailabilityError:
        # Re-raise typed errors from get_sheet_client() as-is
        raise
    except gspread.exceptions.SpreadsheetNotFound:
        raise AvailabilityError(
            f"Google Sheet not found (sheet_id={sheet_id}). "
            "Check the Sheet ID in Settings and ensure the service account "
            "has been granted Viewer access to this sheet."
        )
    except gspread.exceptions.APIError as e:
        status = getattr(e.response, 'status_code', 'unknown')
        raise AvailabilityError(
            f"Google Sheets API error (HTTP {status}) for sheet_id={sheet_id}: {e}"
        ) from e
    except Exception as e:
        raise AvailabilityError(
            f"Unexpected error fetching sheet_id={sheet_id}: {type(e).__name__}: {e}"
        ) from e

    # Parse the sheet records into our internal format
    doctors: dict = {}
    skipped = 0

    for row in records:
        doctor_id = str(row.get("Doctor ID", "")).strip()
        name = str(row.get("Doctor Name", "")).strip()

        if not doctor_id or not name:
            skipped += 1
            continue

        doctors[doctor_id] = {
            "id": doctor_id,
            "name": name,
            "department": str(row.get("Department", "")).strip(),
            "schedule": str(row.get("Base Schedule", "")).strip(),
            "absent_dates": str(row.get("Absent Dates (comma-separated)", "")).strip(),
        }

    if skipped:
        logger.warning(
            "[Availability] Skipped %d rows with missing Doctor ID or Name "
            "in sheet_id=%s",
            skipped, sheet_id
        )

    # Update cache only after a successful parse
    _cache[sheet_id] = doctors
    _cache_time[sheet_id] = now

    logger.info(
        "[Availability] Loaded %d doctors from sheet_id=%s",
        len(doctors), sheet_id
    )

    return doctors


def get_cached_or_empty(sheet_id: str) -> dict:
    """
    Returns the last known good cache for this sheet_id, or {} if no
    cache exists. Used by callers that want to gracefully degrade to
    stale data rather than showing an error message to the patient.

    The caller is responsible for logging that stale data is being used.
    """
    return _cache.get(sheet_id, {})