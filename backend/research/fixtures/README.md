# Research Fixtures — AROGYA M-03

These files contain **fictional** fact-sheets for two test hospitals used in the
AROGYA multi-tenant retrieval evaluation (task M-03).

> **All facts in these files are correct and internally consistent.**
> Deliberately altered (wrong) versions used for retrieval-error testing are
> produced in task M-04 and kept in a separate directory.

---

## Files

| File | Purpose |
|------|---------|
| `hospital_a.json` | Fictional Hospital A — Brightmoor Community Hospital (60 facts) |
| `hospital_b.json` | Fictional Hospital B — Larkfield Medical Centre (60 facts) |
| `validate_fixtures.py` | Validates both files; run via `python -m backend.research.fixtures.validate_fixtures` |
| `README.md` | This file |

---

## Fact-ID Scheme

```
<PREFIX>-<CATEGORY>-<NNN>
```

| Part | Description | Examples |
|------|-------------|---------|
| `PREFIX` | `A` for Hospital A, `B` for Hospital B | `A`, `B` |
| `CATEGORY` | Upper-case abbreviated category name | `GEN`, `ADMIN`, `DEP`, `DOC`, `SCHED`, `LAB`, `MED` |
| `NNN` | Zero-padded three-digit sequence number (per category, per file) | `001`, `012` |

**Examples:** `A-GEN-001`, `B-LAB-012`, `A-ADMIN-002`

- Fact IDs are unique **within each file** and **across both files** (the `A`/`B`
  prefix guarantees cross-file uniqueness automatically).
- Each file contains **55–65 facts**.

---

## Value Formats

| Attribute type | Python / JSON type | Format | Example |
|---|---|---|---|
| Schedule or opening hours | `dict` | `{"days": ["Mon","Tue",...], "start": "HH:MM", "end": "HH:MM"}` (24 h) | `{"days": ["Mon","Wed","Fri"], "start": "09:00", "end": "13:00"}` |
| Price (INR) | `number` | Numeric; represents cost in Indian Rupees | `650`, `4.0`, `5.5` |
| Boolean flag | `bool` | `true` / `false` | `true` |
| Fasting hours | `integer` | Whole hours required for fasting (`0` = none) | `8`, `12` |
| Turnaround hours | `integer` | Hours until report is ready | `4` |
| Stock status | `string` | One of `in_stock`, `low_stock`, `out_of_stock` | `"low_stock"` |
| Preparation (no fasting) | `string` | `"no_fasting_required"` | `"no_fasting_required"` |
| Emergency / helpline | `string` | Phone number string | `"1800-234-5678"` |

**Rule: one fact = one atomic value.** Each fact captures exactly one piece of
information. Compound information (e.g. price **and** fasting) uses separate facts.

### Day names

Valid day tokens: `Mon`, `Tue`, `Wed`, `Thu`, `Fri`, `Sat`, `Sun`.

---

## Deliberate Overlaps (5)

Hospital B contains five facts that **intentionally differ** from Hospital A for the
same named entity. These are used to verify that the retrieval system correctly
distinguishes between hospitals and does not mix up tenant data.

| # | Entity | Attribute | Hospital A value | Hospital B value |
|---|--------|-----------|-----------------|-----------------|
| a | Dr. Priya Nair | department | `General Medicine` | `Dermatology` |
| a | Dr. Priya Nair | clinic_schedule | Mon/Wed/Fri 09:00–13:00 | Tue/Thu 14:00–18:00 |
| b | Dr. Rajesh Varma | department | `Cardiology` | `ENT` |
| b | Dr. Rajesh Varma | clinic_schedule | Tue/Thu 09:00–12:30 | Mon/Wed/Sat 10:00–13:00 |
| c | Metformin 500mg | price_inr | `4.0` | `5.5` |
| d | Comprehensive Lipid Profile | price_inr | `650` | `850` |
| d | Comprehensive Lipid Profile | fasting_hours | `12` | `8` |
| e | Visiting hours | visiting_hours | 16:00–19:00 daily | 17:00–20:00 daily |

All other facts in Hospital B are distinct from Hospital A.

---

## Running the Validator

From the **repository root**:

```bash
python -m backend.research.fixtures.validate_fixtures
```

The validator prints `[PASS]` or `[FAIL]` for every check and a final `OVERALL`
line. It exits with code **0** on full pass and **1** on any failure.

### Checks performed

1. **Valid JSON** — each file parses without error.
2. **Fact count** — each file has between 55 and 65 facts.
3. **Required fields** — every fact has `fact_id`, `category`, `statement`,
   `attribute`, and `value`.
4. **`fact_id` format** — every ID matches `^[AB]-[A-Z]+-\d{3}$` with the correct
   prefix for its file.
5. **`fact_id` unique within file** — no duplicate IDs inside a single file.
6. **`fact_id` unique across both files** — no ID appears in both files.
7. **Time ranges valid** — for any value dict with `start`/`end` keys: both parse
   as `HH:MM` and `start < end`.
8. **Day names valid** — all entries in `days` lists are recognised (`Mon`–`Sun`).
9. **Numeric attributes ≥ 0** — `price_inr`, `fasting_hours`, and
   `turnaround_hours` are numbers and non-negative.
10. **Five deliberate overlaps present** — checks that each overlap entity exists
    with the expected values in both files.
