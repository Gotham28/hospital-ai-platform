import os
from datetime import datetime
from pathlib import Path
import gspread
from google.oauth2.service_account import Credentials

# -------------------------------------------------
# CREDENTIALS PATH
# -------------------------------------------------
# Ensure your 'google_credentials.json' is in the backend root folder
CREDENTIALS_PATH = Path(__file__).resolve().parent.parent / "google_credentials.json"

_cache = {}
_cache_time = {}

def get_sheet_client():
    """Ported from your previous model"""
    if not CREDENTIALS_PATH.exists():
        raise FileNotFoundError(f"Google credentials missing at: {CREDENTIALS_PATH}")

    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_service_account_file(str(CREDENTIALS_PATH), scopes=scopes)
    return gspread.authorize(creds)

def get_doctor_availability(sheet_id: str, force_refresh: bool = False):
    """
    MODIFIED: Now accepts a specific sheet_id for multi-tenancy.
    """
    if not sheet_id:
        return {}

    global _cache, _cache_time
    now = datetime.now()

    # Per-hospital caching
    last_refresh = _cache_time.get(sheet_id)
    
    if (force_refresh or sheet_id not in _cache or 
        (last_refresh and (now - last_refresh).total_seconds() > 300)):
        try:
            client = get_sheet_client()
            sheet = client.open_by_key(sheet_id).sheet1
            records = sheet.get_all_records()

            doctors = {}
            for row in records:
                doctor_id = str(row.get("Doctor ID", "")).strip()
                name = str(row.get("Doctor Name", "")).strip()
                if not doctor_id or not name: continue

                doctors[doctor_id] = {
                    "id": doctor_id,
                    "name": name,
                    "department": str(row.get("Department", "")).strip(),
                    "schedule": str(row.get("Base Schedule", "")).strip(),
                    "absent_dates": str(row.get("Absent Dates", "")).strip(),
                }

            _cache[sheet_id] = doctors
            _cache_time[sheet_id] = now
            print(f"[Availability] Loaded {len(doctors)} doctors for Sheet: {sheet_id}")

        except Exception as e:
            print(f"[Availability] Fetch failed: {repr(e)}")
            return _cache.get(sheet_id, {})

    return _cache.get(sheet_id, {})