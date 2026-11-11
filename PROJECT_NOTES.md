# Project Notes

This document serves as a reference for setup-relevant details, credentials, and local dev commands.
*Note: Keep this file updated whenever setup details change, but only upon explicit request to avoid unscoped changes.*

## 1. Local seed credential
- `backend/seed_rich_data.py` requires `SUPERADMIN_PASSWORD` to be set in the private
  local environment (at least 16 characters) before it creates the seeded superadmin
  account. The script does not print the password. Never run this development seed
  script against production.
- Set a unique `JWT_SECRET` of at least 32 characters in the private local environment;
  the application now refuses to start if it is missing or too short.

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
- **Security Hardening**: Confirm any previously seeded superadmin account is not used in production; rotate its password if it was created with the former fixed default.
