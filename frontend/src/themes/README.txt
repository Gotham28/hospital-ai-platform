This **README.md** is designed to be the "Source of Truth" for your multi-tenant hospital platform. It covers the folder structure, the connection between the frontend and the FastAPI brain, and how to scale the system for new clients.

---

# 🏥 Multi-Tenant AI Hospital Platform (Gothos/Arogya)

This platform allows multiple hospitals to have their own branded patient portals, powered by a central AI engine that access specific doctor directories and medical knowledge bases.

## 🏗️ Core Architecture

The system uses a **Slug-based Multi-tenancy** model:

1. **URL Structure**: `domain.com/p/{hospital-slug}`.
2. **Theme Loading**: The `ThemeLoader` identifies the slug, fetches the `hospital_id` from the PostgreSQL database, and dynamically imports the corresponding React theme.
3. **Data Isolation**: Every AI request includes the `hospital_id` so the backend only searches that specific hospital's data.

---

## 📂 Frontend Folder Structure

To add a new hospital, create a folder in `src/themes/` named exactly after the database slug.

```text
src/
├── api/
│   └── axios.ts          # Central API instance (No hardcoded URLs)
├── themes/
│   ├── registry.ts       # Dynamic import logic (import.meta.glob)
│   ├── ThemeLoader.tsx   # The "Switch" that loads themes based on URL
│   └── [slug]/           # Hospital-specific folder (e.g., 'arogya')
│       ├── index.tsx     # Theme entry point
│       └── components/   # Bolt-generated UI components

```

---

## 🚀 Creating a New Theme (Integration Steps)

### 1. The Entry Point (`index.tsx`)

Your theme must export a default component that accepts `hospitalId` and `hospitalName` as props.

```tsx
// src/themes/[slug]/index.tsx
import Chat from './Chat';

const HospitalTheme = ({ hospitalId, hospitalName }) => (
  <div className="theme-container">
    <header>{hospitalName}</header>
    <Chat hospitalId={hospitalId} />
  </div>
);
export default HospitalTheme;

```

### 2. Connecting the AI Chat (`Chat.tsx`)

When porting code from **Bolt.new**, you must refactor the `sendMessage` function to align with the FastAPI backend.

> **Correction (2026-07-21):** An earlier version of this guide documented `POST /api/v1/ai/chat`
> as the integration path. **This is wrong — do not use it for new themes.**
> All production frontend components use `POST /api/v1/ai/chat-stream` (Server-Sent Events).
> `/api/v1/ai/chat` exists but is not called by any frontend; it is kept only for
> internal testing and scripts.

* **Request Method**: `POST /api/v1/ai/chat-stream` (Server-Sent Events stream).
* **Request Body**: Must include `question` (string), `hospital_id` (int), and `session_token` (string — use a stable per-user UUID).
* **Response Body**: Each `data:` line is a JSON-encoded token chunk; the stream ends with `data: [DONE]`.
* **How to consume**: Use the browser's `EventSource` API or `fetch` with `ReadableStream`. See `useHospitalChat.tsx` for the canonical implementation.

### 3. Styling & Animations

Copy custom `@keyframes` (like `slideUp` or `fadeIn`) from the Bolt `index.css` into the root `src/index.css` to make them globally available.

---

## 🧠 Backend Logic (FastAPI)

### Doctor Directory Sync

The system processes CSV files (like `full_doctor_availability_sheet.csv`) and stores them in the `doctors` table. The AI queries this table during chat to provide real-time staff information.

### Knowledge Base (RAG)

Hospitals can upload PDFs. The backend splits these into chunks, generates embeddings, and stores them in PostgreSQL using `pgvector`.

---

## 🛠️ Developer Checklist for New Hospitals

* [ ] **Database**: Create the hospital entry in the admin dashboard and note the **Slug**.
* [ ] **Sync**: Bulk upload the doctor CSV for that specific `hospital_id`.
* [ ] **Files**: Create `src/themes/[slug]/index.tsx`.
* [ ] **API**: Ensure the Chat component uses the shared `api` instance and passes `hospitalId`.
* [ ] **Assets**: Place custom logos in `public/themes/[slug]/`.

---

**Would you like me to create a "troubleshooting" section for this README to help you debug common issues like 422 Unprocessable Content or 404 Not Found?**