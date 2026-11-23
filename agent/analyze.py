"""Pattern analysis over the verified dataset -> data/analysis.json (feeds the report)."""
import json, re, collections
from . import providers as P


def load_final():
    for name in ("final.json", "research_v2_raw.json", "research_v1.json"):
        p = P.DATA / name
        if p.exists():
            rows = json.loads(p.read_text(encoding="utf-8"))
            if rows:
                return rows, name
    return [], None


def norm_auth(m):
    m = str(m).lower()
    if "oauth" in m: return "OAuth2"
    if "api key" in m or "apikey" in m or "api-key" in m: return "API key"
    if "basic" in m: return "Basic"
    if "jwt" in m: return "JWT"
    if "bearer" in m or "token" in m: return "Bearer token"
    return "other"


def blocker_bucket(text):
    t = (text or "").lower()
    if not t: return None
    if any(k in t for k in ("no public api", "no api", "no documented api", "not public", "no rest")): return "No public API"
    if any(k in t for k in ("partner", "contact sales", "sales team", "partnership", "enterprise agreement")): return "Partner / sales gate"
    if any(k in t for k in ("paid", "subscription", "pricing", "paywall", "premium plan")): return "Paid plan required"
    if any(k in t for k in ("admin", "approval", "app review", "allowlist", "whitelist", "permission", "scope")): return "Admin / app-review approval"
    if any(k in t for k in ("oauth", "auth complex", "token refresh", "mandate", "2fa", "mfa")): return "Complex auth flow"
    if any(k in t for k in ("rate limit", "quota", "throttl")): return "Rate limits / quotas"
    if any(k in t for k in ("self-host", "self host", "open-source", "open source", "cli", "local")): return "Self-hosted / local tool"
    return "Other"


def run():
    rows, source = load_final()
    rows = [r for r in rows if not r.get("error")]
    n = len(rows)
    auth = collections.Counter()
    for r in rows:
        for m in set(norm_auth(x) for x in r.get("auth_methods", [])):
            auth[m] += 1
    access = collections.Counter(r.get("access", "unknown") for r in rows)
    api_type = collections.Counter(r.get("api_type", "unknown") for r in rows)
    breadth = collections.Counter(r.get("api_breadth", "unknown") for r in rows)
    mcp = collections.Counter((r.get("existing_mcp") or {}).get("status", "unknown") for r in rows)
    verdict = collections.Counter((r.get("buildability") or {}).get("verdict", "unknown") for r in rows)
    conf = collections.Counter(r.get("confidence", "unknown") for r in rows)

    cats = sorted(set(r["category"] for r in rows))
    access_order = ["free_self_serve", "trial_self_serve", "paid_plan", "admin_approval", "partner_gated", "no_public_api", "unknown"]
    heatmap = {}
    for c in cats:
        cr = [r for r in rows if r["category"] == c]
        heatmap[c] = {a: sum(1 for r in cr if r.get("access") == a) for a in access_order}

    blockers = collections.Counter()
    for r in rows:
        b = (r.get("buildability") or {}).get("blocker", "")
        if (r.get("buildability") or {}).get("verdict") in ("blocked", "feasible") and b:
            bb = blocker_bucket(b)
            if bb: blockers[bb] += 1

    self_serve = {"free_self_serve", "trial_self_serve"}
    easy_wins = [r for r in rows if r.get("access") in self_serve
                 and r.get("api_type") in ("REST", "GraphQL", "both")
                 and (r.get("buildability") or {}).get("verdict") in ("ready", "feasible")
                 and (r.get("existing_mcp") or {}).get("status") != "official"]
    composio_have = [r for r in rows if (r.get("composio_toolkit") or {}).get("exists")]
    composio_missing = [r for r in rows if not (r.get("composio_toolkit") or {}).get("exists")]
    cat_summary = []
    for c in cats:
        cr = [r for r in rows if r["category"] == c]
        auth_c = collections.Counter()
        for r in cr:
            for m in set(norm_auth(x) for x in r.get("auth_methods", [])):
                auth_c[m] += 1
        cat_summary.append({
            "category": c, "n": len(cr),
            "free": sum(1 for r in cr if r.get("access") == "free_self_serve"),
            "trial": sum(1 for r in cr if r.get("access") == "trial_self_serve"),
            "gated": sum(1 for r in cr if r.get("access") in ("paid_plan", "admin_approval", "partner_gated")),
            "no_api": sum(1 for r in cr if r.get("access") == "no_public_api"),
            "mcp_official": sum(1 for r in cr if (r.get("existing_mcp") or {}).get("status") == "official"),
            "ready": sum(1 for r in cr if (r.get("buildability") or {}).get("verdict") == "ready"),
            "easy_wins": sum(1 for r in cr if r in easy_wins),
            "top_auth": auth_c.most_common(1)[0][0] if auth_c else "?",
        })
    outreach = [r for r in rows if r.get("access") in ("partner_gated", "admin_approval")
                or (r.get("buildability") or {}).get("verdict") == "blocked"]
    no_api = [r for r in rows if r.get("access") == "no_public_api" or r.get("api_type") == "none"]

    def slim(r):
        return {"id": r["id"], "name": r["name"], "category": r["category"],
                "access": r.get("access"), "verdict": (r.get("buildability") or {}).get("verdict"),
                "auth": sorted(set(norm_auth(x) for x in r.get("auth_methods", []))),
                "mcp": (r.get("existing_mcp") or {}).get("status"),
                "composio": (r.get("composio_toolkit") or {}).get("exists", False)}

    top_auth = auth.most_common(1)[0] if auth else ("?", 0)
    auth_two = auth.most_common(2)
    second_auth = auth_two[1][0] if len(auth_two) > 1 else "no other method"
    gated_total = sum(access[a] for a in ("paid_plan", "admin_approval", "partner_gated"))
    headlines = [
        f"{top_auth[0]} dominates: {top_auth[1]} of {n} apps ({round(100*top_auth[1]/max(n,1))}%) support it; {second_auth} is next.",
        f"{access['free_self_serve']} of {n} apps are free self-serve for developers; {gated_total} are gated (paid plan, admin approval, or partner/sales).",
        f"{mcp['official']} apps already ship an official MCP server, {mcp['community']} have community MCP - the rest is whitespace for agent toolkits.",
        f"Most common blocker: {blockers.most_common(1)[0][0] if blockers else 'n/a'} ({blockers.most_common(1)[0][1] if blockers else 0} apps).",
        f"{len(easy_wins)} easy wins: self-serve + documented API + no official MCP yet - build these toolkits first.",
        f"{len(outreach)} apps need outreach or are blocked - business development, not engineering.",
        f"Composio already ships toolkits for {len(composio_have)} of {n}; {len(composio_missing)} are catalog whitespace.",
    ]
    analysis = {
        "source": source, "n": n, "categories": cats,
        "auth_distribution": dict(auth.most_common()),
        "access_distribution": {a: access[a] for a in access_order},
        "access_heatmap": heatmap, "access_order": access_order,
        "api_type_distribution": dict(api_type.most_common()),
        "breadth_distribution": dict(breadth.most_common()),
        "mcp_distribution": dict(mcp.most_common()),
        "verdict_distribution": dict(verdict.most_common()),
        "confidence_distribution": dict(conf.most_common()),
        "blocker_buckets": dict(blockers.most_common()),
        "category_summary": cat_summary,
        "composio_coverage": {"have": len(composio_have), "missing": len(composio_missing),
                               "missing_apps": [slim(r) for r in composio_missing]},
        "easy_wins": [slim(r) for r in sorted(easy_wins, key=lambda r: r["id"])],
        "outreach": [slim(r) for r in sorted(outreach, key=lambda r: r["id"])],
        "no_api": [slim(r) for r in no_api],
        "headlines": headlines,
    }
    (P.DATA / "analysis.json").write_text(json.dumps(analysis, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"Analysis over {n} rows ({source}) -> data/analysis.json")
    for h in headlines:
        print(" -", h)
    return analysis


if __name__ == "__main__":
    run()
