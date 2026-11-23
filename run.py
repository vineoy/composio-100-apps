"""One-command rebuild of the case study from saved data. ZERO API calls, zero cost.

    python run.py

Regenerates data/analysis.json and report/index.html from the best available
dataset (final.json > research_v2_raw.json > research_v1.json).
"""
from agent import analyze, report

if __name__ == "__main__":
    analyze.run()
    report.run()
    print("\nOpen report/index.html in a browser. Done.")
