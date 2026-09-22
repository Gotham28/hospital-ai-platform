# Research

## How to run
Any module in this package must be run from the repository root using the `backend/venv` virtual environment (e.g. `backend\venv\Scripts\python -m backend.research.<module>` on Windows). This package is never run as a standalone script from inside its own directory — always run it as `-m backend.research.<module>` from the repo root.

## Two-way isolation rule
The research package enforces a strict two-way isolation boundary: nothing under `backend/app/` may import anything from `backend/research/`, and nothing under `backend/research/` may import anything from `backend/app/`. All research code must be runnable standalone. To verify this rule, an automated check is available. Run it using `python -m backend.research.check_isolation`.

## API keys
API keys for this package live in `backend/research/.env` (see `.env.example` for the variable names — `OPENAI_API_KEY`, `GROQ_API_KEY`). This file is strictly local and must never be committed to the repository.

**Note:** never commit `.env`.
