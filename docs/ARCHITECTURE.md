# Architecture

- `engine/cmf_rates.py` — rate periods (`valid_from..valid_to`), UF interpolation (10th-to-10th, geometric).
- `engine/calculator.py` — pure `Decimal` ledger: simple interest, TMC cap, bracket fixed at issue date, cumulative rounding.
- `schemas/` — Pydantic v2 models (RUT módulo 11, factura totals).
- `services/extractor.py` — LLM → JSON → schema validation, one retry; LLM injected via `LLMClient` protocol.
- `engine/legal_templates.py` + `services/generator.py` — deterministic Spanish templates → `.docx` (Times New Roman 12, 1.5 spacing).
- `services/documents.py` — upload sniffing, PDF text extraction, OCR via vision client.
- `core/middleware.py` — rate limit, body cap, security headers, access log without bodies.
- `api/v1` — `/extract`, `/extract-file`, `/liquidate`, `/preview-lawsuit`, `/generate-lawsuit` (ledger recomputed server-side; only narrative text is client-editable).
- Frontend (`frontend/src`): landing (`/`), workspace (`/app`, 4 steps), privacy (`/privacidad`); server-side proxy at `app/api/v1`; drafts only in browser localStorage.
- Not built by design: multi-case storage / batch runs (conflicts with zero data retention; would need an explicit retention and encryption design).
- Open items: see "Disclaimers" in the root README and `docs/LEGAL_SPEC.md` §5.
