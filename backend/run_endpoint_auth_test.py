import os
import sys
import unittest.mock
from jose import jwt

# 1. Fake environment variables before imports
os.environ["JWT_SECRET"] = "test-secret"
os.environ["DATABASE_URL"] = "postgresql://test:test@localhost:5432/test_db"
os.environ["OPENAI_API_KEY"] = "fake-key"
os.environ["REDIS_URL"] = "redis://localhost:6379/0"

network_calls = 0
def network_tripwire(*args, **kwargs):
    global network_calls
    network_calls += 1
    raise RuntimeError("network call attempted in offline test")

unittest.mock.patch('httpx.HTTPTransport.handle_request', side_effect=network_tripwire).start()
unittest.mock.patch('httpx.AsyncHTTPTransport.handle_async_request', side_effect=network_tripwire).start()
unittest.mock.patch('openai.OpenAI').start()
unittest.mock.patch('openai.AsyncOpenAI').start()
unittest.mock.patch('redis.from_url').start()
unittest.mock.patch('app.api.v1.endpoints.hospitals.OpenAI').start()

from fastapi.testclient import TestClient
from app.main import app
from app.api.deps import get_db

# 2. Setup mock DB
mock_session = unittest.mock.MagicMock()

# Mock crud functions so endpoints don't fail internally with 500s 
import types
from datetime import datetime
mock_hospital = types.SimpleNamespace(
    id=1,
    name="Test Hospital",
    slug="test-hospital",
    address="123 Test St",
    is_active=True,
    system_prompt="You are Arogya, a helpful assistant.",
    google_sheet_id=None,
    welcome_message=None,
    post_booking_disclaimer=None,
    relevance_criteria=None,
    created_at=datetime(2026, 1, 1)
)
mock_session.query.return_value.filter.return_value.first.return_value = mock_hospital
mock_session.query.return_value.filter.return_value.all.return_value = [mock_hospital]

app.dependency_overrides[get_db] = lambda: mock_session

client = TestClient(app, raise_server_exceptions=False)

# 3. Mint tokens
superadmin_token = jwt.encode({"sub": "super@test.invalid", "role": "superadmin", "hospital_id": None}, "test-secret", algorithm="HS256")
admin1_token = jwt.encode({"sub": "admin1@test.invalid", "role": "admin", "hospital_id": 1}, "test-secret", algorithm="HS256")
admin2_token = jwt.encode({"sub": "admin2@test.invalid", "role": "admin", "hospital_id": 2}, "test-secret", algorithm="HS256")

headers_super = {"Authorization": f"Bearer {superadmin_token}"}
headers_admin1 = {"Authorization": f"Bearer {admin1_token}"}
headers_admin2 = {"Authorization": f"Bearer {admin2_token}"}
headers_none = {}

passed = 0
failed = 0

def run_test(name, condition, msg=""):
    global passed, failed
    if condition:
        print(f"PASS {name}")
        passed += 1
    else:
        print(f"FAIL {name} {msg}")
        failed += 1

def check_route(name, method, url, is_superadmin_only=False, json_data=None, data=None, skip_cross_tenant=False):
    # (a) no token -> 401
    resp_none = client.request(method, url, headers=headers_none, json=json_data, data=data)
    run_test(f"{name} - no token -> 401", resp_none.status_code == 401, f"got {resp_none.status_code}")

    # (b) hospital-2 admin targeting hospital 1 -> 403
    if not skip_cross_tenant:
        resp_admin2 = client.request(method, url, headers=headers_admin2, json=json_data, data=data)
        run_test(f"{name} - admin2 -> 403", resp_admin2.status_code == 403, f"got {resp_admin2.status_code}")
    
    # (c) allowed caller -> not 401, 403
    if is_superadmin_only:
        resp_super = client.request(method, url, headers=headers_super, json=json_data, data=data)
        run_test(f"{name} - superadmin allowed (got {resp_super.status_code})", resp_super.status_code not in (401, 403), f"got {resp_super.status_code}")
        
        resp_admin1 = client.request(method, url, headers=headers_admin1, json=json_data, data=data)
        run_test(f"{name} - admin1 -> 403 (superadmin only)", resp_admin1.status_code == 403, f"got {resp_admin1.status_code}")
    else:
        if "slug" not in url:
            resp_admin1 = client.request(method, url, headers=headers_admin1, json=json_data, data=data)
            run_test(f"{name} - admin1 allowed (got {resp_admin1.status_code})", resp_admin1.status_code not in (401, 403), f"got {resp_admin1.status_code}")

# Route checks
check_route("1. create_hospital", "POST", "/api/v1/hospitals/", is_superadmin_only=True, json_data={"name": "test", "slug": "test"})
check_route("2. read_hospitals", "GET", "/api/v1/hospitals/", skip_cross_tenant=True)
check_route("3. get_hospital_by_id", "GET", "/api/v1/hospitals/1")
check_route("4. update_specific_hospital", "PATCH", "/api/v1/hospitals/1", json_data={"welcome_message": "test"})
check_route("5. update_my_hospital_settings", "PATCH", "/api/v1/hospitals/me", json_data={"welcome_message": "test"}, skip_cross_tenant=True)

resp_slug = client.request("GET", "/api/v1/hospitals/slug/test")
run_test("6. get_hospital_by_slug - stays public", resp_slug.status_code not in (401, 403))
run_test("6. get_hospital_by_slug - no google_sheet_id", "google_sheet_id" not in resp_slug.json())

check_route("7. get_hospital_doctors", "GET", "/api/v1/hospitals/1/doctors")
check_route("8. add_doctor", "POST", "/api/v1/hospitals/1/doctors", json_data={"name": "D", "doctor_id": "D1"})
check_route("9. get_hospital_billing", "GET", "/api/v1/hospitals/1/billing")
check_route("10. delete_doctor", "DELETE", "/api/v1/hospitals/1/doctors/1")
check_route("11. update_doctor", "PATCH", "/api/v1/hospitals/1/doctors/1", json_data={"name": "D"})
check_route("12. reset_hospital_billing", "DELETE", "/api/v1/hospitals/1/billing/reset", is_superadmin_only=True)
check_route("13. ingest_knowledge", "POST", "/api/v1/ai/ingest", json_data={"hospital_id": 1, "text": "fact"})

# 14. POST /upload-pdf - requires a file upload to avoid 422 before token checking
with open("test.pdf", "wb") as f:
    f.write(b"%PDF-1.4\n")
with open("test.pdf", "rb") as f:
    files = {"file": ("test.pdf", f, "application/pdf")}
    resp_none = client.post("/api/v1/ai/upload-pdf", headers=headers_none, data={"hospital_id": 1, "entry_type": "fact"}, files=files)
    run_test("14. upload_pdf - no token -> 401", resp_none.status_code == 401, f"got {resp_none.status_code}")
    
    f.seek(0)
    resp_admin2 = client.post("/api/v1/ai/upload-pdf", headers=headers_admin2, data={"hospital_id": 1, "entry_type": "fact"}, files=files)
    run_test("14. upload_pdf - admin2 -> 403", resp_admin2.status_code == 403, f"got {resp_admin2.status_code}")
    
    f.seek(0)
    resp_admin1 = client.post("/api/v1/ai/upload-pdf", headers=headers_admin1, data={"hospital_id": 1, "entry_type": "fact"}, files=files)
    run_test(f"14. upload_pdf - admin1 allowed (got {resp_admin1.status_code})", resp_admin1.status_code not in (401, 403), f"got {resp_admin1.status_code}")

if os.path.exists("test.pdf"):
    os.remove("test.pdf")

check_route("15. list_knowledge", "GET", "/api/v1/ai/knowledge/1")
check_route("16. create_appointment", "POST", "/api/v1/appointments/", json_data={
    "hospital_id": 1,
    "doctor_id": 1,
    "patient_name": "Test Patient",
    "patient_age": "20",
    "patient_phone": "0000000000",
    "preferred_date": "2030-01-01",
    "time_of_day": "morning"
})
check_route("17. get_appointment_status", "GET", "/api/v1/appointments/status/1/1234567890")

# Specific allowlist tests
mock_session.commit.reset_mock()
old_system_prompt = mock_hospital.system_prompt
resp_allowlist_fail = client.patch("/api/v1/hospitals/1", headers=headers_admin1, json={"system_prompt": "x"})
run_test("allowlist - admin1 rejects system_prompt -> 422", resp_allowlist_fail.status_code == 422, f"got {resp_allowlist_fail.status_code}")
run_test("allowlist 422 - no commit", not mock_session.commit.called, "commit was called")
run_test("allowlist 422 - system_prompt unchanged", mock_hospital.system_prompt == old_system_prompt, f"system_prompt changed to {mock_hospital.system_prompt}")

resp_allowlist_pass = client.patch("/api/v1/hospitals/1", headers=headers_admin1, json={"welcome_message": "a", "post_booking_disclaimer": "b", "relevance_criteria": "c"})
run_test("allowlist - admin1 accepts 3 fields", resp_allowlist_pass.status_code not in (401, 403, 422), f"got {resp_allowlist_pass.status_code}")

with unittest.mock.patch('app.crud.crud_hospital.get_hospitals') as mock_crud:
    mock_crud.return_value = []
    resp_super = client.get("/api/v1/hospitals/", headers=headers_super)
    super_cond = resp_super.status_code == 200 and mock_crud.called
    run_test("GET /hospitals/ as superadmin returns 200 and calls get_hospitals", super_cond, f"got {resp_super.status_code}, called={mock_crud.called}")
    
    mock_crud.reset_mock()
    resp_get_hosp = client.get("/api/v1/hospitals/", headers=headers_admin1)
    try:
        body = resp_get_hosp.json()
        body_len = len(body) if isinstance(body, list) else 'not a list'
        id_correct = isinstance(body, list) and len(body) == 1 and body[0].get("id") == 1
    except Exception:
        body_len = 'invalid json'
        id_correct = False
    
    admin_cond = resp_get_hosp.status_code == 200 and id_correct and not mock_crud.called
    run_test("GET /hospitals/ as admin1 returns specific hospital", admin_cond, f"got {resp_get_hosp.status_code} len={body_len} called={mock_crud.called}")

run_test("PASS/FAIL no network call attempted", network_calls == 0, f"network_calls={network_calls}")

print(f"{passed} passed, {failed} failed")
if failed > 0:
    sys.exit(1)
