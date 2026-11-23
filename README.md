# 100 Apps, One Agent — Composio AI Product Ops take-home

An agent researched **100 apps across 10 categories** for Composio toolkit feasibility:
auth methods, self-serve vs gated access, API surface, existing MCP, buildability verdict —
with **evidence URLs for every claim**, four verification loops, a human audit, and a
single self-contained HTML case study. **Total cost: $0.** No deployment.

## Quickstart

```bash
pip install -r requirements.txt

# Rebuild the case study from saved data — no keys, no network needed:
python run.py
# -> open report/index.html
```

## Full re-run of the research agent

1. Put free API keys in `.env` (copy `.env.example`):
   - `GEMINI_API_KEY` — https://aistudio.google.com/apikey (free, no card)
   - `COMPOSIO_API_KEY` — https://dashboard.composio.dev (free plan, no card)
2. Run the pipeline (each step resumable):

```bash
python -m agent.research --pass 1        # search -> fetch docs -> evidence -> LLM extraction (100 apps)
python -m agent.verify --checks          # Loop A: evidence grounding + schema checks
python -m agent.verify --second-pass     # Loop B: independent pass, different model + prompt
python -m agent.verify --reconcile       # diff passes, arbiter settles disputes -> data/final.json
python -m agent.verify --audit-sheet     # Loop D: 15-app human audit form (data/verification/audit.html)
python -m agent.verify --ingest-audit    # after human fills audit_results.json: corrections + accuracy
python run.py                            # regenerate the case study
```

Useful flags: `--only 5,10,84` (subset), `--no-resume` (start over), `--model <name>`.

## Layout

```
agent/            providers.py (free Gemini/ddgs/fetch/Composio catalog), research.py,
                  verify.py (4 loops), analyze.py (patterns), report.py (HTML builder)
data/             apps.json (input), composio_toolkits.json (1,842-toolkit catalog via SDK),
                  evidence/<app>/ (saved doc pages + URLs), research_v1.json,
                  research_v2_raw.json, final.json, analysis.json, verification/
report/index.html THE deliverable (offline, no CDNs, embedded machine-readable dataset)
log.md            every action, timestamped, start to end
assignment.md     the task verbatim + the 100-app list
PLAN.md           the 5-step build plan
```

## Honesty notes

- Gated findings (paid/partner/admin) are valid results, backed by public docs — no paid accounts were created.
- Misses found by the human audit are shown on the page and badged in the matrix.
- `unknown` is used wherever docs don't support an answer; the agent never guesses.
- Python 3.14 tested; free-tier rate limits are handled with pacing + retries + checkpoints.
