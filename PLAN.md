# The Plan — 5 Steps (simple words, full detail)

**Goal:** Research 100 apps the way Composio does before building a toolkit (auth, self-serve vs gated, API surface, MCP, buildability, evidence) — using an agent we build, verify the accuracy with real loops, find the patterns, and present everything in ONE self-explanatory HTML case study.

**Hard rules:** zero cost (free tiers only) · no deployment (local HTML + runnable repo) · accuracy first · every action logged in `log.md` · ask the user whenever something is needed.

**One honest note:** the assignment asks for a *live deployed link*, but the user said no deployment. We follow the user: a single self-contained HTML file that opens locally + a repo with a one-command runnable trigger. (If the user later changes their mind, GitHub Pages is free — but we will not deploy.)

---

## What we already have (done)

- Full assignment text saved → `assignment.md`
- All 100 apps extracted programmatically from Notion (no typos) → `data/apps.json`
- Action log started → `log.md`
- Composio free tier confirmed: $0, no card, 10,000 tool calls/month + one-time $2 credits.

## What the finished project looks like

```
composio_assignment/
├── log.md                  # every action, start to end
├── PLAN.md                 # this plan
├── assignment.md           # the task, verbatim
├── README.md               # how to run everything (short)
├── run.py                  # ONE command: rebuild the report from saved data (no keys needed)
├── requirements.txt
├── .env.example            # where free API keys go (never committed)
├── data/
│   ├── apps.json           # input: the 100 apps
│   ├── evidence/           # saved raw doc pages per app (proof, reproducible)
│   ├── research_v1.json    # first agent pass
│   ├── research_v2.json    # after automated verification + second pass
│   ├── final.json          # after browser + human checks (the truth we publish)
│   └── verification/       # audit sheets, diffs, accuracy numbers
├── agent/
│   ├── research.py         # the research agent (search → fetch docs → LLM extract)
│   ├── verify.py           # verification loops (evidence checks, second pass, diffs)
│   ├── analyze.py          # patterns, clusters, stats
│   ├── report.py           # builds the single-file HTML
│   └── providers.py        # free LLM + search providers, rate-limit aware
└── report/
    └── index.html          # THE deliverable (works offline, no CDN)
```

---

## STEP 1 — Setup & prove the free tools work (~30–45 min)

**What:** Prepare everything so the agent can run for ₹0/$0.

1. Create the folder structure above, `requirements.txt` (httpx, beautifulsoup4, ddgs, python-dotenv, google-genai or groq — all free/open-source), `.env.example`, git repo init.
2. **USER gives us one free LLM API key** (we ask; recommended: Google AI Studio Gemini key — free, no card; Groq is the backup — also free). Keys go in `.env`, never in code or the report.
3. Optional but recommended: **USER creates a free Composio account** (dashboard.composio.dev, no card) and gives the API key → we use Composio's SDK for part of the search/fetch work, which the assignment explicitly says is "in the spirit of the role". We stay inside 10,000 free tool calls and watch the $2 credit meter; DuckDuckGo (`ddgs`, free, no key) is the default search so we never *depend* on paid usage.
4. Smoke tests: 1 LLM call, 1 DuckDuckGo search, 1 docs-page fetch, 1 Composio SDK call (if key provided). Log results. If a free tier is rate-limited, the pipeline paces itself (requests/minute limits, retries, resume-from-checkpoint) — 100 apps fits comfortably in free daily quotas.

**Done when:** all smoke tests pass and are logged; we know exactly which free providers work.
**Need from user:** the free API key(s). Nothing else.

## STEP 2 — Build the research agent & run pass 1 on all 100 (~2–3 h)

**What:** A Python pipeline that researches each app like a Composio product ops person would.

Per app, the agent:
1. Starts from the hint URL in `apps.json` + targeted searches: `"<app> API authentication"`, `"<app> API pricing free tier"`, `"<app> MCP server"`.
2. Fetches the 2–4 most relevant official doc pages (auth docs, pricing/dev docs, MCP announcements). Saves the raw text + URL + fetch time into `data/evidence/<app>/` — this is our proof trail and makes everything re-runnable offline.
3. Sends the evidence to the free LLM with a strict JSON schema and rules ("only claim what the evidence supports; cite a URL for every field; say `unknown` instead of guessing"):
   - one-line description · category
   - `auth_methods` (OAuth2 / API key / Basic / token / other)
   - `access` (free self-serve / trial self-serve / paid plan / admin approval / partner-gated / no public API / unknown)
   - `api_surface` (REST / GraphQL / both / none; rough breadth; endpoint-count estimate where docs show it)
   - `existing_mcp` (official / community / none + link)
   - `buildability` (ready / feasible-with-work / blocked) + main blocker
   - `evidence[]` (claim → URL) + `confidence` (high/medium/low)
4. Checkpoints after every app (crash-safe, resumable), respects rate limits, logs each app's outcome.

Output: `data/research_v1.json` — 100 structured rows, each backed by saved evidence.
**Done when:** 100/100 rows exist (honest `unknown`s allowed), evidence saved, run logged.
**Need from user:** nothing (keys from Step 1).

## STEP 3 — Verification loops: make accuracy provably go up (~2–3 h) ⭐ most important

**What:** Four loops, each catching different error types. We measure accuracy on a fixed sample BEFORE and AFTER, and show the improvement honestly.

- **Loop A — automated evidence check (all 100):** every cited URL must be live and its saved text must actually support the claim (keyword/grounding checks, e.g. claimed "OAuth2" but no OAuth mention in evidence → flag). Schema validation. Flags low-confidence rows.
- **Loop B — independent second agent pass (all 100):** re-research with a differently-ordered prompt (and second free model if available) WITHOUT seeing pass-1 answers. Diff the two passes field-by-field. Agreements → confidence up. Disagreements → targeted re-fetch of the specific doc that settles it, or flag for Loop C. Output: `research_v2.json` + a visible diff report.
- **Loop C — browser deep-checks (~15–20 hard apps):** I (the OpenCode agent) drive the real in-app browser to visit auth/pricing pages for the tricky ones — e.g. DealCloud, Paygent Connect, iPayX, fanbasis, Waterfall.io, PitchBook, Gladly, Pylon, Consensus, Grain, higgsfield, NotebookLM, Sherlock, Mermaid CLI. This is the "browser-use" loop the assignment asks for. Screenshots/notes saved as evidence.
- **Loop D — human audit (USER, ~20–30 min):** a stratified random sample of ~15 apps (across categories & verdicts). We generate a simple audit sheet: our answer + the exact doc link + "correct / wrong / unsure" checkboxes. **USER checks them against the real docs** and returns the sheet. We compute per-field accuracy (auth, access, API, MCP, verdict) for v1 vs final on that same sample, fix every confirmed miss, and record hits AND misses honestly.

Output: `data/final.json`, `data/verification/` (audit sheets, diffs, accuracy-before/after table).
**Done when:** every flag resolved or honestly marked `unknown`; accuracy numbers computed; misses documented.
**Need from user:** ~20–30 minutes for the 15-app audit sheet (we schedule it when ready).

## STEP 4 — Find the patterns (~45 min)

**What:** Turn 100 rows into insight — the actual point of the assignment.

`agent/analyze.py` computes from `final.json`:
- Auth distribution (which auth dominates, overall + per category).
- Self-serve vs gated heatmap by category (which categories are developer-friendly vs sales-gated).
- Most common blockers (ranked).
- MCP coverage: who already has official/community MCP vs whitespace.
- **Easy wins:** self-serve + documented API + no MCP yet → "build these toolkits first" list.
- **Needs outreach:** partner-gated / contact-sales list → "business development, not engineering".
- Oddities & honest failures (apps that defeated the agent, e.g. no public API at all).

We write 4–6 plain-English headline findings backed by the numbers.
**Done when:** stats + headline insights generated and sanity-checked against the raw rows.
**Need from user:** nothing.

## STEP 5 — The case study page + packaging + final QA (~1.5–2 h)

**What:** ONE self-contained `report/index.html` a reviewer understands in ~2 minutes, no narration, works offline (zero CDNs — all CSS/JS/charts inline).

Page order (matches the assignment's checklist exactly):
1. **Headline patterns up top** — big stat cards + 4–6 plain findings (the "so what").
2. **The matrix** — all 100 apps, clean color-coded table: category, one-liner, auth, self-serve/gated, API surface, MCP, verdict, evidence links. Filter by category/auth/verdict + search box.
3. **The agent** — what we built, architecture diagram (inline SVG), which parts are automated vs where a human was needed, exact run commands.
4. **The proof** — runnable trigger: `python run.py` rebuilds the whole report from saved data with zero API calls; full re-run instructions with free keys in README.
5. **Verification** — the 4 loops, the 15-app human audit with hits AND misses shown honestly, accuracy v1 → v2 → final chart, apps that defeated us.
6. **Process & limitations** — workflow timeline, what we'd do with more time.
7. Machine-readable: `final.json` embedded in the page + linked in repo → "easy for both an agent and a human to consume".

Then: `README.md` (short: what this is, how to run, where keys go), final QA — open the page in the browser, check every section renders, filters work, links resolve, 2-minute skim test, no external requests, no secrets anywhere. Log everything.
**Done when:** user opens `report/index.html`, understands it in 2 minutes, and can re-run the pipeline from README.
**Need from user:** final review/approval of the page.

---

## Free-cost guarantee (how we stay at $0)

| Need | Free solution | Fallback |
|---|---|---|
| LLM extraction | Gemini free tier (AI Studio) or Groq free tier | pace requests; split across providers; I (OpenCode agent) can do extraction directly if quotas run out |
| Web search | DuckDuckGo via `ddgs` (no key, no cost) | Composio free-tier search within $2 credits; direct known-URL fetching |
| Docs fetching | httpx + BeautifulSoup (free) | in-app browser for JS-heavy pages |
| Composio SDK usage | Free plan: 10k tool calls/mo, $2 one-time credits | optional — pipeline works without it |
| Browser verification | OpenCode in-app browser (already available) | — |
| Hosting | none (no deployment per user) | — |
| Charts/HTML | hand-built inline SVG/CSS, no paid libs | — |

## Risks & how we handle them

- **Free-tier rate limits** → pacing, retries, checkpoints, resumable runs; worst case spread over 2 days or use me as the extraction engine.
- **JS-heavy docs sites** → browser loop fetches them; saved as evidence.
- **Obscure apps (Paygent, iPayX, fanbasis…)** → "no public API / gated" IS a valid finding per the assignment; we prove it with evidence, not guesses.
- **LLM hallucination** → evidence-first schema, `unknown` over guessing, 4 verification loops, human audit, honest miss reporting.
- **Time budget (6–8 h)** → steps are checkpointed; the report can be generated from whatever verified data exists; we prioritize accuracy over polish.
