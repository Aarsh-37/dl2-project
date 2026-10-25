"""Evaluate deterministic ATS + gap scoring against the human-labeled eval set.

The eval set (data/eval/eval_set.csv) carries human ATS scores, verdicts, and
expected-missing skills per resume/JD pair. This harness scores each pair with
the REAL deterministic pipeline (no LLM) and reports how close we are:

    ATS MAE / max error, verdict agreement, missing-skill P/R/F1.

Usage (from backend/):
    python -m scripts.eval_ats              # honor CAREERPILOT_SEMANTIC
    python -m scripts.eval_ats --semantic   # force embeddings on
    python -m scripts.eval_ats --no-semantic
    python -m scripts.eval_ats --compare    # run both, side by side
    python -m scripts.eval_ats --json
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from pathlib import Path

_BACKEND = Path(__file__).resolve().parents[1]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from app.core.config import EVAL_CSV, REPO_ROOT  # noqa: E402
from app.core.pipeline import run_core_pipeline  # noqa: E402


def _read(path: str) -> str:
    p = Path(path)
    if not p.is_absolute():
        p = REPO_ROOT / p
    return p.read_text(encoding="utf-8")


def load_pairs() -> list[dict]:
    """Rows with a resume, JD, and human score. Placeholder rows are skipped."""
    pairs: list[dict] = []
    with open(EVAL_CSV, encoding="utf-8-sig", newline="") as fh:
        for row in csv.DictReader(fh):
            refs = (row.get("resume_ref") or "").strip()
            jd = (row.get("jd_ref") or "").strip()
            human = (row.get("human_ats") or "").strip()
            if not (refs and jd and human):
                continue
            expected = {
                s.strip() for s in (row.get("expected_missing") or "").split("|") if s.strip()
            }
            pairs.append({
                "pair_id": (row.get("pair_id") or "").strip(),
                "resume_text": _read(refs),
                "jd_text": _read(jd),
                "human_ats": float(human),
                "human_verdict": (row.get("human_verdict") or "").strip().lower(),
                "expected_missing": expected,
            })
    return pairs


def _score(pair: dict) -> dict:
    res = run_core_pipeline(
        resume_text=pair["resume_text"], jd_text=pair["jd_text"], hours_per_day=3)
    ats = res["ats_result"]
    missing = {m["skill"].strip().lower() for m in res["skill_gap"]["missing"]}
    return {
        "pair_id": pair["pair_id"],
        "pred_ats": ats["score"],
        "human_ats": pair["human_ats"],
        "delta": round(ats["score"] - pair["human_ats"], 1),
        "pred_verdict": ats["verdict"].lower(),
        "human_verdict": pair["human_verdict"],
        "verdict_ok": ats["verdict"].lower() == pair["human_verdict"],
        "pred_missing": missing,
        "expected_missing": {s.lower() for s in pair["expected_missing"]},
        "semantic": ats["breakdown"].get("semantic"),
    }


def evaluate(*, semantic: bool) -> dict:
    """Run the whole eval set. Temporarily forces the semantic flag, then restores."""
    prev = os.environ.get("CAREERPILOT_SEMANTIC")
    os.environ["CAREERPILOT_SEMANTIC"] = "1" if semantic else "0"
    try:
        pairs = load_pairs()
        rows = [_score(p) for p in pairs]
    finally:
        if prev is None:
            os.environ.pop("CAREERPILOT_SEMANTIC", None)
        else:
            os.environ["CAREERPILOT_SEMANTIC"] = prev

    n = len(rows)
    abs_err = [abs(r["delta"]) for r in rows]
    tp = fp = fn = 0
    for r in rows:
        tp += len(r["pred_missing"] & r["expected_missing"])
        fp += len(r["pred_missing"] - r["expected_missing"])
        fn += len(r["expected_missing"] - r["pred_missing"])
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    for r in rows:  # sets are not JSON-serialisable
        r["pred_missing"] = sorted(r["pred_missing"])
        r["expected_missing"] = sorted(r["expected_missing"])
    return {
        "semantic": semantic,
        "n": n,
        "ats": {
            "mae": round(sum(abs_err) / n, 2) if n else None,
            "max_abs_error": round(max(abs_err), 1) if n else None,
        },
        "verdict": {
            "agree": sum(1 for r in rows if r["verdict_ok"]),
            "agreement_pct": round(100 * sum(1 for r in rows if r["verdict_ok"]) / n, 1) if n else None,
        },
        "missing": {
            "precision": round(precision, 3),
            "recall": round(recall, 3),
            "f1": round(f1, 3),
            "tp": tp, "fp": fp, "fn": fn,
        },
        "rows": rows,
    }


def _print(report: dict) -> None:
    mode = "semantic ON" if report["semantic"] else "semantic OFF"
    print(f"\n=== ATS eval — {mode} | {report['n']} pairs ===")
    print(f"{'pair':8s} {'pred':>6s} {'human':>6s} {'delta':>7s}  {'verdict':>8s}  missing(pred/exp)")
    for r in report["rows"]:
        exp = ",".join(sorted(r["expected_missing"])) or "-"
        pred = ",".join(sorted(r["pred_missing"])) or "-"
        print(f"{r['pair_id']:8s} {r['pred_ats']:6.1f} {r['human_ats']:6.1f} "
              f"{r['delta']:+7.1f}  {'OK' if r['verdict_ok'] else 'MISS':>8s}  "
              f"[{pred}] vs [{exp}]")
    a, v, m = report["ats"], report["verdict"], report["missing"]
    print(f"\nATS       MAE={a['mae']}  max|err|={a['max_abs_error']}")
    print(f"Verdict   {v['agree']}/{report['n']} agree ({v['agreement_pct']}%)")
    print(f"Missing   P={m['precision']}  R={m['recall']}  F1={m['f1']}  "
          f"(tp={m['tp']} fp={m['fp']} fn={m['fn']})")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--semantic", action="store_true", help="force embeddings on")
    ap.add_argument("--no-semantic", action="store_true", help="force embeddings off")
    ap.add_argument("--compare", action="store_true", help="run both modes")
    ap.add_argument("--json", action="store_true", help="emit JSON")
    args = ap.parse_args()

    if args.compare:
        reports = {"off": evaluate(semantic=False), "on": evaluate(semantic=True)}
        if args.json:
            print(json.dumps(reports, indent=2))
        else:
            for r in reports.values():
                _print(r)
        return 0

    semantic = os.getenv("CAREERPILOT_SEMANTIC") == "1"
    if args.semantic:
        semantic = True
    if args.no_semantic:
        semantic = False
    report = evaluate(semantic=semantic)
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        _print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
