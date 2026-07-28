# Project Notes

This document serves as a reference for setup-relevant details, credentials, and local dev commands.
*Note: Keep this file updated whenever setup details change, but only upon explicit request to avoid unscoped changes.*

## 1. Credentials
- **Superadmin Login**:
  - **Email:** `superadmin@gothos.com`
  - **Password:** `superadmin123`
  *(Note: Sourced from the local seed script `backend/seed_rich_data.py`)*

## 2. Database Connection
- **Local Dev DB**: `postgresql://localhost:5432/hospital_ai`

## 3. Dev Servers
To run the local development servers, use the following commands from the project root:

**Backend (FastAPI)**:
```bash
cd backend
uvicorn app.main:app --reload
```
*(Runs on port 8000 by default)*

**Frontend (React/Vite)**:
```bash
cd frontend
npm run dev
```
*(Runs on port 5173 by default)*

## 4. Current Status
- **WhatsApp Stage 1 Migration**: The Alembic migration `0c682ef81de1_add_whatsapp_logs_table.py` is currently **unapplied** on the local DB and is pending developer approval.

## 5. Known Follow-Ups
- **Dependency Consolidation**: Consolidate `backend/requirements.txt` into the root `requirements.txt`.
- **Logging Compliance Check**: Review the pre-existing raw patient-context logging in `ai.py`'s `_save_patient_ctx` function to ensure compliance with `AGENTS.md` Rule 6 (Never log/store raw patient text in a security log/audit trail without hashing).
- **Security Hardening**: The current superadmin credentials (`superadmin@gothos.com` / `superadmin123`) are a weak seed default. This must be changed to a strong, secure password before any production deployment.
