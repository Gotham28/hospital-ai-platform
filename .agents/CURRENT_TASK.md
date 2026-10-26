# Current Task

## Feature
Add a per-hospital chatbot link to each card in the superadmin Hospital Management list. The link uses that hospital's slug to open the existing public `/p/:hospitalSlug` route in the same tab.

## Files/areas in scope
- `frontend/src/App.tsx`: add the dynamic Chatbot link to every hospital card.
- `.agents/CURRENT_TASK.md`: this task record.

## Explicitly out of scope
- Do not change the public chatbot route, theme loading, chatbot behavior, hospital API, or tenant data.
- Do not change card actions other than adding the Chatbot link.
- Do not update `docs/STATUS.md` directly; provide a proposed update for review.
- Do not run tests unless separately requested.
