"""Post-research orchestrator (free, no human input needed until the audit).

    python -m agent.finalize            # run now (assumes pass 1 is complete)
    python -m agent.finalize --wait     # wait for pass 1 to reach 100, retry errors, then run

Steps: wait/pass-1 health -> retry errored apps -> Loop A checks -> Loop B second pass
       (flagged + cross-category sample) -> reconcile (arbiter) -> apply verified
       corrections -> audit sheet -> report.
Every step is checkpointed; re-running skips finished work.
"""
import datetime
import json
import random
import sys
import time

from agent import providers as P
from agent import research as R
from agent import verify as V

V1 = P.DATA / "research_v1.json"
V2 = P.DATA / "research_v2_raw.json"


def log(msg):
    print(f"[{datetime.datetime.now():%H:%M:%S}] {msg}", flush=True)


def load_rows(path):
    if not path.exists():
        return []
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []


def wait_for_pass1(timeout_min=50):
    start = time.time()
    while True:
        rows = load_rows(V1)
        if len(rows) >= 100:
            errs = [r["id"] for r in rows if r.get("error")]
            if not errs:
                log(f"pass 1 complete: {len(rows)}/100 clean rows")
                return
            log(f"pass 1 has {len(errs)} errored rows -> retrying {errs}")
            R.run(1, only=errs)
            continue
        if time.time() - start > timeout_min * 60:
            log(f"timeout waiting for pass 1 ({len(rows)}/100). Run again later.")
            sys.exit(2)
        log(f"waiting for pass 1: {len(rows)}/100 rows")
        time.sleep(30)


def loop_b_sample(flags, rows, extra_per_cat=1, seed=42):
    """All hard-flagged apps + one random non-flagged app per category (free-tier sample)."""
    hard = {int(i) for i, fl in flags.items()
            if any(not str(x).startswith("access_soft") for x in fl)}
    soft = {int(i) for i in flags} - hard
    chosen = set(hard)
    by_cat = {}
    for r in rows:
        by_cat.setdefault(r.get("category", "?"), []).append(r["id"])
    rng = random.Random(seed)
    for cat, ids in sorted(by_cat.items()):
        pool = [i for i in ids if i not in chosen]
        if not pool:
            continue
        # prefer soft-flagged, then clean
        soft_pool = [i for i in pool if i in soft] or pool
        pick = rng.sample(soft_pool, min(extra_per_cat, len(soft_pool)))
        chosen.update(pick)
    return sorted(chosen)


def main():
    if "--wait" in sys.argv:
        wait_for_pass1()
    rows = load_rows(V1)
    errs = [r["id"] for r in rows if r.get("error")]
    if errs:
        log(f"retrying errored rows {errs}")
        R.run(1, only=errs)
        rows = load_rows(V1)

    log("Loop A: automated evidence checks on all rows")
    flags = V.checks()

    sample = loop_b_sample(flags, rows)
    log(f"Loop B: independent second pass on {len(sample)} apps "
        f"(hard-flagged + 1/category sample): {sample}")
    V.second_pass(only=sample)

    log("Reconciling pass 1 vs pass 2 + arbiter")
    V.reconcile()

    log("Applying browser/human-verified corrections")
    V.apply_corrections()

    log("Generating human audit sheet (15-app stratified sample)")
    V.audit_sheet()

    log("Regenerating analysis + report")
    import agent.analyze as A
    import agent.report as Rep
    A.run()
    Rep.run()

    log("DONE. Next: human fills data/verification/audit.html, then "
        "`python -m agent.verify --ingest-audit && python run.py`")


if __name__ == "__main__":
    main()
