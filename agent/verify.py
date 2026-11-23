"""Verification loops (the accuracy engine).

Loop A  --checks        automated evidence grounding + schema checks on pass 1 (all 100)
Loop B  --second-pass   independent re-research: different model + reordered prompt, same saved evidence
        --reconcile     field-by-field diff; disagreements settled by an arbiter LLM with the evidence
Human   --audit-sheet   stratified 15-app audit form (HTML) + markdown sheet for the user
        --ingest-audit  apply human corrections, compute v1-vs-final accuracy on the sample

Outputs: data/final.json, data/verification/*.json
"""
import argparse, json, re, datetime, pathlib
from . import providers as P
from . import research as R

VDIR = P.DATA / "verification"
VDIR.mkdir(parents=True, exist_ok=True)

ENUMS = {
    "access": {"free_self_serve", "trial_self_serve", "paid_plan", "admin_approval", "partner_gated", "no_public_api", "unknown"},
    "api_type": {"REST", "GraphQL", "both", "none", "unknown"},
    "api_breadth": {"narrow", "moderate", "broad", "very_broad", "unknown"},
    "confidence": {"high", "medium", "low"},
}
MCP_ENUM = {"official", "community", "none", "unknown"}
VERDICT_ENUM = {"ready", "feasible", "blocked", "unknown"}
COMPARE_FIELDS = ["auth_methods", "access", "api_type", "api_breadth", "existing_mcp.status", "buildability.verdict"]


def load(name):
    p = P.DATA / name
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else []


def save(name, obj):
    p = P.DATA / name
    p.write_text(json.dumps(obj, indent=1, ensure_ascii=False), encoding="utf-8")


def evidence_text(row):
    ev = P.ROOT / row.get("_meta", {}).get("evidence_dir", "")
    txt = ""
    if ev.exists():
        for f in sorted(ev.glob("page*.txt")):
            txt += f.read_text(encoding="utf-8") + "\n"
    return txt.lower()


def evidence_urls(row):
    ev = P.ROOT / row.get("_meta", {}).get("evidence_dir", "")
    p = ev / "urls.json"
    if p.exists():
        return set(json.loads(p.read_text(encoding="utf-8")).get("urls", []))
    return set()


def norm_auth(methods):
    out = set()
    for m in methods or []:
        m = str(m).lower()
        if "oauth" in m: out.add("oauth2")
        elif "api key" in m or "apikey" in m or "api-key" in m: out.add("api key")
        elif "basic" in m: out.add("basic")
        elif "jwt" in m: out.add("jwt")
        elif "bearer" in m or "token" in m: out.add("token")
        else: out.add(m)
    return out


def get_field(row, field):
    if field == "existing_mcp.status":
        return (row.get("existing_mcp") or {}).get("status", "unknown")
    if field == "buildability.verdict":
        return (row.get("buildability") or {}).get("verdict", "unknown")
    if field == "auth_methods":
        return sorted(norm_auth(row.get("auth_methods")))
    return row.get(field, "unknown")


# ---------------- Loop A ----------------
def checks():
    rows = load("research_v1.json")
    flags = {}
    for row in rows:
        fl = []
        if row.get("error"):
            flags[row["id"]] = ["research_error"]
            continue
        for k, allowed in ENUMS.items():
            if row.get(k) not in allowed:
                fl.append(f"schema:{k}={row.get(k)}")
        if (row.get("existing_mcp") or {}).get("status") not in MCP_ENUM:
            fl.append("schema:existing_mcp.status")
        if (row.get("buildability") or {}).get("verdict") not in VERDICT_ENUM:
            fl.append("schema:buildability.verdict")
        txt = evidence_text(row)
        urls = evidence_urls(row)
        if not txt:
            fl.append("no_evidence_saved")
        for e in row.get("evidence", []):
            u = (e.get("url") or "").split("#")[0].rstrip("/")
            if u and not any(u == x.rstrip("/") or x.rstrip("/").startswith(u) or u.startswith(x.rstrip("/")) for x in urls):
                fl.append(f"uncited_url:{u[:80]}")
        auth_kw = {"oauth2": ["oauth"], "api key": ["api key", "apikey", "api-key", "x-api-key"],
                   "basic": ["basic auth", "basic authentication"], "jwt": ["jwt", "json web token"],
                   "token": ["token", "bearer"]}
        for a in norm_auth(row.get("auth_methods")):
            kws = auth_kw.get(a, [a])
            if txt and not any(k in txt for k in kws):
                fl.append(f"auth_ungrounded:{a}")
        mcp = (row.get("existing_mcp") or {}).get("status")
        if mcp in ("official", "community") and txt and "mcp" not in txt and "model context protocol" not in txt:
            fl.append("mcp_ungrounded")
        acc = row.get("access")
        if acc == "free_self_serve" and txt and "free" not in txt:
            fl.append("access_soft:free_not_in_docs")
        if acc == "partner_gated" and txt and not any(k in txt for k in ("partner", "sales", "contact")):
            fl.append("access_soft:gate_not_in_docs")
        if fl:
            flags[row["id"]] = fl
    save("verification/loop_a_flags.json", flags)
    hard = {i: f for i, f in flags.items() if any(not x.startswith("access_soft") for x in f)}
    print(f"Loop A: {len(rows)} rows checked, {len(flags)} flagged ({len(hard)} hard). -> verification/loop_a_flags.json")
    return flags


# ---------------- Loop B ----------------
def second_pass(only=None):
    R.run(pass_no=2, only=only)


def reconcile():
    v1 = {r["id"]: r for r in load("research_v1.json")}
    v2 = {r["id"]: r for r in load("research_v2_raw.json")}
    flags = json.loads((VDIR / "loop_a_flags.json").read_text(encoding="utf-8")) if (VDIR / "loop_a_flags.json").exists() else {}
    final, disputes_all = [], []
    agree_counts = {f: 0 for f in COMPARE_FIELDS}
    compared = 0
    for id_, row1 in sorted(v1.items()):
        row2 = v2.get(id_)
        row = json.loads(json.dumps(row1))  # deep copy
        ver = {"disputes": [], "flags": flags.get(str(id_), flags.get(id_, []))}
        if row1.get("error") or not row2 or row2.get("error"):
            ver["agreement"] = "single_pass"
            row["verification"] = ver
            final.append(row)
            continue
        compared += 1
        diffs = []
        for f in COMPARE_FIELDS:
            a, b = get_field(row1, f), get_field(row2, f)
            if a == b:
                agree_counts[f] += 1
            else:
                diffs.append(f)
        hard_flags = [x for x in ver["flags"] if not x.startswith("access_soft")]
        # targeted improvement: if BOTH passes say access unknown, fetch pricing evidence specifically
        if get_field(row1, "access") == "unknown" and get_field(row2, "access") == "unknown":
            try:
                hits = P.search(f"{row1['name']} pricing API access free plan", max_results=5)
                cand = [h["href"] for h in hits if h.get("href")][:3]
                extra = ""
                for u in cand:
                    d = P.fetch(u) or P.fetch_jina(u)
                    if d and len(d["text"]) > 500:
                        extra += f"\n[PRICING DOC] {d['url']}\n{d['text'][:8000]}\n"
                        ev = P.ROOT / row1.get("_meta", {}).get("evidence_dir", "")
                        if ev.exists():
                            k = len(list(ev.glob("page*.txt"))) + 1
                            (ev / f"page{k}.txt").write_text(f"URL: {d['url']}\nVIA: pricing-refetch\n\n{d['text']}", encoding="utf-8")
                            meta_p = ev / "urls.json"
                            if meta_p.exists():
                                meta = json.loads(meta_p.read_text(encoding="utf-8"))
                                meta["urls"].append(d["url"])
                                meta_p.write_text(json.dumps(meta, indent=1), encoding="utf-8")
                        break
                if extra:
                    pr = f"""For the app "{row1['name']}", two research passes could not determine developer access (free self-serve vs paid vs gated).
Using ONLY this pricing/documentation text, decide the "access" field.
Definitions: free_self_serve = anyone can get API credentials free (incl. free dev tier/sandbox); trial_self_serve = self-serve time-limited trial; paid_plan = credentials need paid subscription; admin_approval = org admin must enable; partner_gated = partnership/contact-sales; no_public_api; unknown if still unclear.
TEXT:{extra}
Return ONLY JSON: {{"access": "<value>", "access_notes": "short", "url": "doc url"}}"""
                    arb2, _ = P.llm_json(pr, model="gemini-3.5-flash")
                    if arb2.get("access") in ENUMS["access"] and arb2["access"] != "unknown":
                        row["access"] = arb2["access"]
                        row["access_notes"] = arb2.get("access_notes", row.get("access_notes", ""))
                        ver["access_refetched"] = True
                        diffs = [f for f in diffs if f != "access"]
            except Exception as e:
                ver["access_refetch_error"] = str(e)[:150]
        if not diffs and not hard_flags:
            ver["agreement"] = "full"
            if row.get("confidence") in ("medium", "low"):
                row["confidence"] = "high" if row.get("confidence") == "medium" else "medium"
        else:
            ver["agreement"] = "disputed" if diffs else "flagged"
            # arbiter settles disputed fields + hard flags using the saved evidence
            docs_txt = evidence_text(row1)[:24000]
            disputed_detail = {f: {"pass1": get_field(row1, f), "pass2": get_field(row2, f)} for f in diffs}
            prompt = f"""You are the verification arbiter for app research on "{row1['name']}".
Two independent research passes disagreed on some fields, or automated checks flagged issues.
Using ONLY the documentation text below, decide the correct value for each disputed field.

DISPUTED FIELDS (pass1 vs pass2):
{json.dumps(disputed_detail, indent=1)}

AUTOMATED FLAGS: {json.dumps(hard_flags)}

FULL PASS-1 ANSWER: {json.dumps({k: row1.get(k) for k in ('description','auth_methods','auth_notes','access','access_notes','api_type','api_breadth','api_notes','existing_mcp','buildability','evidence')}, ensure_ascii=False)}
FULL PASS-2 ANSWER: {json.dumps({k: row2.get(k) for k in ('description','auth_methods','auth_notes','access','access_notes','api_type','api_breadth','api_notes','existing_mcp','buildability','evidence')}, ensure_ascii=False)}

DOCUMENTATION:
{docs_txt}

Rules: prefer what the docs explicitly support; if neither pass is supported, output "unknown" for that field.
A gated finding (paid/partner/admin) is valid if docs support it. Cite doc URLs.
Return ONLY JSON: {{"resolutions": {{"<field>": {{"value": <correct value, same type as the fields above>, "reason": "short", "url": "doc url or empty"}}}}, "confidence": "high|medium|low"}}
For auth_methods the value must be a list; for existing_mcp.status / buildability.verdict use the plain string value."""
            try:
                arb, model = P.llm_json(prompt, model="gemini-3.5-flash")
                for f, res in (arb.get("resolutions") or {}).items():
                    val = res.get("value")
                    if f == "existing_mcp.status":
                        row.setdefault("existing_mcp", {})["status"] = val if val in MCP_ENUM else "unknown"
                    elif f == "buildability.verdict":
                        row.setdefault("buildability", {})["verdict"] = val if val in VERDICT_ENUM else "unknown"
                    elif f == "auth_methods":
                        row["auth_methods"] = val if isinstance(val, list) else row.get("auth_methods")
                    elif f in ENUMS:
                        row[f] = val if val in ENUMS[f] else "unknown"
                    ver["disputes"].append({"field": f, "pass1": get_field(row1, f), "pass2": get_field(row2, f),
                                            "final": val, "reason": res.get("reason", "")[:300], "url": res.get("url", "")})
                row["confidence"] = arb.get("confidence", row.get("confidence", "medium"))
                ver["arbiter_model"] = model
            except Exception as e:
                ver["arbiter_error"] = str(e)[:200]
                # keep pass-1 values, mark low confidence
                row["confidence"] = "low"
            disputes_all.append({"id": id_, "name": row1["name"], "disputes": ver["disputes"], "flags": hard_flags})
        row["verification"] = ver
        row["_meta"]["finalized_at"] = datetime.datetime.now().isoformat()
        final.append(row)
        print(f"[{id_:3d}] {row1['name']:<28} {ver['agreement']}" + (f" disputes={len(ver['disputes'])}" if ver["disputes"] else ""), flush=True)
    save("final.json", final)
    stats = {"apps_compared": compared,
             "field_agreement_rate": {f: round(agree_counts[f] / compared, 3) for f in COMPARE_FIELDS} if compared else {},
             "full_agreement": sum(1 for r in final if r.get("verification", {}).get("agreement") == "full"),
             "disputed_or_flagged": len(disputes_all)}
    save("verification/diff_report.json", {"stats": stats, "disputes": disputes_all})
    print("Reconcile done ->", json.dumps(stats))


# ---------------- Human audit ----------------
def audit_sheet(n=15):
    final = load("final.json") or load("research_v1.json")
    by_cat = {}
    for r in final:
        by_cat.setdefault(r["category"], []).append(r)
    picked, used = [], set()
    # one per category, prefer disputed/low-confidence within each
    for cat, rows in by_cat.items():
        rows_sorted = sorted(rows, key=lambda r: (0 if r.get("verification", {}).get("disputes") else 1,
                                                  0 if r.get("confidence") == "low" else 1))
        for r in rows_sorted:
            if r["id"] not in used:
                picked.append(r); used.add(r["id"]); break
    # fill remaining slots with disputed / low-confidence / error rows
    rest = sorted([r for r in final if r["id"] not in used],
                  key=lambda r: (0 if r.get("error") else 1,
                                 0 if r.get("verification", {}).get("disputes") else 1,
                                 0 if r.get("confidence") == "low" else 1, r["id"]))
    for r in rest:
        if len(picked) >= n: break
        picked.append(r); used.add(r["id"])
    picked.sort(key=lambda r: r["id"])
    save("verification/audit_sample.json", [{"id": r["id"], "name": r["name"]} for r in picked])

    fields = [("auth_methods", "Auth method(s)"), ("access", "Self-serve vs gated"),
              ("api_type", "API type"), ("existing_mcp.status", "Existing MCP"), ("buildability.verdict", "Buildability")]
    # markdown sheet
    md = ["# Human audit sheet — 15-app stratified sample",
          "", "For each app: open the evidence links, check our answer, mark right/wrong/unsure.",
          "Fill the HTML form (audit.html) and click 'Generate results JSON', save as data/verification/audit_results.json — or edit the marks below.", ""]
    for r in picked:
        md.append(f"## {r['id']}. {r['name']} ({r['category']})")
        md.append(f"What it does: {r.get('description','?')}")
        for f, label in fields:
            md.append(f"- {label}: **{get_field(r, f)}**  → [ ] right  [ ] wrong  [ ] unsure")
        md.append("- Evidence: " + " | ".join(e.get("url", "") for e in r.get("evidence", [])[:4]))
        md.append("")
    (VDIR / "audit_sheet.md").write_text("\n".join(md), encoding="utf-8")

    # interactive HTML form
    cards = []
    for r in picked:
        ev_links = "".join(f'<a href="{e.get("url","")}" target="_blank" rel="noopener">doc {i+1}</a> '
                           for i, e in enumerate(r.get("evidence", [])[:4]))
        rows_html = ""
        for f, label in fields:
            val = get_field(r, f)
            if isinstance(val, list): val = ", ".join(val)
            rows_html += f"""<tr><td>{label}</td><td class="val">{val}</td>
<td><label><input type="radio" name="f{r['id']}_{f.replace('.','_')}" value="right"> right</label>
<label><input type="radio" name="f{r['id']}_{f.replace('.','_')}" value="wrong"> wrong</label>
<label><input type="radio" name="f{r['id']}_{f.replace('.','_')}" value="unsure"> unsure</label></td></tr>"""
        cards.append(f"""<div class="card" data-id="{r['id']}"><h3>{r['id']}. {r['name']} <span class="cat">{r['category']}</span></h3>
<p class="desc">{r.get('description','')}</p><table>{rows_html}</table>
<p class="ev">Evidence: {ev_links}</p>
<input class="corr" placeholder="If wrong, type the correct value(s) here (optional)" data-id="{r['id']}"></div>""")
    html = f"""<!doctype html><html><head><meta charset="utf-8"><title>Human audit — 15 apps</title>
<style>body{{font-family:system-ui,sans-serif;max-width:900px;margin:24px auto;padding:0 16px;background:#0f1420;color:#e8ecf4}}
.card{{background:#171e2e;border:1px solid #2a3550;border-radius:12px;padding:16px;margin:16px 0}}
h3{{margin:0 0 6px}}.cat{{font-size:12px;color:#8fa3c8;font-weight:400;margin-left:8px}}
.desc{{color:#aab8d4;font-size:14px}}table{{width:100%;border-collapse:collapse;font-size:14px}}
td{{padding:6px 8px;border-top:1px solid #232d45}}.val{{color:#7ee0a3;font-weight:600}}
label{{margin-right:10px;cursor:pointer}}.ev a{{color:#7ab8ff;margin-right:6px}}
.corr{{width:100%;margin-top:8px;padding:8px;border-radius:8px;border:1px solid #2a3550;background:#0f1420;color:#e8ecf4}}
button{{background:#3b82f6;color:#fff;border:0;padding:12px 20px;border-radius:10px;font-size:16px;cursor:pointer;margin:12px 0}}
textarea{{width:100%;height:180px;background:#0f1420;color:#7ee0a3;border:1px solid #2a3550;border-radius:10px;padding:10px;font-family:monospace}}
</style></head><body>
<h1>Human accuracy audit — 15 apps</h1>
<p>Open each evidence link, compare with our answer, mark <b>right / wrong / unsure</b>. Takes ~20 minutes. Then click the button and save the JSON as <code>data/verification/audit_results.json</code> (or paste it back to the agent).</p>
{''.join(cards)}
<button onclick="gen()">Generate results JSON</button>
<textarea id="out" placeholder="results appear here"></textarea>
<script>
const FIELDS={json.dumps([f for f,_ in fields])};
function gen(){{
 const res=[];
 document.querySelectorAll('.card').forEach(c=>{{
  const id=+c.dataset.id, fields={{}};
  FIELDS.forEach(f=>{{
   const sel=c.querySelector('input[name="f'+id+'_'+f.replace('.','_')+'"]:checked');
   fields[f]=sel?sel.value:'unmarked';
  }});
  const corr=c.querySelector('.corr').value.trim();
  res.push({{id, fields, corrections:corr}});
 }});
 document.getElementById('out').value=JSON.stringify(res,null,1);
}}
</script></body></html>"""
    (VDIR / "audit.html").write_text(html, encoding="utf-8")
    print(f"Audit sheet: {len(picked)} apps -> verification/audit.html + audit_sheet.md")


def ingest_audit():
    results = json.loads((VDIR / "audit_results.json").read_text(encoding="utf-8"))
    final = {r["id"]: r for r in load("final.json")}
    v1 = {r["id"]: r for r in load("research_v1.json")}
    per_field = {}
    misses = []
    for entry in results:
        r = final.get(entry["id"])
        if not r: continue
        r1 = v1.get(entry["id"], {})
        for f, mark in entry.get("fields", {}).items():
            if mark == "unmarked": continue
            pf = per_field.setdefault(f, {"v1_right": 0, "v1_wrong": 0, "final_right": 0, "final_wrong": 0, "unsure": 0, "n": 0})
            pf["n"] += 1
            v1val, finval = get_field(r1, f), get_field(r, f)
            same = v1val == finval
            if mark == "right":
                pf["final_right"] += 1
                if same: pf["v1_right"] += 1
                else: pf["v1_wrong"] += 1
            elif mark == "wrong":
                pf["final_wrong"] += 1
                if same: pf["v1_wrong"] += 1
                misses.append({"id": entry["id"], "name": r["name"], "field": f,
                               "our_value": finval, "correction": entry.get("corrections", "")})
                # apply correction if provided as simple value
                corr = entry.get("corrections", "").strip()
                if corr:
                    if f == "auth_methods":
                        r["auth_methods"] = [x.strip() for x in corr.split(",")]
                    elif f == "existing_mcp.status":
                        r.setdefault("existing_mcp", {})["status"] = corr
                    elif f == "buildability.verdict":
                        r.setdefault("buildability", {})["verdict"] = corr
                    elif f in ENUMS and corr in ENUMS[f]:
                        r[f] = corr
                    r.setdefault("verification", {})["human_corrected"] = True
            else:
                pf["unsure"] += 1
    save("final.json", list(final.values()))
    def acc(pf, side):
        right, wrong = pf[side + "_right"], pf[side + "_wrong"]
        return round(right / (right + wrong), 3) if right + wrong else None
    summary = {"sample_apps": len(results), "method": "human marks final answer right/wrong vs real docs; v1 accuracy inferred where v1==final (same answer) or v1!=final & final right (v1 wrong). unsure excluded.",
               "per_field": {f: {**pf, "v1_accuracy": acc(pf, "v1"), "final_accuracy": acc(pf, "final")} for f, pf in per_field.items()},
               "misses": misses}
    tot_r = sum(pf["final_right"] for pf in per_field.values()); tot_w = sum(pf["final_wrong"] for pf in per_field.values())
    v1_r = sum(pf["v1_right"] for pf in per_field.values()); v1_w = sum(pf["v1_wrong"] for pf in per_field.values())
    summary["overall_final_accuracy"] = round(tot_r / (tot_r + tot_w), 3) if tot_r + tot_w else None
    summary["overall_v1_accuracy"] = round(v1_r / (v1_r + v1_w), 3) if v1_r + v1_w else None
    save("verification/accuracy.json", summary)
    print(json.dumps({k: summary[k] for k in ("overall_v1_accuracy", "overall_final_accuracy", "sample_apps")}))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--checks", action="store_true")
    ap.add_argument("--second-pass", action="store_true")
    ap.add_argument("--reconcile", action="store_true")
    ap.add_argument("--audit-sheet", action="store_true")
    ap.add_argument("--ingest-audit", action="store_true")
    ap.add_argument("--only", type=str, default=None)
    a = ap.parse_args()
    only = [int(x) for x in a.only.split(",")] if a.only else None
    if a.checks: checks()
    if a.second_pass: second_pass(only)
    if a.reconcile: reconcile()
    if a.audit_sheet: audit_sheet()
    if a.ingest_audit: ingest_audit()
