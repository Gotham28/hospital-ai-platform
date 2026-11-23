# Current Task

## Feature
Import patient recipients from Excel, CSV, PDF and photos on the Patient Messaging page. Require explicit review, consent and approval, then send through the existing Arogya Meta welcome sender using a durable queue.

## Files/areas in scope
- Frontend Messaging page and new WelcomeBatch component.
- WhatsApp routes, new import and batch services, queue model, Alembic revision, runtime configuration, dependencies, app startup and model registration.
- WhatsApp setup documentation and this task record.

## Explicitly out of scope
- Personal WhatsApp senders, new message wording, deployment, real patient testing and hosted database commands.
- Changes to the single-send UI or Meta activation checkpoints.
