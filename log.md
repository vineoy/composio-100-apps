# Build Log — Composio AI Product Ops Intern Assignment

Every action executed from start to end, in order. Timestamps are local (IST, UTC+5:30).
Convention: `[time] ACTION — details / outcome`. Decision points and user inputs are marked **USER**.

---

## Phase 0 — Understand the assignment (2026-11-23)

- [~15:45] **USER** received task: build the Composio take-home assignment (research 100 apps with an agent, find patterns, verify accuracy, deliver one self-explanatory HTML case study). Constraints from user: (1) NO deployment, (2) completely free / zero cost, (3) accuracy + high quality is the priority, (4) maintain this log.md throughout, (5) ask the user whenever anything is needed.
- [~15:46] Attempted `webfetch` of the Notion assignment URL → returned empty (Notion pages are JavaScript-rendered; plain fetch gets no content).
- [~15:47] Loaded the `browser` skill; opened the assignment URL in the in-app browser (tab `tab_86b0a894…`). App shell loaded but page body rendered only "Skip to content". Console errors were telemetry-only (Statsig/Splunk CSP/CORS blocks) — unrelated to content.
- [~15:49] Reloaded tab + waited 30s for content text → still not rendered. `browser.network.list` failed with an internal error ("Expected JSON value"), so network debugging via browser was abandoned.
- [~15:50] Switched strategy: called Notion's public page-data API directly — `POST https://composio.notion.site/api/v3/loadPageChunk` with `pageId=391f261a-6dfe-80e9-946b-ee899d3a3762` → HTTP 200, 107 blocks in first chunk.
- [~15:51] First parse attempt produced empty text — discovered blocks are double-nested (`entry.value.value`). Fixed unwrapping; paginated chunks → 165 blocks total.
- [~15:52] Reconstructed full assignment text. Table cells initially empty — discovered cells live under custom property keys (e.g. `tD`x`, `t<Vr`, `fF@b`) with column order in `format.table_block_column_order`. Fixed table extraction → recovered all 10 category tables = exactly 100 apps with names + website hints.
- [~15:53] Inspected the 3 trailing blocks of the page → private/inaccessible (`role: none`, likely embedded links). Confirmed no essential assignment content is missing. Full task, constraints, deliverable spec and app list captured.
- [~15:53] Checked free-tier feasibility: `websearch` for Composio/Gemini free tiers returned no results (search integration unavailable in this environment). `webfetch` of https://composio.dev/pricing succeeded → **Composio Free plan: $0, no credit card, 10,000 tool calls/month, one-time $2 credits; "instant tools" (web search, SEO, etc.) are pay-per-use from credits**. Conclusion: Composio SDK usable for free within these limits; DuckDuckGo search + direct docs fetching as the zero-cost workhorse; free LLM tier (Gemini via Google AI Studio or Groq) for extraction — to be smoke-tested in Step 1.
- [15:54] Generated `data/apps.json` programmatically from the Notion API response (no manual transcription) — verified count = 100, ids 1–100, 10 categories. Normalized bare-domain hints to https URLs; Paygent Connect has no URL in the source (hint text only: "paygent (NMI-powered)") — flagged as a research challenge.
- [15:55] Created workspace files: `assignment.md` (verbatim task + app list), `data/apps.json` (machine-readable input), `log.md` (this file), `PLAN.md` (the 5-step build plan).
- [15:55] Presented the 5-step plan to the user; asked for: (a) a free LLM API key (Gemini or Groq), (b) optional free Composio account/API key, (c) confirmation of the no-deploy adaptation.
- [15:58] **USER decisions:** (a) Google Gemini free key — chosen; (b) free Composio account — user will create it. No-deploy adaptation stands.
- [15:59] Environment check: Python 3.14.7 ✓, git 2.47.1.windows.2 ✓. Risk noted: Python 3.14 is new — will verify package wheels (esp. composio/pydantic-core, lxml) at install time; fallback = Composio REST via httpx if SDK wheels unavailable.
- [15:59] Created `.env.example`, `.env` (empty placeholders for the two free keys), `.gitignore` (excludes `.env` so secrets are never committed).
- [16:00] Gave user exact steps to obtain both free keys and where to paste them. **Awaiting keys to run Step 1 smoke tests.**
- [16:07] **USER** reached Composio onboarding ("How do you want to use Composio?"); asked which option to pick. Advised: "Build an Agent with Composio SDK" (matches our pipeline); skip/Other for any framework question; goal = dashboard → Settings → API Keys.

---

## Phase 1 — Setup & smoke tests

- [16:10] **USER** "keys ready" + time pressure (submit quickly). Verified `.env`: GEMINI_API_KEY set (53 chars), COMPOSIO_API_KEY set (23 chars). Keys never printed in full.
- [16:11] `pip install httpx beautifulsoup4 ddgs python-dotenv google-genai composio` → success on Python 3.14 (wheels available; earlier risk resolved). Core imports OK.
- [16:12] Wrote + ran `smoke_test.py`: Gemini ✓ (gemini-2.5-flash replied OK), DuckDuckGo ✓ (3 hits), docs fetch ✓ (api.slack.com 200, 39KB), Composio SDK import+client ✓. COMPOSIO_SEARCH slug not found → investigated.
- [16:13] Composio SDK exploration: `tools.list` absent; `get_raw_composio_tools(search=...)` works; `COMPOSIO_SEARCH_TOOLS` execute needs `dangerously_skip_version_check=True` (works but noisy semantic results). Pivoted to the definitive source: `client.toolkits.list()` → full catalog.
- [16:14] Fetched Composio toolkit catalog via SDK in 2 pages → **1,842 toolkits** saved to `data/composio_toolkits.json`. Probe-matched ~85 of the 100 apps to existing Composio slugs (e.g. slack, github, notion, salesforce, pylon_mcp, otter_ai_mcp, notebook_lm, youtube_transcript, mermaid_chart_mcp). This becomes a bonus "Composio already ships it?" column + whitespace insight. SDK usage stays well within free 10k calls (2 list calls).
- [16:16] Wrote `agent/providers.py` (Gemini rate-limit+fallback, ddgs search, httpx+BS4 fetch, Composio catalog matcher with aliases) and `agent/research.py` (search→fetch→evidence→strict-JSON extraction, resumable checkpoints, pass1/pass2).
- [16:17] Single-app test (Slack) FAILED: model chain 404/400. Diagnosed via `models.list()` + `model_test.py`: **gemini-2.5-flash rejects JSON mode on api v1 ("use v1beta")**, and 2.5-flash-lite is retired for new keys. Newer models work.
- [16:18] Fix: MODEL_CHAIN → `["gemini-3.5-flash","gemini-3.6-flash","gemini-3.1-flash-lite"]`; pass-2 independent model → `gemini-3.6-flash`. Verified all three return valid JSON. Removed failed Slack row + temp test scripts.
- [16:19] Launched full pass-1 research over all 100 apps in background (resumable, ~9 RPM LLM pacing). Writing verify/analyze/report modules while it runs.
- [16:25] Wrote `agent/verify.py` (Loop A grounding checks, Loop B second pass + arbiter reconciliation, 15-app stratified human audit HTML form + ingest/accuracy math), `agent/analyze.py` (distributions, heatmap, blocker buckets, easy-wins/outreach/whitespace lists, headlines), `agent/report.py` (single-file offline HTML case study: headline→matrix→agent→proof→verification→process→embedded JSON), `run.py` (zero-API rebuild), `requirements.txt`, `README.md`.
- [16:30] Quality check on early rows: Salesforce got only 1 doc (JS-rendered docs site returns empty shell to plain HTTP) and pace was 50–135s/app (sequential 20s-timeout fetches). Stopped run (7 rows done).
- [16:33] Fixes: parallel fetches (4 workers, 12s timeout), smarter URL ranking (homepage penalty, auth/api/mcp/pricing path boost, 6 candidates), free Jina reader fallback for JS sites, Bing search fallback when ddgs exhausted. Re-ran Salesforce: 3 docs, access=free_self_serve ✓, 49.5s.
- [16:34] Relaunched full pass-1 in background with improved pipeline (resumes from 7 good rows).
- [16:38] Test-generated report from partial data (`python run.py`) → 51KB single-file HTML; opened via local QA server (127.0.0.1:8765, NOT deployment): zero console errors, matrix renders, search filter works. Screenshot skipped (desktop window not visible); visual QA deferred to final pass.
- [16:40] Added targeted pricing re-fetch to reconcile(): when BOTH passes say access=unknown, agent searches pricing specifically, saves new evidence, arbiter decides access. (Close/Copper showed this gap.)
- [16:42] `git init` + first commit (setup, agent, verification, report builder; .env excluded). Inspected HubSpot row: excellent quality (OAuth2+token+hapikey, official MCP w/ URL, per-claim citations, high confidence).
- [16:44] Tested verify modules on partial data: Loop A flagged 4/10 rows (e.g. Attio "Basic" auth ungrounded — real catch; Zoho "other: unknown" sloppy value). Audit form generator works (HTML + markdown). All modules green; waiting on pass-1 completion (~93 apps remaining, ~35–55s each).
- [17:00] Server restart cancelled the background run at 45/100 saved (no loss — checkpoints). Diagnosis while down: (a) free daily quota for gemini-3.5/3.6-flash is small (~20 calls) so run had fallen back to flash-lite; (b) DuckDuckGo package now rate-limited (11.7s ConnectErrors) → per-app times ballooned to 75–105s.
- [17:02] Fixes: (1) discovered **gemini-2.5-flash works in JSON mode on the v1beta API** (1.4s) — separate quota pool, 250 RPD; added a v1beta client routed automatically for 2.5 models, 2.5-flash now primary in MODEL_CHAIN, pass-2 + arbiter switched to 2.5-flash (true model independence restored). (2) Search chain rewritten: DDG Lite HTML endpoint first (tested: 10 correct hits in **1.4s**), ddgs package second, Bing-with-redirect-decoding last. Expected per-app time down from ~90s to ~20s.
- [17:05] Relaunched pass 1 from checkpoint (45 rows done). Estimated 15–20 min for the remaining 55 apps.
- [17:10] Loop C browser checks started. Verified against live docs: DealCloud official MCP ✓ (full MCP docs section); Pylon admin_approval ✓ ("Only Admin users can create API tokens"); Gladly Basic auth ✓ ("token-based Basic Authentication") + admin-set permissions ✓; Pinterest review gate ✓; systeme.io API key on any plan ✓.
- [17:15] **Loop C catches (real errors, corrected):** (1) Aircall was `free_self_serve` → docs show trial-account limits → `trial_self_serve`; (2) Amazon SP-API was `free_self_serve` → docs: "must have a professional selling account... Individual accounts are not eligible" → `paid_plan`; (3) **fanbasis was entirely wrong**: the cited "MCP" repo is *Basis protocol on BNB Chain* (unrelated crypto project); fanbasis rebranded to Commas and has no developer docs (all URLs redirect to marketing, /api = 404) → MCP `none`, access `no_public_api`, verdict `blocked`, auth `unknown`.
- [17:20] Server restart again (tool catalog update) interrupted the run; it resumed automatically from checkpoint. Search backends verified healthy post-restart (DDG Lite 10 hits/1.1s; Bing 30 hits/0.7s decoded).
- [17:22] Fixed report bug: stale analysis.json produced stats for 7 apps while table had 50 → report now always regenerates analysis from the current dataset.
- [17:25] Audit form upgraded: "✓ all right" per-app shortcut, per-field correction inputs, progress counter, direct `audit_results.json` download. Tested in browser: 15 cards / 225 radios / valid JSON / zero console errors.
- [17:28] Rewrote audit ingest for the new per-field format and precise accuracy math: pass-1 human accuracy → after corrections, with counts (wrong/corrected/unsure/right) and every miss listed. `apply_corrections()` added for Loop C fixes (applied after reconcile).
- [17:30] Report verification section now renders the Loop C browser-check table (confirmed/contradicted + what the page showed) and verified-fix badges in the matrix.
- [17:33] Pass 1 at 55/100, running clean at 17–47s/app on gemini-2.5-flash. Committing progress to git.


## Phase 2 — Research agent, first pass (100 apps)

## Phase 3 — Verification loops & accuracy improvement

## Phase 4 — Patterns & analysis

## Phase 5 — Case study page, packaging & final QA
