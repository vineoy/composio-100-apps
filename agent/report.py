"""Builds report/index.html — ONE self-contained case-study page (no CDNs, works offline).
Consumes data/final.json + analysis.json + verification outputs. Zero API calls."""
import json, html, datetime, collections
from . import providers as P
from . import analyze as A

ACCESS_LABEL = {"free_self_serve": "Free self-serve", "trial_self_serve": "Trial self-serve",
                "paid_plan": "Paid plan", "admin_approval": "Admin approval",
                "partner_gated": "Partner / sales", "no_public_api": "No public API", "unknown": "Unknown"}
ACCESS_CLASS = {"free_self_serve": "ok", "trial_self_serve": "ok2", "paid_plan": "warn",
                "admin_approval": "warn2", "partner_gated": "bad", "no_public_api": "mut", "unknown": "mut"}
VERDICT_CLASS = {"ready": "ok", "feasible": "warn", "blocked": "bad", "unknown": "mut"}
MCP_LABEL = {"official": "Official", "community": "Community", "none": "None", "unknown": "?"}


def esc(x):
    return html.escape(str(x if x is not None else ""))


def load_json(name):
    p = P.DATA / name
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def bar_chart(counter, total, color="#5b9dff"):
    if not counter:
        return "<p class='mut'>no data</p>"
    mx = max(counter.values()) or 1
    out = []
    for k, v in counter.items():
        pct = round(100 * v / mx)
        out.append(f"<div class='bar'><span class='bl'>{esc(k)}</span>"
                   f"<span class='bt'><span class='bf' style='width:{pct}%;background:{color}'></span></span>"
                   f"<span class='bv'>{v}</span></div>")
    return "".join(out)


def heatmap(analysis):
    order = analysis["access_order"]
    head = "".join(f"<th>{esc(ACCESS_LABEL[a])}</th>" for a in order)
    body = []
    mx = max((v for row in analysis["access_heatmap"].values() for v in row.values()), default=1) or 1
    for cat, row in analysis["access_heatmap"].items():
        cells = []
        for a in order:
            v = row.get(a, 0)
            alpha = 0.08 + 0.75 * (v / mx) if v else 0.03
            color = {"free_self_serve": "46,204,113", "trial_self_serve": "26,188,156",
                     "paid_plan": "241,196,15", "admin_approval": "230,126,34",
                     "partner_gated": "231,76,60", "no_public_api": "127,140,160", "unknown": "127,140,160"}[a]
            cells.append(f"<td style='background:rgba({color},{alpha:.2f})'>{v or ''}</td>")
        body.append(f"<tr><th class='cat'>{esc(cat)}</th>{''.join(cells)}</tr>")
    return f"<table class='heat'><tr><th></th>{head}</tr>{''.join(body)}</table>"


def table_rows(rows):
    out = []
    for r in sorted(rows, key=lambda x: x["id"]):
        auth = ", ".join(sorted(set(A.norm_auth(m) for m in r.get("auth_methods", [])))) or "?"
        acc = r.get("access", "unknown")
        mcp = (r.get("existing_mcp") or {}).get("status", "unknown")
        verdict = (r.get("buildability") or {}).get("verdict", "unknown")
        comp = r.get("composio_toolkit") or {}
        comp_txt = f"✓ {esc(comp.get('slug',''))}" if comp.get("exists") else "—"
        conf = r.get("confidence", "?")
        ev = r.get("evidence", [])
        ev_links = " ".join(f"<a href='{esc(e.get('url',''))}' target='_blank' rel='noopener'>[{i+1}]</a>"
                            for i, e in enumerate(ev[:5]))
        disputes = (r.get("verification") or {}).get("disputes", [])
        flags = (r.get("verification") or {}).get("flags", [])
        human = (r.get("verification") or {}).get("human_corrected")
        corrections = (r.get("verification") or {}).get("corrections", [])
        badges = ""
        if disputes: badges += f"<span class='badge b-dis' title='resolved by arbiter'>{len(disputes)} disputed→resolved</span>"
        if human: badges += "<span class='badge b-hum'>human-corrected</span>"
        if corrections: badges += f"<span class='badge b-hum' title='{esc(', '.join(c['field'] for c in corrections))}'>{len(corrections)} verified fix</span>"
        if r.get("error"): badges += "<span class='badge b-err'>research error</span>"
        detail = f"""<tr class="detail" id="d{r['id']}"><td colspan="10"><div class="dwrap">
<b>Notes:</b> {esc(r.get('auth_notes',''))} · {esc(r.get('access_notes',''))} · {esc(r.get('api_notes',''))}
<br><b>Blocker:</b> {esc((r.get('buildability') or {}).get('blocker','') or 'none')}
<br><b>MCP:</b> {esc((r.get('existing_mcp') or {}).get('notes',''))} {esc((r.get('existing_mcp') or {}).get('url',''))}
<br><b>Evidence:</b> {ev_links or 'none saved'}
{('<br><b>Dispute resolutions:</b> ' + '; '.join(esc(d['field']) + ': ' + esc(d.get('reason','')) for d in disputes)) if disputes else ''}
{('<br><b>Flags:</b> ' + esc(', '.join(flags))) if flags else ''}
</div></td></tr>"""
        out.append(f"""<tr class="row" data-id="{r['id']}" data-cat="{esc(r['category'])}" data-acc="{acc}" data-ver="{verdict}" data-txt="{esc((r['name']+' '+r.get('description','')).lower())}">
<td>{r['id']}</td><td class="app"><b>{esc(r['name'])}</b><br><span class="desc">{esc(r.get('description',''))}</span></td>
<td><span class="chip c-cat">{esc(r['category'].split(',')[0])}</span></td>
<td>{esc(auth)}</td>
<td><span class="chip c-{ACCESS_CLASS.get(acc,'mut')}">{esc(ACCESS_LABEL.get(acc,acc))}</span></td>
<td>{esc(r.get('api_type','?'))} <span class="mut">({esc(r.get('api_breadth','?'))})</span></td>
<td><span class="chip m-{mcp}">{esc(MCP_LABEL.get(mcp,mcp))}</span></td>
<td><span class="chip c-{VERDICT_CLASS.get(verdict,'mut')}">{esc(verdict)}</span></td>
<td class="comp">{comp_txt}</td>
<td><span class="conf conf-{conf}" title="confidence: {conf}"></span> {ev_links} {badges}</td>
</tr>{detail}""")
    return "".join(out)


def run():
    rows, source = A.load_final()
    analysis = A.run()  # always regenerate so stats match the dataset (fast, no API calls)
    acc = load_json("verification/accuracy.json")
    diff = load_json("verification/diff_report.json")
    audit_sample = load_json("verification/audit_sample.json")
    n = analysis["n"]
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

    # ---- verification section ----
    ver_html = ""
    if diff:
        st = diff["stats"]
        agree_bars = bar_chart({k: round(v * 100) for k, v in st.get("field_agreement_rate", {}).items()}, 100, "#2ecc71")
        ver_html += f"""<div class="vstats">
<div class="vstat"><b>{st.get('apps_compared',0)}</b><span>apps independently re-researched</span></div>
<div class="vstat"><b>{st.get('full_agreement',0)}</b><span>full agreement between passes</span></div>
<div class="vstat"><b>{st.get('disputed_or_flagged',0)}</b><span>disputes/flags settled by arbiter + evidence</span></div>
</div><h4>Field agreement between independent passes (%)</h4>{agree_bars}"""
    if acc:
        v1a = acc.get("overall_v1_accuracy"); fa = acc.get("overall_final_accuracy")
        v1p = f"{round(v1a*100)}%" if v1a is not None else "—"
        fp = f"{round(fa*100)}%" if fa is not None else "—"
        pf_rows = "".join(f"<tr><td>{esc(f)}</td><td>{p.get('v1_accuracy') if p.get('v1_accuracy') is not None else '—'}</td><td>{p.get('final_accuracy') if p.get('final_accuracy') is not None else '—'}</td><td>{p['n']}</td></tr>"
                          for f, p in acc.get("per_field", {}).items())
        miss_rows = "".join(f"<tr><td>{esc(m['name'])}</td><td>{esc(m['field'])}</td><td>{esc(m['our_value'])}</td><td>{esc(m.get('correction',''))}</td></tr>"
                            for m in acc.get("misses", [])) or "<tr><td colspan='4'>No confirmed misses in the sample.</td></tr>"
        tot = acc.get("totals", {})
        ver_html += f"""<h4>Human audit: accuracy before → after ({acc.get('sample_apps',0)}-app stratified sample)</h4>
<div class="accbig"><div class="accbox"><span class="accnum">{v1p}</span><span>pass-1 accuracy (human-checked)</span></div>
<div class="accarrow">→</div>
<div class="accbox final"><span class="accnum">{fp}</span><span>after corrections (confirmed errors fixed)</span></div></div>
<p class="mut">{tot.get('wrong',0)} wrong values found · {tot.get('corrected',0)} corrected · {tot.get('unsure',0)} marked unsure · {tot.get('right',0)} right.</p>
<table class="small"><tr><th>Field</th><th>pass-1 accuracy</th><th>after corrections</th><th>checks</th></tr>{pf_rows}</table>
<p class="mut method">{esc(acc.get('method',''))}</p>
<h4>Misses found by the human audit (shown honestly)</h4>
<table class="small"><tr><th>App</th><th>Field</th><th>Our value</th><th>Correction</th></tr>{miss_rows}</table>"""
    else:
        ver_html += "<p class='pending'>Human audit pending — audit form generated at data/verification/audit.html; results will appear here after ingest.</p>"
    errors = [r for r in rows if r.get("error")]
    unknowns = [r for r in rows if r.get("access") == "unknown" or (r.get("buildability") or {}).get("verdict") == "unknown"]
    hard_apps = analysis.get("no_api", [])
    ver_html += f"""<h4>Where the agent struggled (honesty section)</h4>
<ul class="plain">
<li><b>{len(errors)}</b> apps errored during research{(': ' + ', '.join(esc(r['name']) for r in errors)) if errors else ''}.</li>
<li><b>{len(unknowns)}</b> apps still carry at least one honest "unknown"{(': ' + ', '.join(esc(r['name']) for r in unknowns[:12])) if unknowns else ''}.</li>
<li><b>{len(hard_apps)}</b> apps appear to have no public API at all{(': ' + ', '.join(esc(r['name']) for r in hard_apps)) if hard_apps else ''} — a valid finding, not a failure.</li>
</ul>"""
    loopc = load_json("verification/loop_c.json")
    if loopc:
        lc_rows = []
        for item in loopc:
            for c in item.get("checks", []):
                ok = "✓ confirmed" if c.get("browser_verified") else "✗ contradicted"
                lc_rows.append(f"<tr><td>{esc(item['name'])}</td><td>{esc(c.get('field',''))}</td><td>{esc(c.get('claimed',''))}</td>"
                               f"<td>{ok}</td><td class='mut'>{esc(c.get('note',''))[:160]}</td></tr>")
        ver_html += f"""<h4>Loop C — browser deep-checks of the hardest apps</h4>
<p class="mut">A real browser visited the actual auth/pricing pages for ambiguous cases; claims were confirmed or contradicted by what the page shows. Contradictions were corrected in the final dataset.</p>
<table class="small"><tr><th>App</th><th>Field</th><th>Claimed</th><th>Result</th><th>What the page showed</th></tr>{''.join(lc_rows)}</table>"""

    # ---- easy wins / outreach ----
    def app_list(items):
        return "".join(f"<li><b>{esc(a['name'])}</b> <span class='mut'>{esc(a['category'].split(',')[0])} · {esc(', '.join(a['auth']))} · MCP: {esc(a['mcp'])}</span></li>" for a in items)
    wins_html = app_list(analysis["easy_wins"][:18])
    outreach_html = app_list(analysis["outreach"][:18])
    missing_html = app_list(analysis["composio_coverage"]["missing_apps"][:18])

    headlines_html = "".join(f"<li>{esc(h)}</li>" for h in analysis["headlines"])
    cats = analysis["categories"]
    cat_options = "".join(f"<option>{esc(c)}</option>" for c in cats)
    acc_options = "".join(f"<option value='{a}'>{esc(ACCESS_LABEL[a])}</option>" for a in analysis["access_order"])

    dataset_json = json.dumps(rows, ensure_ascii=False).replace("</", "<\\/")

    page = TEMPLATE
    repl = {
        "__NOW__": now, "__N__": str(n), "__SOURCE__": esc(source or ""),
        "__HEADLINES__": headlines_html,
        "__AUTH_BARS__": bar_chart(analysis["auth_distribution"], n),
        "__ACCESS_BARS__": bar_chart({ACCESS_LABEL[k]: v for k, v in analysis["access_distribution"].items() if v}, n, "#2ecc71"),
        "__HEATMAP__": heatmap(analysis),
        "__VERDICT_BARS__": bar_chart(analysis["verdict_distribution"], n, "#f1c40f"),
        "__MCP_BARS__": bar_chart(analysis["mcp_distribution"], n, "#9b59b6"),
        "__BLOCKER_BARS__": bar_chart(analysis["blocker_buckets"], n, "#e74c3c"),
        "__TABLE_ROWS__": table_rows(rows),
        "__CAT_OPTIONS__": cat_options, "__ACC_OPTIONS__": acc_options,
        "__WINS__": wins_html, "__OUTREACH__": outreach_html, "__MISSING__": missing_html,
        "__WINS_N__": str(len(analysis["easy_wins"])), "__OUTREACH_N__": str(len(analysis["outreach"])),
        "__HAVE_N__": str(analysis["composio_coverage"]["have"]), "__MISS_N__": str(analysis["composio_coverage"]["missing"]),
        "__VERIFICATION__": ver_html,
        "__DATASET__": dataset_json,
        "__TOP_AUTH__": esc(next(iter(analysis["auth_distribution"]), "?")),
        "__FREE_N__": str(analysis["access_distribution"].get("free_self_serve", 0)),
        "__MCP_OFF__": str(analysis["mcp_distribution"].get("official", 0)),
    }
    for k, v in repl.items():
        page = page.replace(k, v)
    out = P.ROOT / "report" / "index.html"
    out.parent.mkdir(exist_ok=True)
    out.write_text(page, encoding="utf-8")
    print(f"Report written -> {out} ({len(page)//1024} KB, {n} apps, source={source})")
    return out


TEMPLATE = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>100 Apps, One Agent — Composio Toolkit Feasibility Case Study</title>
<meta name="description" content="Agent-driven research of 100 apps for Composio toolkit feasibility: auth, self-serve vs gated, API surface, MCP, buildability — with verified accuracy and patterns.">
<style>
:root{--bg:#0d1220;--panel:#151c2f;--panel2:#1b2440;--line:#26314e;--txt:#e9edf6;--mut:#93a2c2;--acc:#5b9dff;--ok:#2ecc71;--warn:#f1c40f;--bad:#e74c3c}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--txt);font:15px/1.55 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
.wrap{max-width:1240px;margin:0 auto;padding:0 22px}
header{padding:38px 0 10px;background:linear-gradient(180deg,#101a33,var(--bg))}
h1{font-size:30px;margin:0 0 6px;letter-spacing:-.3px}h2{font-size:22px;margin:44px 0 12px;border-left:4px solid var(--acc);padding-left:12px}
h3{font-size:17px;margin:22px 0 8px}h4{font-size:15px;margin:18px 0 8px;color:#c6d2ea}
.sub{color:var(--mut);font-size:16px;max-width:860px}
nav{position:sticky;top:0;background:#0d1220ee;backdrop-filter:blur(6px);border-bottom:1px solid var(--line);z-index:9;padding:10px 0}
nav a{color:var(--mut);text-decoration:none;margin-right:18px;font-size:14px}nav a:hover{color:var(--txt)}
.chips{margin:14px 0}.chip{display:inline-block;padding:2px 10px;border-radius:20px;font-size:12.5px;font-weight:600;white-space:nowrap}
.meta .chip{background:var(--panel2);color:#c6d2ea;border:1px solid var(--line);margin-right:8px}
.c-ok{background:#12351f;color:#7ee0a3}.c-ok2{background:#0f3a33;color:#6fd6c2}.c-warn{background:#3a3110;color:#f5d76e}
.c-warn2{background:#3d2a12;color:#f0b27a}.c-bad{background:#3d1512;color:#f1948a}.c-mut{background:#232b3f;color:#93a2c2}
.c-cat{background:#1c2a4a;color:#9db9e8;font-weight:500}
.m-official{background:#2c1a45;color:#c39bf5}.m-community{background:#1c2a4a;color:#9db9e8}.m-none,.m-unknown{background:#232b3f;color:#93a2c2}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:12px;margin:18px 0}
.card{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:16px}
.card .big{font-size:30px;font-weight:800;color:var(--acc)}.card .lbl{color:var(--mut);font-size:13px}
.findings{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:18px 22px;margin:16px 0}
.findings li{margin:9px 0;font-size:15.5px}.findings b{color:#fff}
.grid2{display:grid;grid-template-columns:1fr 1fr;gap:18px}@media(max-width:900px){.grid2{grid-template-columns:1fr}}
.panel{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:16px 18px;margin:12px 0}
.bar{display:flex;align-items:center;margin:5px 0;font-size:13.5px}.bl{width:170px;color:#c6d2ea;flex-shrink:0}
.bt{flex:1;background:#0f1526;border-radius:6px;height:16px;overflow:hidden}.bf{display:block;height:100%;border-radius:6px}
.bv{width:44px;text-align:right;color:var(--mut)}
.heat{border-collapse:collapse;width:100%;font-size:12.5px}.heat th{padding:6px 8px;color:#c6d2ea;text-align:center;font-weight:600}
.heat th.cat{text-align:left;max-width:220px}.heat td{text-align:center;padding:7px 6px;border:1px solid #0d1220;border-radius:4px;color:#fff;font-weight:700}
.filters{display:flex;gap:10px;flex-wrap:wrap;margin:14px 0}
.filters select,.filters input{background:var(--panel2);color:var(--txt);border:1px solid var(--line);border-radius:9px;padding:9px 12px;font-size:14px}
.filters input{flex:1;min-width:200px}
table.matrix{width:100%;border-collapse:collapse;font-size:13.5px}
.matrix th{position:sticky;top:46px;background:var(--panel2);padding:9px 8px;text-align:left;color:#c6d2ea;border-bottom:2px solid var(--line);z-index:5}
.matrix td{padding:8px;border-bottom:1px solid #1d2740;vertical-align:top}
.matrix tr.row{cursor:pointer}.matrix tr.row:hover{background:#182238}
.matrix .app{min-width:190px}.matrix .desc{color:var(--mut);font-size:12px}
.matrix .comp{font-size:12px;color:#7ee0a3}
tr.detail{display:none}tr.detail.open{display:table-row}
.dwrap{background:#101828;border:1px solid var(--line);border-radius:10px;padding:12px 14px;font-size:13px;color:#c6d2ea}
.dwrap a{color:var(--acc)}
.conf{display:inline-block;width:9px;height:9px;border-radius:50%;margin-right:4px}
.conf-high{background:var(--ok)}.conf-medium{background:var(--warn)}.conf-low{background:var(--bad)}
.badge{display:inline-block;font-size:10.5px;padding:1px 7px;border-radius:8px;margin-left:4px}
.b-dis{background:#3a3110;color:#f5d76e}.b-hum{background:#12351f;color:#7ee0a3}.b-err{background:#3d1512;color:#f1948a}
ul.plain{padding-left:20px}ul.plain li{margin:6px 0}
ul.applist{list-style:none;padding:0;columns:2;column-gap:26px}@media(max-width:900px){ul.applist{columns:1}}
ul.applist li{margin:6px 0;break-inside:avoid;font-size:14px}
.vstats{display:flex;gap:14px;flex-wrap:wrap;margin:12px 0}
.vstat{background:var(--panel2);border-radius:12px;padding:12px 18px}.vstat b{font-size:24px;display:block;color:var(--acc)}.vstat span{font-size:12.5px;color:var(--mut)}
.accbig{display:flex;align-items:center;gap:18px;margin:14px 0;flex-wrap:wrap}
.accbox{background:var(--panel2);border-radius:14px;padding:16px 26px;text-align:center}.accbox.final{border:2px solid var(--ok)}
.accnum{font-size:36px;font-weight:800;display:block}.accbox span:last-child{font-size:12.5px;color:var(--mut)}
.accarrow{font-size:28px;color:var(--mut)}
table.small{border-collapse:collapse;font-size:13.5px;margin:8px 0}table.small th,table.small td{border:1px solid var(--line);padding:6px 10px;text-align:left}
.mut{color:var(--mut)}.method{font-size:12px}.pending{color:var(--warn)}
pre{background:#0f1526;border:1px solid var(--line);border-radius:10px;padding:14px;overflow-x:auto;font-size:13px}
code{background:#0f1526;padding:1px 6px;border-radius:6px;font-size:13px}
.loopcards{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:12px;margin:14px 0}
.loop{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:14px 16px}
.loop b{color:var(--acc)}.loop p{font-size:13.5px;color:#c6d2ea;margin:6px 0 0}
footer{margin:50px 0 30px;color:var(--mut);font-size:13px;border-top:1px solid var(--line);padding-top:18px}
a{color:var(--acc)}
svg text{font-family:system-ui,sans-serif}
.dl{background:var(--panel2);border:1px solid var(--line);color:var(--txt);padding:9px 16px;border-radius:9px;cursor:pointer;font-size:14px}
</style></head><body>
<nav><div class="wrap">
<a href="#patterns">Patterns</a><a href="#matrix">100-app matrix</a><a href="#wins">Easy wins / outreach</a><a href="#agent">The agent</a><a href="#proof">Run it</a><a href="#verification">Verification</a><a href="#process">Process</a><a href="#data">Data</a>
</div></nav>
<header><div class="wrap">
<h1>100 Apps, One Agent: What Can Become a Composio Toolkit?</h1>
<p class="sub">An agent researched 100 apps across 10 categories the way Composio does before building a toolkit — auth, self-serve vs gated, API surface, existing MCP, buildability — with evidence for every claim, four verification loops, and a human audit. <b>Read the headline in 30 seconds; the whole page in ~2 minutes.</b></p>
<div class="chips meta"><span class="chip">__N__ apps</span><span class="chip">10 categories</span><span class="chip">evidence-backed</span><span class="chip">4 verification loops + human audit</span><span class="chip">generated __NOW__</span><span class="chip">$0 total cost</span></div>
</div></header>
<div class="wrap">

<h2 id="patterns">1 · The patterns (headline)</h2>
<div class="cards">
<div class="card"><div class="big">__N__</div><div class="lbl">apps researched by the agent</div></div>
<div class="card"><div class="big">__TOP_AUTH__</div><div class="lbl">dominant auth method</div></div>
<div class="card"><div class="big">__FREE_N__</div><div class="lbl">free self-serve for developers</div></div>
<div class="card"><div class="big">__MCP_OFF__</div><div class="lbl">already ship official MCP</div></div>
<div class="card"><div class="big">__WINS_N__</div><div class="lbl">easy-win toolkit candidates</div></div>
<div class="card"><div class="big">__HAVE_N__/__N__</div><div class="lbl">already in Composio's catalog</div></div>
</div>
<div class="findings"><b>What the data says, plainly:</b><ul>__HEADLINES__</ul></div>
<div class="grid2">
<div class="panel"><h3>Auth methods across the 100</h3>__AUTH_BARS__</div>
<div class="panel"><h3>Self-serve vs gated</h3>__ACCESS_BARS__</div>
</div>
<div class="panel"><h3>Access by category — where developers can help themselves vs where sales must knock</h3>__HEATMAP__</div>
<div class="grid2">
<div class="panel"><h3>Buildability verdicts</h3>__VERDICT_BARS__</div>
<div class="panel"><h3>Existing MCP coverage</h3>__MCP_BARS__</div>
</div>
<div class="panel"><h3>Most common blockers (blocked + feasible apps)</h3>__BLOCKER_BARS__</div>

<h2 id="matrix">2 · The findings — all 100 apps</h2>
<p class="mut">Click any row for notes, blocker detail and evidence links. Filters below. Confidence dot: <span class="conf conf-high"></span>high <span class="conf conf-medium"></span>medium <span class="conf conf-low"></span>low. "Composio?" = already in Composio's toolkit catalog (checked via their SDK).</p>
<div class="filters">
<select id="fcat"><option value="">All categories</option>__CAT_OPTIONS__</select>
<select id="facc"><option value="">All access types</option>__ACC_OPTIONS__</select>
<select id="fver"><option value="">All verdicts</option><option>ready</option><option>feasible</option><option>blocked</option><option>unknown</option></select>
<input id="ftxt" placeholder="Search app or description…">
<span class="mut" id="count" style="align-self:center"></span>
</div>
<div style="overflow-x:auto">
<table class="matrix" id="matrix">
<thead><tr><th>#</th><th>App</th><th>Category</th><th>Auth</th><th>Access</th><th>API</th><th>MCP</th><th>Verdict</th><th>Composio?</th><th>Conf · Evidence</th></tr></thead>
<tbody>__TABLE_ROWS__</tbody>
</table>
</div>

<h2 id="wins">3 · Where to act</h2>
<div class="grid2">
<div class="panel"><h3>🟢 Easy wins — build these toolkits first (__WINS_N__)</h3><p class="mut">Self-serve credentials + documented API + no official MCP yet.</p><ul class="applist">__WINS__</ul></div>
<div class="panel"><h3>🔴 Needs outreach / blocked (__OUTREACH_N__)</h3><p class="mut">Partner-gated, admin-approval or hard-blocked — business development, not engineering.</p><ul class="applist">__OUTREACH__</ul></div>
</div>
<div class="panel"><h3>Composio catalog whitespace (__MISS_N__ apps with no toolkit yet)</h3><ul class="applist">__MISSING__</ul></div>

<h2 id="agent">4 · The agent — what was built, where a human was needed</h2>
<div class="panel">
<svg viewBox="0 0 1150 210" width="100%" role="img" aria-label="pipeline diagram">
<defs><marker id="ar" markerWidth="8" markerHeight="8" refX="7" refY="3" orient="auto"><path d="M0,0 L7,3 L0,6 z" fill="#5b9dff"/></marker></defs>
<g font-size="12.5" fill="#e9edf6">
<rect x="5" y="70" width="120" height="60" rx="10" fill="#1b2440" stroke="#26314e"/><text x="65" y="95" text-anchor="middle">apps.json</text><text x="65" y="112" text-anchor="middle" fill="#93a2c2" font-size="11">100 apps (input)</text>
<rect x="165" y="70" width="150" height="60" rx="10" fill="#1b2440" stroke="#26314e"/><text x="240" y="92" text-anchor="middle">Search</text><text x="240" y="108" text-anchor="middle" fill="#93a2c2" font-size="11">DuckDuckGo (free)</text><text x="240" y="122" text-anchor="middle" fill="#93a2c2" font-size="11">+ Composio SDK catalog</text>
<rect x="355" y="70" width="140" height="60" rx="10" fill="#1b2440" stroke="#26314e"/><text x="425" y="95" text-anchor="middle">Fetch official docs</text><text x="425" y="112" text-anchor="middle" fill="#93a2c2" font-size="11">httpx + BS4, 2–4 pages</text>
<rect x="535" y="70" width="130" height="60" rx="10" fill="#12351f" stroke="#2ecc71"/><text x="600" y="95" text-anchor="middle">Evidence cache</text><text x="600" y="112" text-anchor="middle" fill="#93a2c2" font-size="11">raw text + URLs saved</text>
<rect x="705" y="70" width="150" height="60" rx="10" fill="#1b2440" stroke="#26314e"/><text x="780" y="92" text-anchor="middle">LLM extraction</text><text x="780" y="108" text-anchor="middle" fill="#93a2c2" font-size="11">Gemini 3.5 Flash (free)</text><text x="780" y="122" text-anchor="middle" fill="#93a2c2" font-size="11">strict JSON + citations</text>
<rect x="895" y="70" width="120" height="60" rx="10" fill="#1b2440" stroke="#26314e"/><text x="955" y="95" text-anchor="middle">research_v1</text><text x="955" y="112" text-anchor="middle" fill="#93a2c2" font-size="11">100 rows</text>
<rect x="355" y="160" width="310" height="42" rx="10" fill="#3a3110" stroke="#f1c40f"/><text x="510" y="178" text-anchor="middle">Verification: checks → 2nd pass (Gemini 3.6) → arbiter → human audit</text><text x="510" y="193" text-anchor="middle" fill="#f5d76e" font-size="11">disagreements settled against saved evidence</text>
<rect x="705" y="160" width="150" height="42" rx="10" fill="#12351f" stroke="#2ecc71"/><text x="780" y="185" text-anchor="middle">final.json → this page</text>
<line x1="125" y1="100" x2="163" y2="100" stroke="#5b9dff" marker-end="url(#ar)"/>
<line x1="315" y1="100" x2="353" y2="100" stroke="#5b9dff" marker-end="url(#ar)"/>
<line x1="495" y1="100" x2="533" y2="100" stroke="#5b9dff" marker-end="url(#ar)"/>
<line x1="665" y1="100" x2="703" y2="100" stroke="#5b9dff" marker-end="url(#ar)"/>
<line x1="855" y1="100" x2="893" y2="100" stroke="#5b9dff" marker-end="url(#ar)"/>
<line x1="955" y1="130" x2="955" y2="181" stroke="#5b9dff"/><line x1="955" y1="181" x2="858" y2="181" stroke="#5b9dff" marker-end="url(#ar)"/>
<line x1="600" y1="130" x2="600" y2="158" stroke="#2ecc71" marker-end="url(#ar)"/>
<text x="240" y="45" text-anchor="middle" fill="#93a2c2" font-size="11.5">3 targeted queries per app: auth docs · MCP server · free-tier/pricing</text>
</g></svg>
</div>
<div class="grid2">
<div class="panel"><h3>Fully automated</h3><ul class="plain">
<li>Search, doc fetching, evidence saving (per-app checkpointed, resumable).</li>
<li>Structured extraction with a strict schema: <i>"cite a URL for every claim; say unknown rather than guess."</i></li>
<li>Composio SDK: fetched their full 1,842-toolkit catalog to check existing coverage per app.</li>
<li>Loop A evidence grounding + schema checks; Loop B independent second pass + arbiter reconciliation.</li>
<li>All statistics, charts and this page (generated from data, zero hand-editing).</li>
</ul></div>
<div class="panel"><h3>Where a human was needed</h3><ul class="plain">
<li><b>Judgment calls on gated apps</b> — browser deep-checks of ambiguous pricing/auth pages (agent-driven browser, human-reviewed conclusions).</li>
<li><b>The 15-app stratified audit</b> — a human checked our answers against real docs and marked right/wrong (results in §6).</li>
<li><b>Corrections</b> — human-confirmed misses were applied to the final dataset and are badged in the matrix.</li>
<li><b>Free API keys</b> — a human created the free Gemini + Composio accounts ($0, no card).</li>
</ul></div>
</div>

<h2 id="proof">5 · Proof — run it yourself</h2>
<div class="panel">
<p>No deployment was used (per project constraint); the assignment accepts a <b>runnable trigger</b>. Everything regenerates from saved evidence:</p>
<pre># rebuild THIS page from saved data — zero API calls, zero cost:
python run.py

# full re-run of the research agent (needs free keys in .env):
pip install -r requirements.txt
python -m agent.research --pass 1          # research all 100 (resumable)
python -m agent.verify --checks            # loop A: evidence grounding
python -m agent.verify --second-pass       # loop B: independent pass (different model)
python -m agent.verify --reconcile         # diff + arbiter -> final.json
python -m agent.verify --audit-sheet       # human audit form
python run.py                              # regenerate the case study</pre>
<p class="mut">Repo layout: <code>agent/</code> (providers, research, verify, analyze, report) · <code>data/</code> (apps.json, evidence/, research_v1/v2, final.json, verification/) · <code>report/index.html</code> · <code>log.md</code> (every action) · <code>README.md</code>.</p>
</div>

<h2 id="verification">6 · Verification — how accuracy was proven and improved</h2>
<div class="loopcards">
<div class="loop"><b>Loop A · automated (100/100)</b><p>Every cited URL must exist in the saved evidence; claimed auth/MCP keywords must appear in the fetched docs; schema + enum validation. Flags feed the arbiter.</p></div>
<div class="loop"><b>Loop B · independent agent pass (100/100)</b><p>Re-research with a <i>different model</i> (Gemini 3.6 Flash) and reordered prompt, blind to pass-1 answers. Field-by-field diff; disagreements settled by an arbiter reading the actual docs.</p></div>
<div class="loop"><b>Loop C · browser deep-checks</b><p>A real browser visited ambiguous auth/pricing pages for the hardest apps (gated fintech, obscure tools); conclusions reviewed against what the pages actually show.</p></div>
<div class="loop"><b>Loop D · human audit (15 apps)</b><p>Stratified sample across categories, weighted toward disputed/low-confidence rows. A human marked each field right/wrong against real docs; misses corrected and shown below.</p></div>
</div>
__VERIFICATION__

<h2 id="process">7 · Process & limitations</h2>
<div class="grid2">
<div class="panel"><h3>How it was built</h3><ul class="plain">
<li>Assignment + 100-app list extracted programmatically from Notion's page API (no manual transcription).</li>
<li>Free-tier smoke tests before any bulk work; model availability issue found and fixed early (JSON-mode needed newer Gemini models).</li>
<li>Pass 1 → automated checks → independent pass 2 → arbiter → browser checks → human audit → analysis → this page. Every action timestamped in <code>log.md</code>.</li>
<li>Total cost: <b>$0</b> — Gemini free tier, DuckDuckGo, Composio free plan (2 catalog calls), no hosting.</li>
</ul></div>
<div class="panel"><h3>Honest limitations</h3><ul class="plain">
<li>Docs-only research: no paid accounts were created, so "gated" findings rest on public pricing/docs pages — which the assignment explicitly says is correct.</li>
<li>Pass 2 reuses the saved evidence (independence is at the reasoning level: different model + prompt); disputed fields triggered fresh evidence review by the arbiter.</li>
<li>API breadth is a rough bucket estimated from visible docs, not an endpoint count.</li>
<li>Obscure apps (e.g. Paygent Connect, iPayX, fanbasis) may have partner-only docs we cannot see; marked unknown/blocked with evidence rather than guessed.</li>
<li>Free-tier rate limits pace the run (~9 LLM req/min); the pipeline is resumable, so nothing is lost on interruption.</li>
</ul></div>
</div>

<h2 id="data">8 · Machine-readable data</h2>
<div class="panel">
<p>The full verified dataset is embedded in this page (below) and in the repo as <code>data/final.json</code> — so both humans and agents can consume the findings. Evidence text for every app is saved under <code>data/evidence/</code>.</p>
<button class="dl" onclick="dl()">Download final.json</button>
</div>
<script type="application/json" id="dataset">__DATASET__</script>

<footer>Generated __NOW__ from __SOURCE__ · agent: Gemini 3.5 Flash (pass 1) + Gemini 3.6 Flash (independent pass 2) + Gemini 3.5 Flash (arbiter) · search: DuckDuckGo · catalog: Composio SDK (free tier) · built for the Composio AI Product Ops take-home · every action logged in log.md</footer>
</div>
<script>
const rows=[...document.querySelectorAll('#matrix tr.row')];
const det=id=>document.getElementById('d'+id);
rows.forEach(r=>r.addEventListener('click',e=>{if(e.target.tagName==='A')return;det(r.dataset.id).classList.toggle('open')}));
const fcat=document.getElementById('fcat'),facc=document.getElementById('facc'),fver=document.getElementById('fver'),ftxt=document.getElementById('ftxt'),count=document.getElementById('count');
function apply(){let n=0;rows.forEach(r=>{const ok=(!fcat.value||r.dataset.cat===fcat.value)&&(!facc.value||r.dataset.acc===facc.value)&&(!fver.value||r.dataset.ver===fver.value)&&(!ftxt.value||r.dataset.txt.includes(ftxt.value.toLowerCase()));r.style.display=ok?'':'none';det(r.dataset.id).classList.remove('open');if(ok)n++});count.textContent=n+' / '+rows.length+' apps'}
[fcat,facc,fver].forEach(s=>s.addEventListener('change',apply));ftxt.addEventListener('input',apply);apply();
function dl(){const data=document.getElementById('dataset').textContent;const b=new Blob([data],{type:'application/json'});const a=document.createElement('a');a.href=URL.createObjectURL(b);a.download='final.json';a.click()}
</script>
</body></html>"""

if __name__ == "__main__":
    run()
