# Current Task

## Feature
Scope Doctor, KnowledgeBase, and appointment row lookups by hospital ownership, including availability, appointment actions/display/reminders, and knowledge-entry mutations. Preserve superadmin workflows by requiring an explicit target hospital where the token has no tenant.

## Files/areas in scope
- `backend/app/api/v1/endpoints/doctor_availability.py`: enforce target hospital in doctor and availability reads/mutations.
- `frontend/src/pages/Doctors.tsx`: pass the selected hospital to availability endpoints.
- `backend/app/api/v1/endpoints/ai.py`: scope doctor appointment display and knowledge entry mutations.
- `frontend/src/pages/KnowledgeBase.tsx`: pass the selected hospital for knowledge-entry mutations.
- `backend/app/api/v1/endpoints/appointments.py`: scope doctor display lookups to each appointment hospital.
- `frontend/src/components/AppointmentsTab.tsx`: send the selected hospital with appointment approve/reject actions.
- `backend/app/services/reminders.py`: scope reminder doctor lookups to each appointment hospital.
- `.agents/CURRENT_TASK.md`: this task record.

## Explicitly out of scope
- Schema changes, migrations, or any database commands.
- Changes to authorization policy beyond tenant query scoping.
- Patient messaging, WhatsApp activation, deployment settings, or live service configuration.
- `docs/STATUS.md` edits; provide a proposed update for review.
- Running tests unless separately requested.
