# Current Task

## Feature
Remove predictable authentication and database-password defaults. JWT signing and validation must use one configured secret and fail closed when it is missing; the local superadmin seed must require an explicit password.

## Files/areas in scope
- `backend/app/core/config.py`: remove static database-password/JWT-secret defaults and provide required JWT-secret validation.
- `backend/app/api/deps.py` and `backend/app/api/v1/endpoints/auth.py`: use the same validated settings value for token signing and verification.
- `backend/app/main.py`: fail startup when JWT secret configuration is absent.
- `backend/.env.example`: show blank required secrets with setup guidance, not usable fixed defaults.
- `backend/seed_rich_data.py`: require an explicit superadmin seed password and never print it.
- `backend/run_endpoint_auth_test.py` and `backend/run_meta_whatsapp_test.py`: use synthetic JWT secrets that satisfy the production minimum.
- `PROJECT_NOTES.md`: remove the fixed login credential and document the required environment setting.
- `.agents/CURRENT_TASK.md`: this task record.

## Explicitly out of scope
- Patient-session logging, tenant-isolation query changes, Google key rotation/removal/history rewriting.
- Database schema or hosted database changes.
- WhatsApp activation settings, template content, or deployment changes.
- Direct push to `main`, merging, or edits outside the listed files.

## Order
1. Remove unsafe authentication and seed defaults.
2. Inspect the scoped diff and report it for review.

## Suggested review tier
Opus 5, high effort — touches authentication secrets.
