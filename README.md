# FINN: a filter, not a feed

Mobile-first investor agent. Push (digest + triggered alerts) and Pull (primary-source research).
FastAPI backend, single-file vanilla JS frontend (no build step), Gemini for LLM work.

## Run
```
pip install -r requirements.txt
export GEMINI_API_KEY=...        # free tier is enough
uvicorn backend.app:app --port 8000
```
No key or no network: `FINN_DEMO=1` serves clearly-labelled SAMPLE data so the UI always runs.
If live fetching fails, the app falls back to sample data and the header pill switches to DEMO DATA. It never shows fake data as live.
Deploy: `render.yaml` included (set GEMINI_API_KEY). Tests: `pytest tests`.

## Design point of view
One screen, not five. Brief = what changed, ranked. Routine filings collapse behind one tap.
- **Priority is computed.** Category tier, lifted one tier if the same stock had an unusual price/volume move that day (filing plus price agreeing is the signal).
- **Alerts use the investor's definition of unusual**: volume multiple, daily move %, announcement types, all editable, stored on device.
- **Pushed items answer "so what"**: results get Revenue/EBITDA/PBT/PAT with QoQ and YoY; management changes get a bio; other P1-P3 items get a one-line summary on demand; P4 is collapsed.

## Architecture and cost routing
| Step | Model | Why |
|---|---|---|
| Announcement classification | none (regex rules) | bulk, deterministic, free |
| Results extraction | FAST (flash-lite) | extraction only; all arithmetic in code |
| Mgmt bio | FAST + search grounding | push-side enrichment may use the web |
| Concall guidance extraction (x4) | FAST, cached per URL | bulk reading |
| Annual report | BM25 retrieval then FAST | never send 300 pages |
| 8-section synthesis | SMART (flash) | the only cross-document reasoning call |

About 6 LLM calls per company, 1 expensive, all cached on disk. `/api/stats` shows calls vs cache hits.

## Pull discipline
Sources: screener.in standardised tables (computed in `analytics.py`), annual report PDF, last 4 concall transcripts.
The prompt forbids outside knowledge; "not stated" is the default. Works for any NSE ticker screener covers.
**Narrative vs numbers**: each call's explicit guidance is extracted, then matched against the next quarters' computed numbers.

## Known limits
- Built in a sandbox with no access to Yahoo, NSE or screener. Live paths need a first-run check. Parsers are tested on fixtures; LLM steps with a mock.
- NSE sometimes blocks cloud IPs. The app then falls back to sample data and says so.
- Management bio uses grounded web search, not LinkedIn. Marked unverified.
- EBITDA is derived (PBT + interest + depreciation - other income); banks show n/a.
- Push is in-app with a badge. No OS push or scheduler yet.
- Not built: BSE fallback, XBRL results parsing, OCR for scanned PDFs.

## Next
Scheduler + web push, XBRL for exact results, position sizes to weight priority, voice morning brief.
