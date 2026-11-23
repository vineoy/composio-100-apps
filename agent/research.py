"""The research agent: search -> fetch official docs -> save evidence -> LLM structured extraction.

Usage:
  python -m agent.research --pass 1            # first pass over all 100 (resumable)
  python -m agent.research --pass 1 --only 5,10,84
  python -m agent.research --pass 2            # independent second pass (different model+prompt)
"""
import argparse, json, re, time, datetime, pathlib
from . import providers as P

SCHEMA = """{
 "description": "one line: what the app does",
 "auth_methods": ["OAuth2" | "API key" | "Basic" | "Bearer token" | "JWT" | "other: <name>"],
 "auth_notes": "short detail, e.g. 'OAuth2 for user data; API key for server-side'",
 "access": "free_self_serve" | "trial_self_serve" | "paid_plan" | "admin_approval" | "partner_gated" | "no_public_api" | "unknown",
 "access_notes": "short detail, e.g. 'free developer edition; production needs paid plan'",
 "api_type": "REST" | "GraphQL" | "both" | "none" | "unknown",
 "api_breadth": "narrow" | "moderate" | "broad" | "very_broad" | "unknown",
 "api_notes": "short detail, e.g. 'REST + SOAP, hundreds of endpoints across clouds'",
 "existing_mcp": {"status": "official" | "community" | "none" | "unknown", "url": "link or empty", "notes": "short"},
 "buildability": {"verdict": "ready" | "feasible" | "blocked" | "unknown", "blocker": "main blocker or empty"},
 "evidence": [{"claim": "which field this supports", "url": "doc URL from the provided pages"}],
 "confidence": "high" | "medium" | "low"
}"""

RULES = """RULES (critical):
- Use ONLY the provided documentation excerpts. Every factual claim must cite one of the provided doc URLs in "evidence".
- If the docs do not answer a field, output "unknown". NEVER guess from general knowledge.
- A gated finding (paid plan / partner approval / contact sales) is a VALID, correct finding - not a failure.
- "none" means the docs explicitly say there is no such thing; otherwise prefer "unknown".
- Judge the app's main public developer API (not internal/admin-only APIs).
- For MCP: "official" = the vendor ships/announces an MCP server; "community" = a third-party MCP server exists; cite where you saw it."""

DEFS = """FIELD DEFINITIONS:
- access: free_self_serve = anyone can sign up and obtain API credentials free (incl. free dev tier/sandbox); trial_self_serve = self-serve but time-limited trial; paid_plan = credentials require a paid subscription; admin_approval = an org admin must enable/approve API access; partner_gated = partnership or contact-sales required; no_public_api = no documented public API.
- api_breadth: narrow (<~20 endpoints), moderate (~20-100), broad (~100-300), very_broad (300+). Estimate ONLY from what the docs show, else unknown.
- buildability: ready = documented API + obtainable credentials + no major blocker; feasible = buildable but notable work/blocker (app review, complex auth, missing scopes); blocked = cannot build today (no public API or hard gate)."""


def build_prompt(app, docs, second_pass=False):
    doc_blocks = []
    for i, d in enumerate(docs, 1):
        doc_blocks.append(f"[DOC {i}] {d['url']}\n{d['text'][:12000]}")
    docs_txt = "\n\n".join(doc_blocks) if doc_blocks else "(no documentation pages could be fetched)"
    if second_pass:
        # reordered prompt + different emphasis for independence
        return f"""Independent verification research. App: {app['name']} (category: {app['category']}). Website hint: {app.get('hint_url') or app.get('hint_text','')}

{DEFS}

Return ONLY a JSON object with exactly these keys:
{SCHEMA}

{RULES}
- Work field by field from the docs below; do not assume anything about this app.

DOCUMENTATION:
{docs_txt}"""
    return f"""You are a product-ops researcher at Composio, which builds toolkits that let AI agents call app APIs.
Research this app for toolkit feasibility.

APP: {app['name']} (category: {app['category']})
Website hint: {app.get('hint_url') or app.get('hint_text','')}

{RULES}

{DEFS}

DOCUMENTATION:
{docs_txt}

Return ONLY a JSON object with exactly these keys:
{SCHEMA}"""


def rank_urls(app, search_results):
    """Official-looking doc URLs first; homepages penalized; auth/api/mcp/pricing paths boosted. Cap 6."""
    name = app["name"].lower()
    tokens = [t for t in re.split(r"[^a-z0-9]+", name) if len(t) >= 3]
    hint = (app.get("hint_url") or "").split("#")[0].rstrip("/")
    candidates = ([hint] if hint.startswith("http") else []) + [r.get("href", "") for r in search_results]
    scored, seen = [], set()
    for u in candidates:
        if not u or not u.startswith("http"):
            continue
        u = u.split("#")[0].rstrip("/")
        if u in seen:
            continue
        seen.add(u)
        rest = re.sub(r"^https?://", "", u)
        dom = rest.split("/")[0].lower()
        path = "/" + "/".join(rest.split("/")[1:])
        score = 0
        if any(t in dom for t in tokens):
            score += 3
        if re.match(r"(developer|developers|docs|api|dev|open|learn|help)\.", dom):
            score += 2
        if any(k in path.lower() for k in ("auth", "api", "docs", "documentation", "mcp", "pricing", "developer", "reference")):
            score += 2
        if path in ("", "/"):
            score -= 3  # homepage: usually marketing, not docs
        if any(x in dom for x in ("reddit.", "quora.", "youtube.", "medium.", "stackoverflow.")):
            score -= 3
        if "github.com" in dom and any(t in u.lower() for t in tokens):
            score += 2  # repos are legit for open-source tools
        if u == hint:
            score += 1
        scored.append((score, u))
    return [u for _, u in sorted(scored, key=lambda x: -x[0])][:6]


def gather_docs(app, second_pass=False, reuse_evidence=False):
    from concurrent.futures import ThreadPoolExecutor
    ev_dir = P.EVIDENCE / f"{app['id']:03d}_{P.slugify(app['name'])}"
    ev_dir.mkdir(parents=True, exist_ok=True)
    if reuse_evidence:
        docs = []
        meta_p = ev_dir / "urls.json"
        if meta_p.exists():
            meta = json.loads(meta_p.read_text(encoding="utf-8"))
            for i, u in enumerate(meta.get("urls", []), 1):
                tp = ev_dir / f"page{i}.txt"
                if tp.exists():
                    docs.append({"url": u, "text": tp.read_text(encoding="utf-8")})
        return docs, ev_dir
    queries = [
        f"{app['name']} API authentication documentation",
        f"{app['name']} MCP server",
        f"{app['name']} API free tier developer credentials pricing",
    ]
    results = []
    for q in queries:
        results.extend(P.search(q, max_results=5))
    urls = rank_urls(app, results)
    with ThreadPoolExecutor(max_workers=4) as ex:
        fetched = list(ex.map(lambda u: P.fetch(u), urls))
    docs = [d for d in fetched if d and len(d["text"]) > 500]
    # JS-rendered sites (e.g. Salesforce docs) return empty shells -> free reader fallback
    if len(docs) < 2:
        have = {d["url"].rstrip("/") for d in docs}
        for u in urls[:4]:
            if u.rstrip("/") in have:
                continue
            d = P.fetch_jina(u)
            if d and len(d["text"]) > 500:
                docs.append(d)
            if len(docs) >= 3:
                break
    docs = docs[:4]
    for i, d in enumerate(docs, 1):
        (ev_dir / f"page{i}.txt").write_text(
            f"URL: {d['url']}\nFETCHED: {datetime.datetime.now().isoformat()}\nVIA: {d.get('via','direct')}\n\n{d['text']}",
            encoding="utf-8")
    (ev_dir / "urls.json").write_text(json.dumps({
        "app": app["name"], "queries": queries, "urls": [d["url"] for d in docs],
        "search_hits": [{"title": r.get("title"), "href": r.get("href")} for r in results][:15],
        "fetched_at": datetime.datetime.now().isoformat()}, indent=1), encoding="utf-8")
    return docs, ev_dir


def run(pass_no=1, only=None, resume=True, model=None):
    apps = json.loads((P.DATA / "apps.json").read_text(encoding="utf-8"))
    out_name = "research_v1.json" if pass_no == 1 else "research_v2_raw.json"
    out_path = P.DATA / out_name
    done = {}
    if resume and out_path.exists():
        done = {r["id"]: r for r in json.loads(out_path.read_text(encoding="utf-8"))}
    results = list(done.values())
    second = pass_no == 2
    for app in apps:
        if only and app["id"] not in only:
            continue
        if app["id"] in done:
            continue
        t0 = time.time()
        try:
            docs, ev_dir = gather_docs(app, second_pass=second, reuse_evidence=second)
            prompt = build_prompt(app, docs, second_pass=second)
            row, used_model = P.llm_json(prompt, model=model or ("gemini-2.5-flash" if second else None))
            row.update({
                "id": app["id"], "name": app["name"], "category": app["category"],
                "composio_toolkit": P.composio_match(app["name"]),
                "_meta": {"pass": pass_no, "model": used_model, "docs_fetched": len(docs),
                          "evidence_dir": str(ev_dir.relative_to(P.ROOT)),
                          "seconds": round(time.time() - t0, 1),
                          "at": datetime.datetime.now().isoformat()},
            })
            results.append(row)
            results.sort(key=lambda r: r["id"])
            tmp = out_path.with_suffix(".tmp")
            tmp.write_text(json.dumps(results, indent=1, ensure_ascii=False), encoding="utf-8")
            tmp.replace(out_path)
            print(f"[{app['id']:3d}/100] {app['name']:<28} docs={len(docs)} model={used_model} "
                  f"access={row.get('access')} verdict={row.get('buildability',{}).get('verdict')} "
                  f"({row['_meta']['seconds']}s)", flush=True)
        except Exception as e:
            print(f"[{app['id']:3d}/100] {app['name']}: ERROR {str(e)[:200]}", flush=True)
            results.append({"id": app["id"], "name": app["name"], "category": app["category"],
                            "error": str(e)[:400],
                            "_meta": {"pass": pass_no, "at": datetime.datetime.now().isoformat()}})
            results.sort(key=lambda r: r["id"])
            out_path.write_text(json.dumps(results, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"DONE pass {pass_no}: {len(results)} rows -> {out_path}")
    print("LLM usage:", json.dumps(P.usage))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--pass", dest="pass_no", type=int, default=1)
    ap.add_argument("--only", type=str, default=None, help="comma-separated app ids")
    ap.add_argument("--no-resume", action="store_true")
    ap.add_argument("--model", type=str, default=None)
    a = ap.parse_args()
    only = [int(x) for x in a.only.split(",")] if a.only else None
    run(a.pass_no, only, not a.no_resume, a.model)
