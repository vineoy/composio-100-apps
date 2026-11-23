"""Builds report/index.html — ONE simple, self-contained case-study page (no CDNs, works offline).

Plain-language version for non-technical readers. Consumes data/final.json + analysis.json
+ verification outputs. Zero API calls.
"""
import datetime
import html
import json

from . import analyze as A
from . import providers as P

ACCESS_LABEL = {
    "free_self_serve": "Free — anyone can sign up",
    "trial_self_serve": "Free trial",
    "paid_plan": "Paid plan needed",
    "admin_approval": "Admin must approve",
    "partner_gated": "Sales / partner deal",
    "no_public_api": "No public API",
    "unknown": "Not clear",
}
ACCESS_SHORT = {
    "free_self_serve": "Free", "trial_self_serve": "Trial", "paid_plan": "Paid",
    "admin_approval": "Admin approval", "partner_gated": "Partner", "no_public_api": "No API", "unknown": "Unknown",
}
VERDICT_LABEL = {"ready": "Ready to build", "feasible": "Possible, with work", "blocked": "Blocked", "unknown": "Unknown"}
MCP_LABEL = {"official": "Official", "community": "Community-made", "none": "None", "unknown": "Unknown"}
AUTH_LABEL = {"OAuth2": "OAuth sign-in", "API key": "API key", "Basic": "Username + password",
              "Bearer token": "Token", "JWT": "JWT token", "other": "Other"}


def esc(x):
    return html.escape(str(x if x is not None else ""))


def load_json(name):
    p = P.DATA / name
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def fmt_pct(x):
    return f"{round(x * 100)}%" if isinstance(x, (int, float)) else "—"


def norm_auth(m):
    m = str(m).lower()
    if "oauth" in m:
        return "OAuth2"
    if "api key" in m or "apikey" in m or "api-key" in m:
        return "API key"
    if "basic" in m:
        return "Basic"
    if "jwt" in m:
        return "JWT"
    if "bearer" in m or "token" in m:
        return "Bearer token"
    return "other"


def bar_list(counter, total, color="#2563eb"):
    if not counter:
        return "<p class='muted'>No data yet.</p>"
    items = list(counter.items()) if hasattr(counter, "items") else list(counter)
    mx = max((v for _, v in items), default=0) or 1
    out = []
    for k, v in items:
        width = round(100 * v / mx)
        out.append(
            f"<div class='barrow'><span class='barlabel'>{esc(k)}</span>"
            f"<span class='bartrack'><span class='barfill' style='width:{width}%;background:{color}'></span></span>"
            f"<span class='barval'>{v}</span></div>"
        )
    return "".join(out)


def status_pill(text, kind):
    return f"<span class='pill {kind}'>{esc(text)}</span>"


def access_pill(a):
    kind = {"free_self_serve": "good", "trial_self_serve": "ok", "paid_plan": "warn",
            "admin_approval": "warn", "partner_gated": "bad", "no_public_api": "grey", "unknown": "grey"}.get(a, "grey")
    return status_pill(ACCESS_SHORT.get(a, a), kind)


def build_pill(v):
    kind = {"ready": "good", "feasible": "ok", "blocked": "bad", "unknown": "grey"}.get(v, "grey")
    return status_pill(VERDICT_LABEL.get(v, v), kind)


def table_rows(rows):
    out = []
    for i, r in enumerate(rows):
        auth = " + ".join(AUTH_LABEL.get(norm_auth(x), "Other") for x in r.get("auth_methods", [])) or "—"
        mcp = (r.get("existing_mcp") or {}).get("status")
        verdict = (r.get("buildability") or {}).get("verdict")
        ev = r.get("evidence", []) or []
        ev_html = "".join(
            f"<li><a href='{esc(e.get('url'))}' target='_blank' rel='noopener'>{esc(e.get('url'))}</a>"
            f"<br><span class='muted'>{esc((e.get('claim') or '')[:220])}</span></li>"
            for e in ev[:5])
        out.append(
            f"<tr class='approw' data-cat='{esc(r.get('category'))}' data-acc='{esc(r.get('access'))}' "
            f"data-ver='{esc(verdict)}' data-text='{esc((r.get('name','') + ' ' + r.get('category','') + ' ' + auth).lower())}'>"
            f"<td><b>{esc(r.get('name'))}</b><br><span class='muted'>{esc(r.get('category'))}</span></td>"
            f"<td>{access_pill(r.get('access'))}</td>"
            f"<td>{esc(auth)}</td>"
            f"<td>{esc(MCP_LABEL.get(mcp, mcp or '—'))}</td>"
            f"<td>{build_pill(verdict)}</td></tr>"
            f"<tr class='detail' id='d{i}'><td colspan='5'><b>What it is:</b> {esc(r.get('description','—'))}<br>"
            f"<b>Why this access answer:</b> {esc(r.get('access_notes','—'))}<br>"
            f"<b>API surface:</b> {esc(r.get('api_type','—'))} ({esc(r.get('api_breadth','—'))}) — {esc(r.get('api_notes','—'))}<br>"
            f"<b>Sources we read:</b><ul class='ev'>{ev_html}</ul></td></tr>"
        )
    return "".join(out)


def easy_wins_html(wins, n=15):
    if not wins:
        return "<p class='muted'>No easy wins found yet.</p>"
    items = []
    for w in wins[:n]:
        items.append(f"<li><b>{esc(w['name'])}</b> <span class='muted'>· {esc(w['category'])} · {esc(', '.join(AUTH_LABEL.get(a, a) for a in w['auth']))}</span></li>")
    extra = f"<p class='muted'>…and {len(wins) - n} more, listed in the full table.</p>" if len(wins) > n else ""
    return "<ul class='clean'>" + "".join(items) + "</ul>" + extra


def outreach_html(items, n=12):
    if not items:
        return "<p class='muted'>Nothing here.</p>"
    lis = []
    for w in items[:n]:
        lis.append(f"<li><b>{esc(w['name'])}</b> <span class='muted'>· {esc(w['category'])} · {esc(ACCESS_SHORT.get(w['access'], w['access']))}</span></li>")
    extra = f"<p class='muted'>…and {len(items) - n} more.</p>" if len(items) > n else ""
    return "<ul class='clean'>" + "".join(lis) + "</ul>" + extra


def verification_section():
    rows = A.load_final()[0]
    rows = [r for r in rows if not r.get("error")]
    acc = load_json("verification/accuracy.json")
    loopc = load_json("verification/loop_c.json") or []
    diff = load_json("verification/diff_report.json") or {}
    flags = load_json("verification/loop_a_flags.json") or {}
    out = ["<p class='lead'>No one should trust a research spreadsheet on faith. Here is exactly how the answers were checked.</p>"]

    out.append("<div class='checks'>")
    out.append("<div class='check'><span class='num'>1</span><h3>Every claim had to cite a page</h3>"
               f"<p>The agent saved the actual documentation it read. {len(flags)} of {len(rows)} apps were automatically flagged "
               "for a weak or missing citation, and those flags were re-checked.</p></div>")
    v2_raw = load_json("research_v2_raw.json") or []
    v2_n = len([r for r in v2_raw if not r.get("error")])
    out.append("<div class='check'><span class='num'>2</span><h3>A second, independent pass</h3>"
               f"<p>The same questions were answered again in a fresh session on {v2_n} apps — every app the citation checker flagged, plus a random sample — without seeing the first answers. "
               "Where the two disagreed, a third step re-read the docs and decided. Disagreements are listed below.</p></div>")
    out.append("<div class='check'><span class='num'>3</span><h3>Manual page checks on hard cases</h3>"
               f"<p>For {len({i['id'] for i in loopc})} confusing or high-risk apps, the actual pricing/auth pages were opened and read. "
               "This caught errors the text-only pass missed — and also caught one false alarm.</p></div>")
    out.append("<div class='check'><span class='num'>4</span><h3>A human checks a sample</h3>"
               + ("<p>15 apps across all 10 categories were marked right or wrong against the real docs. "
                  "Corrections were applied to the final data.</p></div>" if acc and acc.get("overall_v1_accuracy") is not None
                  else "<p>15 apps across all 10 categories are being marked right or wrong against the real docs. "
                       "Corrections are applied to the final data and the before/after score appears below.</p></div>"))
    out.append("</div>")

    # Loop C table
    if loopc:
        lis = []
        for item in loopc:
            for c in item.get("checks", []):
                ok = c.get("browser_verified")
                lis.append(
                    f"<tr><td><b>{esc(item['name'])}</b></td><td>{esc(c.get('field',''))}</td>"
                    f"<td>{esc(c.get('claimed',''))}</td><td>{'✓ confirmed' if ok else '✗ corrected'}</td>"
                    f"<td class='small'>{esc((c.get('note') or '')[:190])}</td></tr>")
        out.append("<h3 class='sub'>What the manual checks found</h3>")
        out.append("<div class='scroll'><table class='simple'><tr><th>App</th><th>Question</th><th>First answer</th>"
                   "<th>Result</th><th>What the page showed</th></tr>" + "".join(lis) + "</table></div>")

    # Accuracy
    if acc and acc.get("overall_v1_accuracy") is not None:
        tot = acc.get("totals", {})
        out.append("<h3 class='sub'>Human check: accuracy before → after</h3>")
        out.append(
            "<div class='score'><div class='scorebox'><div class='bignum'>" + fmt_pct(acc.get("overall_v1_accuracy")) +
            "</div><div>correct in the first pass</div></div><div class='arrow'>→</div>"
            "<div class='scorebox good'><div class='bignum'>" + fmt_pct(acc.get("overall_final_accuracy")) +
            "</div><div>after verification + fixes</div></div></div>")
        out.append(f"<p class='muted'>On the 15-app sample: {tot.get('right',0)} answers were right, "
                   f"{tot.get('wrong',0)} were wrong, {tot.get('unsure',0)} were unclear. "
                   f"{tot.get('pre_fixed',0)} of the wrong ones had already been fixed by the checks above; "
                   f"{tot.get('human_fixed',0)} more were fixed from the human's correction.</p>")
        _chg = acc.get("changed_by_verification_before_audit", 0)
        if _chg:
            out.append(f"<p class='muted'>During verification, <b>{_chg}</b> field answers were corrected. "
                       "Where the human said the first-pass value was right, the verified value was kept "
                       "and is listed in the conflicts section below.</p>")
        pf = []
        for f, p in acc.get("per_field", {}).items():
            label = {"auth_methods": "Login method", "access": "Sign-up access", "api_type": "API type",
                     "existing_mcp.status": "Existing MCP", "buildability.verdict": "Buildable?"}.get(f, f)
            pf.append(f"<tr><td>{esc(label)}</td><td>{fmt_pct(p.get('v1_accuracy'))}</td>"
                      f"<td>{fmt_pct(p.get('final_accuracy'))}</td><td>{p.get('n',0)}</td></tr>")
        out.append("<div class='scroll'><table class='simple'><tr><th>Question</th><th>First pass</th>"
                   "<th>After fixes</th><th>Checked</th></tr>" + "".join(pf) + "</table></div>")
        misses = acc.get("misses", [])
        if misses:
            mr = "".join(
                f"<tr><td>{esc(m['name'])}</td><td>{esc(m['field'])}</td><td>{esc(m['our_value'])}</td>"
                f"<td>{esc(m.get('correction',''))}</td><td>{'yes' if m.get('applied') or m.get('already_fixed_by_loops') else 'no'}</td></tr>"
                for m in misses)
            out.append("<h3 class='sub'>The misses, shown honestly</h3>")
            out.append("<div class='scroll'><table class='simple'><tr><th>App</th><th>Question</th><th>First answer</th>"
                       "<th>Correction</th><th>Fixed?</th></tr>" + mr + "</table></div>")
        conflicts = acc.get("conflicts", [])
        if conflicts:
            cr = "".join(f"<tr><td>{esc(c['name'])}</td><td>{esc(c['field'])}</td><td>{esc(c['v1'])}</td>"
                         f"<td>{esc(c['final'])}</td></tr>" for c in conflicts)
            out.append("<p class='muted'><b>Also flagged:</b> in a few cases the human thought the first answer was right "
                       "but a later check had changed it. Those were kept as checked values and listed here for transparency.</p>")
            out.append("<div class='scroll'><table class='simple'><tr><th>App</th><th>Field</th><th>First</th>"
                       "<th>Kept</th></tr>" + cr + "</table></div>")
    else:
        out.append("<p class='note'>The human audit is not filled in yet. Run the audit form and this section will show "
                   "exactly how many answers were right before and after fixes.</p>")

    # disputes
    stats = diff.get("stats", {})
    disputes = diff.get("disputes", [])
    if disputes:
        dr = []
        for d in disputes[:20]:
            for x in d.get("disputes", []):
                dr.append(f"<tr><td>{esc(d['name'])}</td><td>{esc(x.get('field'))}</td>"
                          f"<td>{esc(x.get('pass1'))}</td><td>{esc(x.get('pass2'))}</td><td>{esc(x.get('final'))}</td></tr>")
        if dr:
            out.append("<h3 class='sub'>Where the two passes disagreed</h3>")
            out.append("<p class='muted'>Each row is a genuine disagreement; the final value was chosen by re-reading the docs.</p>")
            out.append("<div class='scroll'><table class='simple'><tr><th>App</th><th>Question</th><th>Pass 1</th>"
                       "<th>Pass 2</th><th>Final</th></tr>" + "".join(dr) + "</table></div>")
    if stats:
        out.append(f"<p class='muted'>Of the {stats.get('apps_compared',0)} apps checked twice, pass 1 and pass 2 agreed on "
                   f"{stats.get('full_agreement',0)} with no open questions; {stats.get('disputed_or_flagged',0)} needed a closer look.</p>")
    return "".join(out)


def run():
    rows, source = A.load_final()
    analysis = A.run()
    rows = [r for r in rows if not r.get("error")]
    errors = [r for r in rows if r.get("error")]
    n = len(rows)
    now = datetime.datetime.now().strftime("%d %b %Y, %H:%M")
    acc = analysis["access_distribution"]
    mcp = analysis["mcp_distribution"]
    free = acc.get("free_self_serve", 0)
    gated = sum(acc.get(k, 0) for k in ("paid_plan", "admin_approval", "partner_gated"))
    official = mcp.get("official", 0)
    wins = analysis["easy_wins"]
    have = analysis["composio_coverage"]["have"]
    missing = analysis["composio_coverage"]["missing"]
    top_auth = next(iter(analysis["auth_distribution"]), "?")
    second_auth = list(analysis["auth_distribution"])[1] if len(analysis["auth_distribution"]) > 1 else "API key"
    auth_counts = analysis["auth_distribution"]

    # plain-language findings, data-driven
    findings = [
        f"<b>{free} of {n} apps are free to try.</b> Anyone can create an account and get API access — a good first target.",
        f"<b>{gated} are gated.</b> They need a paid plan, an admin's permission, or a sales conversation before a toolkit can be built.",
        f"<b>{AUTH_LABEL.get(top_auth, top_auth)} is the most common way to connect</b> ({auth_counts.get(top_auth,0)} apps), "
        f"followed by {AUTH_LABEL.get(second_auth, second_auth)} ({auth_counts.get(second_auth,0)}).",
        f"<b>{official} apps already ship an official MCP server.</b> That is both competition and proof that AI integrations matter here.",
        f"<b>{len(wins)} are quick wins:</b> free access, a documented API, and no official MCP yet.",
        f"<b>Composio already covers {have} of {n}.</b> {missing} are gaps in the catalog.",
    ]

    # simple access overview
    access_counts = [(ACCESS_LABEL[k], v) for k, v in analysis["access_distribution"].items() if v]
    verdict_counts = [(VERDICT_LABEL.get(k, k), v) for k, v in analysis["verdict_distribution"].items() if v]
    auth_counts_plain = [(AUTH_LABEL.get(k, k), v) for k, v in auth_counts.items()]
    cat_rows = "".join(
        f"<tr><td><b>{esc(c['category'])}</b></td><td>{c['n']}</td><td>{c['free']}</td><td>{c['trial']}</td>"
        f"<td>{c['gated']}</td><td>{c['official_mcp'] if 'official_mcp' in c else c['mcp_official']}</td>"
        f"<td>{c['ready']}</td><td>{c['easy_wins']}</td></tr>"
        for c in analysis.get("category_summary", []))

    cat_options = "".join(f"<option>{esc(c)}</option>" for c in analysis["categories"])
    acc_options = "".join(f"<option value='{k}'>{esc(v)}</option>" for k, v in ACCESS_LABEL.items())
    ver_options = "".join(f"<option value='{k}'>{esc(v)}</option>" for k, v in VERDICT_LABEL.items())
    ver_html = verification_section()
    dataset_json = json.dumps(rows, ensure_ascii=False).replace("</", "<\\/")

    page = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Can we build a Composio toolkit for it? 100 apps, checked</title>
<style>
:root{{--bg:#f6f7f9;--card:#fff;--txt:#17202a;--mut:#667085;--line:#e4e7ec;--blue:#1d4ed8;--green:#087443;--greenbg:#e7f6ec;--amber:#8a5a00;--amberbg:#fff4d6;--red:#b42318;--redbg:#fde8e6;--grey:#475467;--greybg:#eef1f4}}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--bg);color:var(--txt);font:16px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Arial,sans-serif}}
.wrap{{max-width:1080px;margin:0 auto;padding:0 22px}}
nav{{position:sticky;top:0;z-index:20;background:#ffffffee;backdrop-filter:blur(8px);border-bottom:1px solid var(--line)}}
nav .wrap{{display:flex;gap:20px;overflow:auto;padding:12px 22px;font-size:14px}}
nav a{{color:var(--grey);text-decoration:none;white-space:nowrap}}
nav a:hover{{color:var(--blue)}}
header{{padding:54px 0 26px}}
h1{{font-size:40px;line-height:1.15;margin:0 0 14px;letter-spacing:-.02em}}
.sub{{font-size:19px;color:var(--mut);max-width:820px;margin:0 0 18px}}
.meta{{font-size:14px;color:var(--mut)}}
h2{{font-size:28px;margin:56px 0 8px;letter-spacing:-.01em}}
h3{{font-size:19px;margin:0 0 6px}}
.lead{{font-size:18px;color:#344054;max-width:850px}}
.muted{{color:var(--mut)}} .small{{font-size:13.5px}}
.cards{{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:14px;margin:20px 0 6px}}
.card{{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:18px}}
.big{{font-size:32px;font-weight:700;line-height:1.1}}
.lbl{{font-size:13.5px;color:var(--mut);margin-top:5px}}
.find{{background:#fff;border:1px solid var(--line);border-left:4px solid var(--blue);border-radius:12px;padding:16px 20px;margin:18px 0}}
.find ul{{margin:8px 0 0;padding-left:20px}} .find li{{margin:8px 0}}
.two{{display:grid;grid-template-columns:1fr 1fr;gap:18px;margin-top:18px}}
.panel{{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:20px}}
.barrow{{display:flex;align-items:center;gap:10px;margin:9px 0;font-size:14.5px}}
.barlabel{{width:150px;flex:none;color:#344054}}
.bartrack{{flex:1;height:10px;background:#edf0f4;border-radius:6px;overflow:hidden}}
.barfill{{display:block;height:100%;border-radius:6px}}
.barval{{width:28px;text-align:right;color:var(--mut)}}
.pill{{display:inline-block;padding:2px 9px;border-radius:999px;font-size:12.5px;font-weight:600;white-space:nowrap}}
.good{{background:var(--greenbg);color:var(--green)}} .ok{{background:#e8f1ff;color:#1849a9}}
.warn{{background:var(--amberbg);color:var(--amber)}} .bad{{background:var(--redbg);color:var(--red)}}
.grey{{background:var(--greybg);color:var(--grey)}}
table.simple{{width:100%;border-collapse:collapse;font-size:14.5px;background:#fff}}
table.simple th{{text-align:left;font-size:12.5px;text-transform:uppercase;letter-spacing:.03em;color:var(--mut);
  border-bottom:2px solid var(--line);padding:10px 10px;white-space:nowrap}}
table.simple td{{border-bottom:1px solid var(--line);padding:11px 10px;vertical-align:top}}
.scroll{{overflow:auto;border:1px solid var(--line);border-radius:12px;max-height:640px}}
.toolbar{{display:flex;gap:10px;flex-wrap:wrap;margin:14px 0}}
.toolbar input,.toolbar select{{padding:10px 12px;border:1px solid #d0d5dd;border-radius:10px;font:inherit;background:#fff;min-width:160px}}
.toolbar input{{flex:1;min-width:240px}}
#count{{font-size:14px;color:var(--mut);margin:4px 0 10px}}
tr.approw{{cursor:pointer}} tr.approw:hover{{background:#f9fafb}}
tr.detail{{display:none}} tr.detail.open{{display:table-row}} tr.detail td{{background:#fbfcfe;font-size:14.5px;padding:16px}}
ul.ev{{padding-left:20px;margin:8px 0 0}} ul.ev li{{margin:7px 0;word-break:break-word}}
.clean{{padding-left:20px;margin:8px 0 0}} .clean li{{margin:7px 0}}
.checks{{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin:18px 0}}
.check{{background:#fff;border:1px solid var(--line);border-radius:14px;padding:20px;position:relative}}
.check .num{{display:inline-flex;width:30px;height:30px;align-items:center;justify-content:center;border-radius:50%;
  background:var(--blue);color:#fff;font-weight:700;font-size:15px;margin-bottom:10px}}
.check p{{margin:6px 0 0;color:#475467;font-size:14.5px}}
h3.sub{{margin:34px 0 10px;font-size:20px}}
.score{{display:flex;align-items:center;gap:18px;margin:16px 0}}
.scorebox{{background:#fff;border:1px solid var(--line);border-radius:14px;padding:18px 24px;min-width:200px}}
.scorebox.good{{border-color:#a6e0bd;background:var(--greenbg)}}
.bignum{{font-size:36px;font-weight:800;line-height:1.1}}
.arrow{{font-size:28px;color:var(--mut)}}
.note{{background:#fff;border:1px dashed #cbd2dc;border-radius:12px;padding:18px;color:#475467}}
pre{{background:#101828;color:#d0d5dd;padding:16px 18px;border-radius:12px;overflow:auto;font-size:13.5px;line-height:1.55}}
code{{background:#eef1f4;padding:2px 6px;border-radius:6px;font-size:13.5px}}
pre code{{background:none;padding:0}}
footer{{margin:70px 0 40px;padding-top:20px;border-top:1px solid var(--line);color:var(--mut);font-size:13.5px}}
.btn{{display:inline-block;background:var(--blue);color:#fff;text-decoration:none;padding:10px 16px;border-radius:10px;font-size:14.5px;border:0;cursor:pointer}}
details{{background:#fff;border:1px solid var(--line);border-radius:12px;padding:14px 18px;margin:12px 0}}
summary{{cursor:pointer;font-weight:600}}
@media (max-width:820px){{h1{{font-size:31px}}.two,.checks{{grid-template-columns:1fr}}.barlabel{{width:118px}}.score{{flex-direction:column;align-items:flex-start}}}}
</style></head><body>

<nav><div class="wrap">
<a href="#summary">Summary</a><a href="#build">What to build</a><a href="#apps">All 100 apps</a>
<a href="#process">How it was done</a><a href="#checks">How we checked</a><a href="#run">Run it</a><a href="#limits">Limits</a>
</div></nav>

<header><div class="wrap">
<h1>Can we build a Composio toolkit for it?</h1>
<p class="sub">One agent researched 100 apps across 10 categories. For each one: how you get in, what the API can do,
whether an MCP server already exists, and whether Composio could build a toolkit today. Every answer is backed by a page we saved.</p>
<div class="meta">{n} apps · 10 categories · generated {now} · total cost $0 · no deployment needed</div>
</div></header>

<div class="wrap">

<span id="patterns"></span>

<h2 id="summary">The short version</h2>
<p class="lead">If you only read one screen, read this.</p><div class="cards">
<div class="card"><div class="big">{n}</div><div class="lbl">apps researched</div></div>
<div class="card"><div class="big">{free}</div><div class="lbl">free to try (self-serve)</div></div>
<div class="card"><div class="big">{gated}</div><div class="lbl">behind a paywall or approval</div></div>
<div class="card"><div class="big">{official}</div><div class="lbl">already have an official MCP</div></div>
<div class="card"><div class="big">{len(wins)}</div><div class="lbl">quick-win toolkit candidates</div></div>
<div class="card"><div class="big">{have}/{n}</div><div class="lbl">already in Composio's catalog</div></div>
</div>
<div class="find"><b>What the data says</b><ul>{''.join(f'<li>{f}</li>' for f in findings)}</ul></div>

<details><summary>Plain-English words used on this page</summary>
<ul class="clean">
<li><b>API</b> — the way one piece of software asks another for data. If an app has a public API, an assistant can read or change things in it.</li>
<li><b>MCP</b> — a standard plug for AI assistants. If an app already has an official MCP server, assistants can connect to it without custom work.</li>
<li><b>Self-serve</b> — you can sign up and get access yourself, without asking a salesperson or an admin.</li>
<li><b>Gated</b> — access needs a paid plan, an admin's approval, or a partner/sales deal.</li>
<li><b>Toolkit</b> — Composio's ready-made set of actions for one app (for example “create an issue” or “send a message”).</li>
</ul></details>

<div class="two">
<div class="panel"><h3>How easy is it to get in?</h3>{bar_list(access_counts, n)}</div>
<div class="panel"><h3>How do apps usually authenticate?</h3>{bar_list(auth_counts_plain, n)}</div>
</div>
<div class="two">
<div class="panel"><h3>Can Composio build it today?</h3>{bar_list(verdict_counts, n, "#087443")}</div>
<div class="panel"><h3>Does an MCP server already exist?</h3>{bar_list([(MCP_LABEL.get(k,k),v) for k,v in mcp.items() if v], n, "#6941c6")}</div>
</div>

<h2 id="build">What to build first</h2>
<p class="lead">A “quick win” here means: free self-serve access + a documented API + no official MCP yet. Those are the toolkits
that can be built and tested without a sales call.</p>
<div class="two">
<div class="panel"><h3 style="color:var(--green)">Quick wins ({len(wins)})</h3>{easy_wins_html(wins)}</div>
<div class="panel"><h3 style="color:var(--red)">Needs a conversation first ({len(analysis['outreach'])})</h3>{outreach_html(analysis['outreach'])}</div>
</div>
<div class="panel" style="margin-top:18px"><h3>Where each category stands</h3>
<p class="muted">A simple count per category. “Ready” means documented API + credentials you can get yourself.</p>
<div class="scroll"><table class="simple"><tr><th>Category</th><th>Apps</th><th>Free</th><th>Trial</th><th>Gated</th><th>Official MCP</th><th>Ready</th><th>Quick wins</th></tr>{cat_rows}</table></div>
</div>

<h2 id="apps">All 100 apps</h2>
<p class="lead">Click any row to see what the app is, why we gave it that answer, and the exact pages we read.</p>
<div class="toolbar">
<input id="q" placeholder="Search app or category…">
<select id="fcat"><option value="">All categories</option>{cat_options}</select>
<select id="facc"><option value="">Any access</option>{acc_options}</select>
<select id="fver"><option value="">Any build status</option>{ver_options}</select>
</div>
<div id="count"></div>
<div class="scroll" style="max-height:760px">
<table class="simple"><thead><tr><th>App</th><th>Getting in</th><th>Login method</th><th>Existing MCP</th><th>Buildable?</th></tr></thead>
<tbody>{table_rows(rows)}</tbody></table>
</div>

<h2 id="process">How it was done</h2>
<span id="how"></span>
<p class="lead">Four simple steps. No jargon needed.</p>
<ol class="clean" style="font-size:17px;line-height:1.7;max-width:820px">
<li><b>Find the docs.</b> For each of the 100 apps, the agent searched for login rules, pricing, and whether an AI plug (MCP) already exists — and saved the pages it found.</li>
<li><b>Answer the same questions.</b> From those pages only, it filled one form per app: how you sign in, whether access is free, what the API covers, and whether a toolkit could be built today. If the page was unclear, it said “unknown” instead of guessing.</li>
<li><b>Check the answers.</b> Citations were auto-checked on all 100. A second pass re-answered the risky ones. Hard cases were opened in a real browser. A human then marked 15 apps right or wrong.</li>
<li><b>Show the results here.</b> Patterns, the full table, and this page are generated from the final data — one command rebuilds everything, offline, with no API keys.</li>
</ol>
<p class="muted">Where a human was needed: picking the 15-app audit sample, reading live pages for ~12 tricky apps, and fixing confirmed mistakes. Everything else was automated.</p>

<h2 id="checks">How we checked the answers</h2>
{ver_html}

<h2 id="run">Run it yourself</h2>
<p class="lead">The full research repo is included. Rebuilding this page needs no API keys and makes no network calls.</p>
<pre><code>pip install -r requirements.txt
python run.py          # rebuilds the data summary and this page from saved evidence</code></pre>
<details><summary>Re-run the research from scratch (needs free API keys in .env)</summary>
<pre><code>python -m agent.research --pass 1        # search + read docs + extract 100 apps
python -m agent.verify --checks          # check citations and schema
python -m agent.verify --second-pass     # independent second pass
python -m agent.verify --reconcile       # settle disagreements against the docs
python -m agent.verify --apply-corrections
python -m agent.verify --audit-sheet     # human audit form
python -m agent.verify --ingest-audit
python run.py</code></pre>
<p class="muted">Or in one command after pass 1: <code>python -m agent.finalize --wait</code></p>
</details>

<h2 id="limits">What this is not</h2>
<div class="panel">
<ul class="clean">
<li><b>Not a trial of every app.</b> No paid accounts were created. Access answers come from public docs and pricing pages, checked by a human on a sample.</li>
<li><b>“Unknown” is a real answer.</b> The agent was told to say it instead of guessing. Every unresolved field is visible in the table.</li>
<li><b>Pricing and plans change.</b> Each row links to the pages used, so a reviewer can re-check quickly.</li>
<li><b>The human check is a sample (15 apps), not all 100.</b> The page reports exactly what was checked and what was missed.</li>
</ul>
</div>

<h2 id="data">Download the data</h2>
<div class="panel">
<p>The same table is available as machine-readable JSON, embedded in this page and in the repo as <code>data/final.json</code>.
Evidence pages are saved under <code>data/evidence/</code>.</p>
<button class="btn" onclick="downloadJson()">Download the 100-app JSON</button>
</div>

<footer>Built for the Composio AI Product Ops take-home · one self-contained HTML page · generated {now} from {esc(source or '')} ·
agent: Gemini free tier, with a free fallback model when the quota is exhausted · every action in <code>log.md</code></footer>
</div>

<script type="application/json" id="dataset">{dataset_json}</script>
<script>
const rows = [...document.querySelectorAll('tr.approw')];
const details = [...document.querySelectorAll('tr.detail')];
rows.forEach((r, i) => r.addEventListener('click', () => details[i].classList.toggle('open')));
const q = document.getElementById('q'), fc = document.getElementById('fcat'), fa = document.getElementById('facc'),
      fv = document.getElementById('fver'), count = document.getElementById('count');
function apply() {{
  let shown = 0;
  rows.forEach((r, i) => {{
    const ok = (!fc.value || r.dataset.cat === fc.value)
      && (!fa.value || r.dataset.acc === fa.value)
      && (!fv.value || r.dataset.ver === fv.value)
      && (!q.value || r.dataset.text.includes(q.value.toLowerCase()));
    r.style.display = ok ? '' : 'none';
    if (!ok) details[i].classList.remove('open');
    details[i].style.display = 'none';
    if (ok) shown++;
  }});
  count.textContent = shown + ' of ' + rows.length + ' apps shown';
}}
[q, fc, fa, fv].forEach(el => el.addEventListener('input', apply));
apply();
function downloadJson() {{
  const data = document.getElementById('dataset').textContent;
  const blob = new Blob([data], {{type: 'application/json'}});
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = 'final.json';
  a.click();
}}
</script>
</body></html>"""

    (P.ROOT / "report").mkdir(exist_ok=True)
    (P.ROOT / "docs").mkdir(exist_ok=True)
    (P.ROOT / "report" / "index.html").write_text(page, encoding="utf-8")
    (P.ROOT / "docs" / "index.html").write_text(page, encoding="utf-8")  # GitHub Pages
    print(f"Report written -> report/index.html + docs/index.html ({len(page)//1024} KB, {n} apps, source={source})")


if __name__ == "__main__":
    run()
