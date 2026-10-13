# Datasheet for AROGYA Grounding Benchmark

Following the Gebru et al. (2021) *Datasheets for Datasets* standard.

---

## 1. Motivation

- **Purpose:** Provide a bilingual (English and Malayalam) benchmark to evaluate context-grounding, hallucination detection, and translation fidelity in retrieval-augmented clinical assistants.
- **Created By:** The AROGYA Research Team, deployed in Kerala, India.

---

## 2. Composition

- **Dataset Size:** 100 core evaluation pairs (50 English, 50 Malayalam).
- **Splits:** 50 tuning items, 50 holdout items.
- **Classes:** 46 supported, 19 unsupported, 35 contradicted.
- **Phenomena Covered:** Cross-tenant doctor attribution, pricing shifts, timing changes, hallucinated procedures, instruction-vs-data conflicts.
- **Data Source:** Synthetic clinical scenarios based on Kerala multi-tenant hospital configurations. Real patient inquiries are strictly excluded from the public release.

---

## 3. Collection & Malayalam Annotation Process

- **English Drafting:** Synthesised from operational schedules, laboratory test tariffs, and service FAQs across two hypothetical hospital tenants (Hospital A and Hospital B).
- **Malayalam Translation & Quality Review:** Translated into natural Malayalam. Validated to prevent machine-translation artifacts, preserving specific Indic numerals and formal clinical terminology.
- **Fact Annotations:** Each clause is hand-labelled with status (`survived`, `changed`, `unverified`) and entity types (`doctor_name`, `price`, `time`, `weekday`, `test_name`, `department`, `hospital`).

---

## 4. Uses & Intended Applications

- **Intended Uses:** Academic research on post-generation RAG validation, multilingual NLP evaluation, and agentic guardrail development for low-resource languages.
- **Prohibited Uses:**
  - Automated diagnosis or direct patient clinical triage.
  - Commercial training of unverified medical AI systems without clinical oversight.
  - Cross-tenant user tracking.

---

## 5. Limitations & Ethical Considerations

- The dataset represents Kerala regional hospital administration patterns (OP booking, consultation fees, laboratory testing) and does not cover inpatient clinical management or critical emergency care.
- Dialectal variations in Malayalam across northern (Malabar) and southern (Travancore) regions are limited in the synthetic phrasing.
