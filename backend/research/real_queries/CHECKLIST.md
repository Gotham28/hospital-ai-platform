# Real-Query Anonymisation Checklist (GATE G7)

This checklist must be performed manually by a designated reviewer on **every question** after the automated `anonymise.py` pass and before any inclusion in analysis.

---

## 1. Storage and Security Protocol

- [ ] **No Cloud/AI Exposure:** Real patient questions must **NEVER** be pasted into any external AI chat, translation tool, IDE assistant, or email.
- [ ] **Local Gitignored Storage Only:** Raw and processed real inquiries must reside strictly in the local `backend/research/results/` directory (which is gitignored). Never run `git add` on any file containing unscrubbed queries.
- [ ] **Ethics & Consent Clearance:** Confirmed that institutional ethics approval (IRB/IEC) and patient consent documentation are signed and on record with the project lead before running this pipeline.

---

## 2. Manual Verification Items (Post-Script)

Review every line of text against the following checks:

| Identifier Type | Automated Tag | Manual Visual Verification |
|---|---|---|
| **Patient / Family Name** | `[NAME]` | Verify no first names, patronymics, or house names remain without a prefix. |
| **Phone Number** | `[PHONE]` | Confirm no 10-digit, 8-digit, or landline numbers remain in text. |
| **National / Hospital IDs** | `[ID]` | Verify Aadhaar (12-digit), UHID, MRN, OP ticket numbers are replaced. |
| **Dates of Birth / Age** | `[DOB]` | Confirm exact DOBs are scrubbed. (Decade-level broad age brackets like "50s" are permissible if approved). |
| **Addresses & Localities** | `[ADDRESS]` / `[PLACE]` | Confirm house names, ward numbers, panchayats, and specific street landmarks are replaced. |
| **Unique Rare Conditions** | `[REDACTED_CONDITION]` | If a patient describes an ultra-rare genetic disorder or public event that could identify them, redact to general clinical terms. |

---

## 3. Dual-Sign-Off Record

- **Reviewer 1 (Script operator):** _____________________   Date: ____________
- **Reviewer 2 (Independent auditor):** _________________   Date: ____________
- **Batch Identifier:** `BATCH-RQ-_______`
- **Total Records in Batch:** ________
- **Records Retained:** ________
- **Records Discarded for Privacy Risk:** ________
