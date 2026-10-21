# LegalTech Chile Engine

Chilean B2B LegalTech: extract credit instruments (pagaré, Ley 18.092; factura, Ley 19.983), liquidate the debt day by day with CMF rates capped at the TMC (Ley 18.010), and assemble an editable *demanda ejecutiva* (`.docx`) with otrosíes and a liquidation annex.

> **Status: engineering prototype.** Rate and UF data are **illustrative and unverified** (see Disclaimers). Not for filing as-is.

## Architecture

```
 Browser (Next.js)                    FastAPI (backend/app)
┌────────────────────┐   JSON    ┌──────────────────────────────────────────┐
│ 1 FileUpload       │──/extract─▶ services/extractor ─▶ LLM (JSON only)     │
│ 2 LiquidationLedger│──/liquidate▶ engine/calculator ◀─ engine/cmf_rates    │
│ 3 LawsuitPreview   │──/generate─▶  (recomputes ledger) ─▶ legal_templates  │
│        ▲ .docx     │◀──────────── services/generator (python-docx)         │
└────────────────────┘           └──────────────────────────────────────────┘
```

Rules: **no LLM arithmetic** (the LLM only transcribes fields; all money math is deterministic `Decimal`); the server recomputes the ledger before generating a document; error bodies never echo client documents (zero data retention: nothing is persisted).

```
backend/app/{api/v1,core,engine,schemas,services}   backend/data/cmf_rates_seed.json
backend/tests/                                      frontend/src/{app,components,lib,styles}
docs/{LEGAL_SPEC,ARCHITECTURE}.md
```

## Quickstart

Backend (Python 3.11+):

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pytest                                   # unit + API + contract tests (live LLM test is skipped)
ruff check . && mypy app                 # lint and types
uvicorn app.main:app --reload --port 8000
```

Frontend (Node 20+):

```bash
cd frontend
npm install
npm run dev                              # http://localhost:3000  (proxies /api/v1 to the backend)
npx playwright install chromium && npm run test:e2e   # browser + accessibility (axe) tests
```

Docker: `docker compose up --build` (backend build arg `WITH_PDF=1` adds LibreOffice for PDF output).
Without an LLM key, use the **Pagaré / Factura** sample buttons in step 1 (they skip extraction).
Optional live check: `LLM_API_KEY=... pytest -m live`.

### API (all under `/api/v1`)

| Endpoint | Purpose |
|---|---|
| `POST /extract` | text → validated `Pagare` / `FacturaElectronica` + `missing_fields` |
| `POST /extract-file` | PDF (text or scanned), PNG/JPG/WEBP or .txt upload; scanned content is OCR'd by a vision model |
| `POST /liquidate` | parameters (incl. `payments` / abonos) → day-by-day ledger |
| `POST /preview-lawsuit` | draft text blocks + attorney notes (ledger recomputed server-side) |
| `POST /generate-lawsuit` | `.docx` or `format: "pdf"`; optional `edited_blocks` (narrative only) and `assets` |

The browser only talks to the Next.js server, which proxies to the backend and adds `API_KEY`; the key never reaches the client.

### Environment variables

| Variable | Where | Purpose | Default |
|---|---|---|---|
| `LLM_PROVIDER` | backend | `anthropic` or `openai_compatible` | `anthropic` |
| `LLM_BASE_URL` | backend | OpenAI-compatible endpoint, e.g. `https://openrouter.ai/api/v1` | — |
| `LLM_API_KEY` | backend | Provider key (anthropic falls back to `ANTHROPIC_API_KEY`) | — |
| `LLM_MODEL` | backend | Extraction model, e.g. `qwen/qwen-2.5-72b-instruct` | `claude-sonnet-5-5` |
| `LLM_VISION_MODEL` | backend | Vision model for OCR with `openai_compatible` (anthropic reuses `LLM_MODEL`) | — |
| `API_KEY` | backend + frontend server | If set, backend requires header `X-API-Key`; the Next proxy sends it | unset (open) |
| `CORS_ORIGINS` | backend | Comma-separated allowed origins | `http://localhost:3000` |
| `RATE_LIMIT_PER_MIN` | backend | Per-IP requests per minute (0 disables) | `60` |
| `MAX_BODY_BYTES` | backend | Request size cap | `12582912` |
| `BACKEND_URL` | frontend server | Where the proxy forwards | `http://localhost:8000` |
| `NEXT_PUBLIC_SITE_URL` | frontend | Canonical URL for sitemap / metadata | `http://localhost:3000` |

PDF output needs LibreOffice Writer on the server; scanned-PDF OCR needs `poppler-utils` (`pdftoppm`).

## Disclaimers

- **Human in the loop.** Output is an editable draft marked *BORRADOR*; the attorney reviews, completes (e.g. embargo assets) and signs. Legal citations and wording must be verified by a Chilean attorney.
- **No OJV automation.** The system never submits to the Oficina Judicial Virtual, by design (Supreme Court anti-bot directives). Filing is manual.
- **Data privacy.** No documents are stored. Review Ley 21.719 duties and your LLM provider's retention terms before sending real client data.
- **Unverified financial data.** `backend/data/cmf_rates_seed.json` is illustrative (`"verified": false`; every ledger warns). The day-count convention (ACT/360 default vs ACT/365) is also unconfirmed and printed on each ledger.

### Replacing the seed with real CMF data

1. Transcribe CMF figures into the CSV templates in `backend/data/templates/` and run
   `python -m app.engine.cmf_ingest --periods periods.csv --uf uf.csv --source "..." --verified -o data/cmf_rates_seed.json`
   (validates contiguity, categories, TMC > corriente, UF coverage). The resulting JSON has the schema: `metadata` (`verified: true`, `source`), `uf_10th` (UF value on the 10th of each month), and `periods[]` with `valid_from`, `valid_to` and `rates` for the four categories (`non_reajustable_clp_under_50_uf`, `..._50_to_200_uf`, `..._over_200_uf`, `reajustable_uf_all`), each with `corriente` and `tmc` (annual %).
2. Feed it from CMF's published certificates (Diario Oficial) or a CMF data feed you are licensed to use, via a scheduled job that rewrites the file (or swap `load_default_table()` in `engine/cmf_rates.py` for a loader reading your store).
3. `pytest` checks period contiguity and category coverage; add real judicial liquidations as vectors in `backend/tests/vectors/` (see its README).
4. Have an attorney go through `docs/REVIEW_CHECKLIST.md` — every legal and financial assumption is listed there.
