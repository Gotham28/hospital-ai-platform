# Neon Migration Runbook

**Task:** Migrate AROGYA staging database from Render Postgres → Neon Postgres.
**Scope:** Staging only. No schema change. No code change. Host move only.
**Date drafted:** 2026-08-08 | **Last updated:** 2026-08-09
**Shell:** PowerShell (Windows). All commands in this document are PowerShell unless
labelled otherwise.

> [!CAUTION]
> This document describes an irreversible operation. Render DB deletion is final and
> sequenced last, gated on full verification. Read every section before running anything.

---

## Pass 1 findings (inspection only, no commands run)

### Finding 1 — `DATABASE_URL` in `config.py`

**No code change is required.**

`backend/app/core/config.py` declares `DATABASE_URL: Optional[str] = None` (line 15).
`pydantic-settings` reads it from the environment automatically. The
`SQLALCHEMY_DATABASE_URL` property (lines 37–45) returns this value when set, with a
`postgres://` → `postgresql://` normalisation, and falls back to a local-construction
string otherwise. `backend/app/db/session.py` (line 7) consumes this property with no
inline logic.

Neon issues `postgresql://` connection strings natively, so the normalisation branch is
a no-op. **Only action required: set `DATABASE_URL` in the deployed environment to the
Neon direct connection string.**

### Finding 2 — Render-specific coupling in `backend/app/`

Zero Render-specific functional coupling found. All hits of the word "render" in
`backend/app/` are comments or the unrelated English verb. No hardcoded
`onrender.com` hostname, no `sslmode` override, no `connect_args`. See the original
Pass 1 report for the full search table.

---

## Prerequisites — developer completes these before any command is run

- [ ] Create the Neon project and choose a region.
- [ ] **Enable `pgvector` on the Neon database NOW, before restore.**
  Connect to the Neon database and run:
  ```sql
  CREATE EXTENSION IF NOT EXISTS vector;
  ```
  Then verify: `SELECT extname FROM pg_extension WHERE extname = 'vector';`
  **This step must come before `pg_restore`.** The dump contains `Vector(1536)` columns
  on the `doctors` and `knowledge_base` tables. If the `vector` type does not exist when
  `pg_restore` runs, the restore will fail with `ERROR: type "vector" does not exist`.
  The dump file is reusable — if this happens, enable the extension and restore again.

- [ ] Check current Render DB size against Neon's 0.5 GB free-tier storage cap.
- [ ] Obtain the Neon **direct** connection string (not the pooled/PgBouncer URL).
  It will look like:
  `postgresql://user:password@ep-xxx-yyy.region.aws.neon.tech/dbname?sslmode=require`
- [ ] Set the two connection string variables in your PowerShell session (see Step 0).
- [ ] Do NOT run `alembic upgrade head` after restore. A full `pg_dump` carries the
  `alembic_version` table with it; the restored DB is already at head. Use
  `SELECT version_num FROM alembic_version;` to confirm — do not run Alembic against it.

---

## Step 0 — Set connection string variables

Run this in your PowerShell session before running any other step. Replace the
placeholder values with the real credentials.

```powershell
# Source: Render dashboard → your database → Connection Details
$RENDER_DB = "postgresql://user:pass@your-host.oregon-postgres.render.com/dbname"

# Source: Neon dashboard → your project → Connection Details → Direct connection
# Use the DIRECT connection string, not the pooled/PgBouncer one.
$NEON_DB   = "postgresql://user:pass@ep-xxx-yyy.region.aws.neon.tech/dbname?sslmode=require"
```

---

## Step 1 — Dump from Render

```powershell
# Safeguard: confirm $RENDER_DB actually points to Render before dumping
if ($RENDER_DB -notmatch "render\.com") {
    Write-Error "FATAL: RENDER_DB does not contain 'render.com'. Check the variable. Aborting."
    return
}
Write-Host "Confirmed source is Render ($RENDER_DB). Proceeding with dump..."

pg_dump `
  --format=custom `
  --no-acl `
  --no-owner `
  --verbose `
  $RENDER_DB `
  --file=arogya_staging_render.dump
```

**Flag rationale:**
- `--format=custom` — binary custom format required for `pg_restore`. Compresses output
  and allows selective/parallel restore.
- `--no-acl` — drops `GRANT`/`REVOKE` statements that reference Render-specific roles
  which do not exist on Neon; these would cause `pg_restore` errors without this flag.
- `--no-owner` — drops `ALTER TABLE ... OWNER TO <render_role>` statements that would
  likewise fail on Neon.
- `--verbose` — prints each object as it is dumped. Watch for the `vector` extension and
  `embedding` columns on `doctors` and `knowledge_base` in the output to confirm they
  are captured.

> [!NOTE]
> `pgvector` columns (`Vector(1536)`) are stored as ordinary PostgreSQL data and dumped
> correctly by `pg_dump`. The dump includes the `CREATE EXTENSION vector` declaration so
> the extension type is defined before the column data is restored. This is why enabling
> `vector` on Neon **before** restore is mandatory — if the extension declaration in the
> dump runs against a database that does not have it installed, it will fail.

---

## Step 2 — Restore into Neon

> [!CAUTION]
> Run Step 1 to completion and confirm the `.dump` file exists and is non-zero before
> proceeding. Do not proceed if Step 1 printed errors.

```powershell
# Safeguard: confirm $NEON_DB actually points to Neon before restoring
if ($NEON_DB -notmatch "neon\.tech") {
    Write-Error "FATAL: NEON_DB does not contain 'neon.tech'. Check the variable. Aborting."
    return
}
Write-Host "Confirmed target is Neon ($NEON_DB). Proceeding with restore..."

pg_restore `
  --format=custom `
  --no-acl `
  --no-owner `
  --verbose `
  --dbname=$NEON_DB `
  arogya_staging_render.dump
```

**`--clean` guidance:** Do **not** pass `--clean` when restoring into a freshly created,
empty Neon database — there is nothing to drop and `--clean` will emit harmless but
confusing `DROP` errors. Use `--clean` only if the target database already contains
objects that you want overwritten before the restore (e.g., a second restore attempt
after a partial first run). For a first-time restore into an empty Neon project, omit it.

**Other flags:**
- `--no-acl`, `--no-owner` — same reason as dump side.
- `--verbose` — print each restored object; scan for errors on `vector`-typed columns.
- No `--single-transaction` — for large dumps this can cause OOM; custom format restore
  handles atomicity per-object.

> [!WARNING]
> If `pg_restore` emits `ERROR: type "vector" does not exist` — the `pgvector` extension
> was not enabled on Neon before the restore. Stop immediately. Enable the extension
> (`CREATE EXTENSION IF NOT EXISTS vector;`), then re-run Step 2 using the same dump
> file (the file is reusable). Do not proceed until this error is gone.
>
> If `pg_restore` emits `ERROR: extension "vector" already exists` — this is harmless;
> the extension is already installed. The restore will continue correctly.

---

## Step 3 — Verify on Neon before touching anything else

Run all queries below on Neon. Run the same row-count queries on Render side by side and
compare. Do not update any environment variable or delete Render until every check passes.

### 3a. Extension present

```sql
SELECT extname FROM pg_extension WHERE extname = 'vector';
-- Expected: one row with extname = 'vector'
```

### 3b. Row counts — every table (dynamic, no hardcoded list)

Run this on **both Render and Neon** and paste the outputs side by side.

```sql
-- Counts every table in the public schema — no hardcoded table list.
-- Any table that restored empty will be visible here.
SELECT
    table_name,
    (xpath('/row/c/text()',
           query_to_xml(
               format('SELECT COUNT(*) AS c FROM %I', table_name),
               false, true, ''
           ))
    )[1]::text::int AS row_count
FROM information_schema.tables
WHERE table_schema = 'public'
  AND table_type  = 'BASE TABLE'
ORDER BY table_name;
```

### 3c. Row-count parity check (per-`hospital_id`)

Run on both sides and compare. This verifies the migration didn't lose or merge rows
by checking total counts per tenant, but it does NOT prove query isolation.
Table names confirmed from `backend/app/models/` source — see § __tablename__ evidence below.

```sql
SELECT hospital_id, COUNT(*) FROM doctors        GROUP BY hospital_id ORDER BY hospital_id;
SELECT hospital_id, COUNT(*) FROM knowledge_base GROUP BY hospital_id ORDER BY hospital_id;
SELECT hospital_id, COUNT(*) FROM appointments   GROUP BY hospital_id ORDER BY hospital_id;
SELECT hospital_id, COUNT(*) FROM lab_tests      GROUP BY hospital_id ORDER BY hospital_id;
```

### 3d. Cross-tenant referential integrity spot check

A true multi-tenant migration failure would result in crossed relationships (e.g. an
appointment belonging to Hospital A referencing a doctor belonging to Hospital B).

Run this query to verify referential integrity across the one tenant-scoped table that
has a foreign key into another tenant-scoped table (`appointments` → `doctors`):

```sql
SELECT a.id AS appointment_id, a.hospital_id AS appt_hospital,
       d.hospital_id AS doctor_hospital
FROM appointments a
JOIN doctors d ON a.doctor_id = d.id
WHERE a.hospital_id != d.hospital_id;
-- Must return 0 rows. Any row here means an appointment references a doctor from a
-- different hospital — a real cross-tenant integrity failure caused by the migration.
```

Then boot the app against Neon and run a real `hospital_id`-filtered query; paste the
query and its output:

```sql
-- Example — replace :hospital_id with the actual test hospital ID.
SELECT id, name, hospital_id FROM doctors WHERE hospital_id = :hospital_id LIMIT 5;
-- Expected: rows where hospital_id equals the value you passed, and nothing else.
-- Paste this output before marking the migration complete.
```

### 3e. Embedding column sanity check

```sql
-- Confirm Vector(1536) columns survived — check dimensions and non-null sample.
SELECT id, array_length(embedding::real[], 1) AS dims
FROM doctors
WHERE embedding IS NOT NULL
LIMIT 5;
-- Expected: dims = 1536 for every row.

SELECT id, array_length(embedding::real[], 1) AS dims
FROM knowledge_base
WHERE embedding IS NOT NULL
LIMIT 5;
-- Expected: dims = 1536 for every row.
```

### 3f. Alembic version

```sql
SELECT version_num FROM alembic_version;
-- Paste the output. Must match the expected head revision.
-- Do NOT run `alembic upgrade head` after a full restore — the version table
-- was carried over by pg_dump and the database is already at head.
-- To check the expected head locally (without touching Neon):
--   alembic heads   (run against local dev DB only)
```

---

## Step 4 — Update `DATABASE_URL` in the deployed environment

After every check in Step 3 passes:

1. Update the `DATABASE_URL` secret in your hosting platform (Render deploy env, or
   wherever the app is deployed) to the Neon direct connection string.
2. Redeploy / restart the service.
3. Run a live smoke test: fire one patient-facing query and one
   `hospital_id`-filtered `doctors` query; paste the output before proceeding.

---

## Step 5 — Delete Render database (developer only, separate sitting)

**Do this in a separate sitting, not the same day as the restore.**

Prerequisites before deleting:
- All checks in Step 3 passed and results were pasted.
- The app has been running cleanly against Neon for at least one session.
- You have confirmed the `.dump` file is retained as a backup for at least 30 days.

This action is irreversible.

---

## `__tablename__` evidence (source of truth for all SQL above)

Confirmed by reading `backend/app/models/` directly. Each line below is the exact
`__tablename__` declaration as it appears in the source file, or the derived value where
the class does not declare one explicitly.

| Model class | File | Source line | Actual table name |
|---|---|---|---|
| `Hospital` | `hospital.py:7` | `__tablename__ = "hospital"` | `hospital` |
| `Doctor` | `doctor.py:8` | `__tablename__ = "doctors"` | `doctors` |
| `DoctorSchedule` | `doctor_availability.py:6` | `__tablename__ = "doctor_schedules"` | `doctor_schedules` |
| `DoctorLeave` | `doctor_availability.py:18` | `__tablename__ = "doctor_leaves"` | `doctor_leaves` |
| `KnowledgeBase` | `knowledge.py:7` | `__tablename__ = "knowledge_base"` | `knowledge_base` |
| `Appointment` | `appointment.py:13` | `__tablename__ = "appointments"` | `appointments` |
| `LabTest` | `lab_test.py:6` | `__tablename__ = "lab_tests"` | `lab_tests` |
| `Medicine` | `medicine.py:6` | `__tablename__ = "medicines"` | `medicines` |
| `UsageLedger` | `usage.py:6` | `__tablename__ = "usage_ledger"` | `usage_ledger` |
| `User` | `user.py` — no explicit declaration | `base_class.py:13`: `return cls.__name__.lower()` | `user` |
| `WhatsAppLog` | `whatsapp_log.py:6` | `__tablename__ = "whatsapp_logs"` | `whatsapp_logs` |

**Prior runbook had six errors:** `doctor` (should be `doctors`), `knowledgebase` (should
be `knowledge_base`), `appointment` (should be `appointments`), `labtest` (should be
`lab_tests`), `whatsapplog` (should be `whatsapp_logs`), and five tables were missing
entirely (`doctor_schedules`, `doctor_leaves`, `medicines`, `usage_ledger`, `user`).
The dynamic `information_schema` query in Step 3b eliminates this class of error going
forward.

---

## `session.py` connection pool note

`backend/app/db/session.py` passes `pool_recycle=1800` and `pool_pre_ping=True` to
`create_engine`. These are generic SQLAlchemy settings and are beneficial for Neon
(serverless can idle connections). They do not need to change for this migration. Revisit
if Neon's connection pooler (PgBouncer) is enabled later — PgBouncer changes how
long-lived connections behave.
