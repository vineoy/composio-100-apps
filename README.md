# 100 Apps, One Agent — Composio AI Product Ops take-home

An agent researched **100 apps across 10 categories** for Composio toolkit feasibility:
auth methods, self-serve vs gated access, API surface, existing MCP, buildability verdict —
with **evidence URLs for every claim**, four verification loops, a human audit, and a
single self-contained HTML case study. **Total cost: $0.**

## Submit links

- **Live case study:** https://vineoy.github.io/composio-100-apps/
- **Source repo:** https://github.com/vineoy/composio-100-apps

## Quickstart (rebuild the page, no keys)

```bash
pip install -r requirements.txt
python run.py
# -> open report/index.html  (same file is also at docs/index.html for GitHub Pages)
```

## Full re-run of the research agent

1. Put free API keys in `.env` (copy `.env.example`):
   - `GEMINI_API_KEY` — https://aistudio.google.com/apikey (free, no card)
   - `COMPOSIO_API_KEY` — https://dashboard.composio.dev (free plan, no card)
2. Run:

```bash
python -m agent.research --pass 1        # search -> fetch docs -> LLM extraction (100 apps)
python -m agent.verify --checks          # Loop A: evidence grounding + schema
python -m agent.verify --second-pass --only <ids>   # Loop B sample (or use finalize)
python -m agent.verify --reconcile
python -m agent.verify --apply-corrections
python -m agent.verify --audit-sheet
python -m agent.verify --ingest-audit    # after filling audit_results.json
python run.py
```

Or after pass 1: `python -m agent.finalize`

**Verification coverage:** Loop A = all 100; Loop B = hard-flagged + 1/category sample;
Loop C = 12 browser checks; Loop D = 15-app audit. Exact counts are on the case study page.

## Layout

```
agent/            research, verify, analyze, report, providers
data/             apps.json, evidence/, research_v1.json, final.json, verification/
report/index.html local case study
docs/index.html   same page (GitHub Pages)
log.md            every action, start to end
```
