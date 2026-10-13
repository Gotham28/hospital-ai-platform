# Related Work Comparison Table

Comparison of published hallucination detection, RAG guardrails, and post-editing systems against the proposed AROGYA Grounding Guard.

---

| Paper & Citation | Key Focus & Method | Target Languages | Multi-Tenant / Clinical Setting? | Instruction vs. Data Conflict Handled? | Post-Generation Correction Mechanism | Difference from AROGYA |
|---|---|---|---|---|---|---|
| **RARR** (Gao et al., ACL 2023) | Retroactive attribution & revision using search engine + LLM editor | English only | General domain web search (no clinic/tenancy) | No | LLM query generation + iterative sentence rewrite | AROGYA runs entirely locally on fixed retrieved passages, requires zero paid LLM calls for editing, and enforces exact multilingual entity lock. |
| **Self-RAG** (Asai et al., ICLR 2024) | End-to-end generator fine-tuned with reflection tokens (`[Retrieve]`, `[IsRel]`, `[IsSup]`) | English (limited multilingual) | General open-domain QA | No | Decoding-time reflection pruning | Requires training a specialized generator model; AROGYA is model-agnostic and wraps any existing LLM black-box without weight retraining. |
| **Corrective RAG (CRAG)** (Yan et al., 2024) | Retrieval evaluator triggering web fallback or document filtering | English only | Open-domain web retrieval | No | Pre-generation retrieval correction | CRAG intervenes *before* generation; AROGYA intercepts output *after* generation to catch subtle cross-lingual translation drift and entity shifts. |
| **RAGTruth** (Zhong et al., ACL 2024) | Hallucination benchmark & fine-grained span analysis across RAG systems | English only | News, QA, Biomedical (MIMIC-IV) | No | Benchmark/evaluator only (no correction engine) | RAGTruth provides diagnostic span labels; AROGYA implements an operational real-time guard that surfaces conflicts and redacts invalid clauses. |
| **SummaC** (Laban et al., TACL 2022) | Zero-shot summary consistency evaluation via NLI chunk matching | English only | News summarisation | No | Metric score only (no text editing) | AROGYA adds clause splitting, entity locking, Malayalam translation pivots, and selective redaction. |
| **FaithDial** (Dziri et al., TACL 2022) | Benchmark and model for faithful knowledge-grounded dialogue | English only | Conversational dialogue (WoW) | No | Training critic model | Focused on conversational chit-chat; does not address hospital appointments, multi-tenant boundaries, or Indian low-resource languages. |
| **AROGYA Grounding Guard** (This Work) | Modular post-generation guard: Claim splitting + Multilingual NLI + Conflict surfacing + Cross-script Fact-Lock | English & Malayalam | Real multi-tenant hospital deployment | Yes (surfaces instruction vs. retrieved data clashes) | Local deterministic redaction (`[FLAG_TEXT]`) and parameter verification | First general guard designed for Indian low-resource clinical RAG with cross-lingual entity locking and multi-tenant isolation. |
