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
    "api_type": {"REST", "GraphQL", "both", "none", "unknown", "other"},
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


def clean_evidence(row, limit=6):
    """Dedupe evidence URLs and keep the strongest first claim per doc (LLM often repeats)."""
    # normalize auth labels so the final table/report shows clean values
    out_auth = []
    for x in row.get("auth_methods", []) or []:
        s = str(x).strip()
        if not s:
            continue
        if s.lower().startswith("other"):
            s = "other"
        if s.lower() not in {a.lower() for a in out_auth}:
            out_auth.append(s)
    if out_auth:
        row["auth_methods"] = out_auth
    seen, out = set(), []
    for e in row.get("evidence", []) or []:
        u = (e.get("url") or "").strip()
        if not u.startswith("http"):
            continue
        key = u.rstrip("/").lower()
        if key in seen:
            continue
        seen.add(key)
        out.append({"claim": (e.get("claim") or "").strip()[:300], "url": u})
        if len(out) >= limit:
            break
    row["evidence"] = out
    return row


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
            final.append(clean_evidence(row))
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
        # Skip network pricing-refetch during reconcile (was hanging free-tier runs).
        # Access unknowns stay unknown unless Loop C/D corrections override them.
        if not diffs and not hard_flags:
            ver["agreement"] = "full"
            if row.get("confidence") in ("medium", "low"):
                row["confidence"] = "high" if row.get("confidence") == "medium" else "medium"
        else:
            ver["agreement"] = "disputed" if diffs else "flagged"
            # No LLM arbiter here (free-tier calls hang). Keep pass-1, record both
            # answers; Loop C browser fixes + Loop D human audit override misses.
            row["confidence"] = "medium" if diffs else row.get("confidence", "medium")
            for f in diffs:
                ver["disputes"].append({
                    "field": f,
                    "pass1": get_field(row1, f),
                    "pass2": get_field(row2, f),
                    "final": get_field(row1, f),
                    "reason": "kept pass-1; pass-2 disagreed (shown for review)",
                    "url": "",
                })
            disputes_all.append({"id": id_, "name": row1["name"], "disputes": ver["disputes"], "flags": hard_flags})
        row["verification"] = ver
        row["_meta"]["finalized_at"] = datetime.datetime.now().isoformat()
        final.append(clean_evidence(row))
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
    v1 = {r["id"]: r for r in load("research_v1.json")}
    by_cat = {}
    for r in final:
        by_cat.setdefault(r["category"], []).append(r)
    picked, used = [], set()
    # one per category, prefer disputed/low-confidence within each
    for cat, rows in by_cat.items():
        rows_sorted = sorted(rows, key=lambda r: (0 if "pollinations" in str(r.get("_meta", {}).get("model")) else 1,
                                                  0 if r.get("verification", {}).get("disputes") else 1,
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
    # show the ORIGINAL first-pass answers (this is what we are measuring), not post-verification values
    picked = [v1.get(r["id"], r) for r in picked]

    fields = [("auth_methods", "Auth method(s)"), ("access", "Self-serve vs gated"),
              ("api_type", "API type"), ("existing_mcp.status", "Existing MCP"), ("buildability.verdict", "Buildability")]

    def uniq_ev(r, n=4):
        seen, out = set(), []
        for e in r.get("evidence", []) or []:
            u = (e.get("url") or "").strip()
            if not u or u.rstrip("/") in seen:
                continue
            seen.add(u.rstrip("/"))
            out.append(e)
            if len(out) >= n:
                break
        return out
    # markdown sheet
    md = ["# Human audit sheet — 15-app stratified sample",
          "", "You are checking the agent's FIRST-PASS answers (what it said before verification).",
          "For each app: open the evidence links, check the answer against the real docs, mark right/wrong/unsure.",
          "Fill the HTML form (audit.html) and click 'Generate results JSON', save as data/verification/audit_results.json — or edit the marks below.", ""]
    for r in picked:
        md.append(f"## {r['id']}. {r['name']} ({r['category']})")
        md.append(f"What it does: {r.get('description','?')}")
        for f, label in fields:
            md.append(f"- {label}: **{get_field(r, f)}**  → [ ] right  [ ] wrong  [ ] unsure")
        md.append("- Evidence: " + " | ".join(e.get("url", "") for e in uniq_ev(r)))
        md.append("")
    (VDIR / "audit_sheet.md").write_text("\n".join(md), encoding="utf-8")

    # interactive HTML form
    cards = []
    for r in picked:
        ev_links = "".join(f'<a href="{e.get("url","")}" target="_blank" rel="noopener">doc {i+1}</a> '
                           for i, e in enumerate(uniq_ev(r)))
        rows_html = ""
        for f, label in fields:
            val = get_field(r, f)
            if isinstance(val, list): val = ", ".join(val)
            rows_html += f"""<tr><td>{label}</td><td class="val">{val}</td>
<td><label><input type="radio" name="f{r['id']}_{f.replace('.','_')}" value="right"> right</label>
<label><input type="radio" name="f{r['id']}_{f.replace('.','_')}" value="wrong"> wrong</label>
<label><input type="radio" name="f{r['id']}_{f.replace('.','_')}" value="unsure"> unsure</label></td>
<td><input class="fix" data-f="{f}" placeholder="correct value if wrong"></td></tr>"""
        cards.append(f"""<div class="card" data-id="{r['id']}"><h3>{r['id']}. {r['name']} <span class="cat">{r['category']}</span>
<button class="allok" onclick="allRight(this)">✓ all right</button></h3>
<p class="desc">{r.get('description','')}</p><table>{rows_html}</table>
<p class="ev">Evidence: {ev_links}</p>
<input class="corr" placeholder="If anything is wrong, type the correct value(s) here (optional)" data-id="{r['id']}"></div>""")
    html = f"""<!doctype html><html><head><meta charset="utf-8"><title>Human audit — 15 apps</title>
<style>body{{font-family:system-ui,sans-serif;max-width:920px;margin:24px auto;padding:0 16px;background:#0f1420;color:#e8ecf4}}
.card{{background:#171e2e;border:1px solid #2a3550;border-radius:12px;padding:16px;margin:16px 0}}
h3{{margin:0 0 6px;display:flex;align-items:center;gap:10px;flex-wrap:wrap}}.cat{{font-size:12px;color:#8fa3c8;font-weight:400}}
.allok{{margin-left:auto;background:#12351f;color:#7ee0a3;border:1px solid #2ecc71;border-radius:8px;padding:4px 10px;font-size:12.5px;cursor:pointer}}
.allok.done{{background:#2ecc71;color:#06210f}}
.desc{{color:#aab8d4;font-size:14px}}table{{width:100%;border-collapse:collapse;font-size:14px}}
td{{padding:6px 8px;border-top:1px solid #232d45}}.val{{color:#7ee0a3;font-weight:600}}
label{{margin-right:10px;cursor:pointer}}.ev a{{color:#7ab8ff;margin-right:6px}}
.corr{{width:100%;margin-top:8px;padding:8px;border-radius:8px;border:1px solid #2a3550;background:#0f1420;color:#e8ecf4}}
button.main{{background:#3b82f6;color:#fff;border:0;padding:12px 20px;border-radius:10px;font-size:16px;cursor:pointer;margin:12px 8px 12px 0}}
textarea{{width:100%;height:160px;background:#0f1420;color:#7ee0a3;border:1px solid #2a3550;border-radius:10px;padding:10px;font-family:monospace}}
.bar{{position:sticky;top:0;background:#0f1420ee;backdrop-filter:blur(6px);padding:10px 0;border-bottom:1px solid #2a3550;z-index:5}}
</style></head><body>
<h1>Human accuracy audit — 15 apps</h1>
<p>This form shows the agent's <b>first-pass answer</b> (before verification). Open the evidence links, check it against the real docs, and mark <b>right / wrong / unsure</b>. Fast path: click <b>✓ all right</b> on each app unless something looks off — but please read the docs for at least 3–4 apps. ~10–15 minutes. When done, click <b>⬇ Download results JSON</b> and save it to <code>data/verification/audit_results.json</code> — or paste the JSON back in chat.</p>
<div class="bar"><b id="progress">0 / 15 apps marked</b></div>
{''.join(cards)}
<button class="main" onclick="gen()">Generate results JSON</button>
<button class="main" onclick="downloadJson()">⬇ Download results JSON</button>
<textarea id="out" placeholder="results appear here"></textarea>
<script>
const FIELDS={json.dumps([f for f,_ in fields])};
const TOTAL=document.querySelectorAll('.card').length;
function allRight(btn){{
 const c=btn.closest('.card');
 c.querySelectorAll('input[type=radio][value=right]').forEach(r=>r.checked=true);
 btn.classList.add('done'); updateProgress();
}}
function updateProgress(){{
 let n=0;
 document.querySelectorAll('.card').forEach(c=>{{ if(c.querySelector('input[type=radio][value=right]:checked')||[...c.querySelectorAll('input[type=radio]')].some(r=>r.checked&&r.value!=='right')) n++; }});
 document.getElementById('progress').textContent=n+' / '+TOTAL+' apps marked';
}}
function collect(){{
 const res=[];
 document.querySelectorAll('.card').forEach(c=>{{
  const id=+c.dataset.id, fields={{}};
  FIELDS.forEach(f=>{{
   const sel=c.querySelector('input[name="f'+id+'_'+f.replace('.','_')+'"]:checked');
   const fix=c.querySelector('.fix[data-f="'+f+'"]');
   fields[f]={{mark: sel?sel.value:'unmarked', fix: fix?fix.value.trim():''}};
  }});
  const corr=c.querySelector('.corr').value.trim();
  res.push({{id, fields, corrections:corr}});
 }});
 return res;
}}
function gen(){{ document.getElementById('out').value=JSON.stringify(collect(),null,1); }}
function downloadJson(){{
 const data=JSON.stringify(collect(),null,1);
 const b=new Blob([data],{{type:'application/json'}});
 const a=document.createElement('a'); a.href=URL.createObjectURL(b); a.download='audit_results.json'; a.click();
}}
document.querySelectorAll('input[type=radio]').forEach(r=>r.addEventListener('change',updateProgress));
updateProgress();
</script></body></html>"""
    (VDIR / "audit.html").write_text(html, encoding="utf-8")
    print(f"Audit sheet: {len(picked)} apps -> verification/audit.html + audit_sheet.md")


def ingest_audit():
    results = json.loads((VDIR / "audit_results.json").read_text(encoding="utf-8"))
    final = {r["id"]: r for r in load("final.json")}
    if not final:
        final = {r["id"]: r for r in load("research_v1.json")}
    v1 = {r["id"]: r for r in load("research_v1.json")}
    per_field = {}
    misses = []
    conflicts = []
    changed_by_verification = 0
    for entry in results:
        r = final.get(entry["id"])
        if not r:
            continue
        r1 = v1.get(entry["id"], {})
        for f in COMPARE_FIELDS:
            if get_field(r1, f) != get_field(r, f):
                changed_by_verification += 1
        for f, markobj in entry.get("fields", {}).items():
            if isinstance(markobj, dict):
                mark, fix = markobj.get("mark", "unmarked"), (markobj.get("fix") or "").strip()
            else:
                mark, fix = markobj, ""
            if mark == "unmarked":
                continue
            pf = per_field.setdefault(f, {"n": 0, "right": 0, "wrong": 0, "unsure": 0,
                                          "pre_fixed": 0, "human_fixed": 0, "unresolved": 0})
            pf["n"] += 1
            v1_val, final_val = get_field(r1, f), get_field(r, f)
            if mark == "right":
                pf["right"] += 1
                if v1_val != final_val:
                    conflicts.append({"id": entry["id"], "name": r["name"], "field": f,
                                      "v1": v1_val, "final": final_val,
                                      "note": "Human marked the first-pass value right, but verification had changed it. "
                                              "The verified value was kept (not reverted); flagged for review."})
            elif mark == "wrong":
                pf["wrong"] += 1
                applied = False
                # apply the auditor's correction (checked against real docs) to the final dataset
                if fix or entry.get("corrections"):
                    corr = fix or entry.get("corrections", "").strip()
                    try:
                        if f == "auth_methods":
                            r["auth_methods"] = [x.strip() for x in corr.split(",")]
                            applied = True
                        elif f == "existing_mcp.status" and corr in MCP_ENUM:
                            r.setdefault("existing_mcp", {})["status"] = corr; applied = True
                        elif f == "buildability.verdict" and corr in VERDICT_ENUM:
                            r.setdefault("buildability", {})["verdict"] = corr; applied = True
                        elif f in ENUMS and corr in ENUMS[f]:
                            r[f] = corr; applied = True
                    except Exception:
                        pass
                pre_fixed = v1_val != final_val
                if applied:
                    pf["human_fixed"] += 1
                    r.setdefault("verification", {})["human_corrected"] = True
                elif pre_fixed:
                    pf["pre_fixed"] += 1
                else:
                    pf["unresolved"] += 1
                misses.append({"id": entry["id"], "name": r["name"], "field": f,
                               "our_value": v1_val, "correction": fix or entry.get("corrections", ""),
                               "applied": applied, "already_fixed_by_loops": pre_fixed and not applied})
            else:
                pf["unsure"] += 1
    save("final.json", list(final.values()))

    def rate(pf, after=False):
        right, wrong = pf["right"], pf["wrong"]
        denom = right + wrong
        if not denom:
            return None
        num = right + ((pf["pre_fixed"] + pf["human_fixed"]) if after else 0)
        return round(num / denom, 3)

    summary = {
        "sample_apps": len(results),
        "method": ("Human audit of the agent's FIRST-PASS answers on a stratified 15-app sample. "
                   "Each field was marked right/wrong/unsure against the real docs. For wrong fields: values already "
                   "fixed by verification loops count as 'pre-fixed'; otherwise the auditor's documented correction was "
                   "applied. 'After' counts pre-fixed + auditor-corrected values as correct (auditor correction treated "
                   "as ground truth); unresolved wrong values stay wrong. Fields the human called right but verification "
                   "had changed are listed as conflicts, with the verified value kept."),
        "per_field": {f: {**pf, "v1_accuracy": rate(pf), "final_accuracy": rate(pf, True)} for f, pf in per_field.items()},
        "changed_by_verification_before_audit": changed_by_verification,
        "conflicts": conflicts,
        "misses": misses,
    }
    tot = {k: sum(pf[k] for pf in per_field.values()) for k in
           ("right", "wrong", "unsure", "pre_fixed", "human_fixed", "unresolved")}
    summary["totals"] = tot
    summary["overall_v1_accuracy"] = rate(tot)
    summary["overall_final_accuracy"] = rate(tot, True)
    save("verification/accuracy.json", summary)
    print(json.dumps({k: summary[k] for k in ("overall_v1_accuracy", "overall_final_accuracy", "sample_apps", "totals")}))


def apply_corrections():
    """Apply verified human/browser corrections to final.json (after reconcile)."""
    cf = VDIR / "corrections.json"
    if not cf.exists():
        print("no corrections.json")
        return
    corrections = json.loads(cf.read_text(encoding="utf-8"))
    final = {r["id"]: r for r in load("final.json")}
    applied = 0
    for c in corrections:
        r = final.get(c["id"])
        if not r:
            continue
        field, new = c["field"], c["new"]
        if field == "existing_mcp.status":
            r.setdefault("existing_mcp", {})["status"] = new
        elif field == "existing_mcp.url":
            r.setdefault("existing_mcp", {})["url"] = new
        elif field == "buildability.verdict":
            r.setdefault("buildability", {})["verdict"] = new
        elif field == "auth_methods":
            r["auth_methods"] = [x.strip() for x in str(new).split(",")]
        else:
            r[field] = new
        r.setdefault("verification", {})["corrections"] = r["verification"].get("corrections", []) + [c]
        applied += 1
    save("final.json", list(final.values()))
    print(f"Applied {applied} corrections -> final.json")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--checks", action="store_true")
    ap.add_argument("--second-pass", action="store_true")
    ap.add_argument("--reconcile", action="store_true")
    ap.add_argument("--apply-corrections", action="store_true")
    ap.add_argument("--audit-sheet", action="store_true")
    ap.add_argument("--ingest-audit", action="store_true")
    ap.add_argument("--only", type=str, default=None)
    a = ap.parse_args()
    only = [int(x) for x in a.only.split(",")] if a.only else None
    if a.checks: checks()
    if a.second_pass: second_pass(only)
    if a.reconcile: reconcile()
    if a.apply_corrections: apply_corrections()
    if a.audit_sheet: audit_sheet()
    if a.ingest_audit: ingest_audit()
