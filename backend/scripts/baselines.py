"""Baseline comparison for the ATS / gap evaluation.

The question a reviewer always asks is "compared with what?". This script
answers it on the same three human-labelled pairs as `scripts.eval_ats`:

    trivial regression baselines   -> keyword-only score, unweighted mean of
                                      components, leave-one-out constant
    naive detection baselines      -> "predict nothing" / "predict every
                                      required skill" for missing-skill P/R/F1
    majority-class baseline        -> "always Moderate" for verdict agreement
    LLM zero-shot baseline         -> Groq gpt-oss-20b asked for a 0-100 score
    full CareerPilot system        -> the real deterministic ATS engine

Usage (from backend/):
    python -m scripts.baselines                 # deterministic baselines only
    python -m scripts.baselines --semantic      # force embeddings on
    python -m scripts.baselines --no-semantic
    python -m scripts.baselines --llm           # +3 Groq zero-shot calls
    python -m scripts.baselines --json
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

_BACKEND = Path(__file__).resolve().parents[1]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from app.core.pipeline import run_core_pipeline  # noqa: E402
from scripts.eval_ats import load_pairs  # noqa: E402

COMPONENTS = ("keyword", "skill", "experience", "education", "project_relevance")


def _metrics(preds: list[float], humans: list[float]) -> dict:
    deltas = [p - h for p, h in zip(preds, humans)]
    n = len(deltas) or 1
    return {
        "mae": round(sum(abs(d) for d in deltas) / n, 2),
        "rmse": round((sum(d * d for d in deltas) / n) ** 0.5, 2),
        "bias": round(sum(deltas) / n, 2),
        "max_abs_error": round(max(abs(d) for d in deltas), 1) if deltas else None,
    }


def _prf(tp: int, fp: int, fn: int) -> dict:
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    return {
        "precision": round(precision, 3),
        "recall": round(recall, 3),
        "f1": round(f1, 3),
        "tp": tp, "fp": fp, "fn": fn,
    }


def _llm_score(resume: str, jd: str) -> float | None:
    """One zero-shot Groq call: ask for a JSON ATS score, parse the integer."""
    from app.core.llm import get_llm

    prompt = (
        "You are an ATS (applicant tracking system) scorer.\n"
        "Read the resume and the job description and rate how well the resume "
        "matches the job on a 0-100 scale.\n"
        "Return ONLY JSON: {\"ats_score\": <integer 0-100>}\n\n"
        f"<RESUME>\n{resume[:6000]}\n</RESUME>\n\n"
        f"<JD>\n{jd[:4000]}\n</JD>\n"
    )
    try:
        text = get_llm("jd", temperature=0.0).invoke(prompt)
    except Exception as exc:  # noqa: BLE001 - baseline must never crash the eval
        print(f"  llm baseline failed: {exc}")
        return None
    match = re.search(r'"?ats_score"?\s*[:=]\s*(\d{1,3})', text)
    if not match:
        match = re.search(r"\b(\d{1,3})\b", text)
    if not match:
        return None
    return float(min(100, int(match.group(1))))


def evaluate(*, semantic: bool, use_llm: bool) -> dict:
    prev = os.environ.get("CAREERPILOT_SEMANTIC")
    os.environ["CAREERPILOT_SEMANTIC"] = "1" if semantic else "0"
    try:
        pairs = load_pairs()
        rows: list[dict] = []
        for pair in pairs:
            res = run_core_pipeline(
                resume_text=pair["resume_text"], jd_text=pair["jd_text"], hours_per_day=3)
            ats = res["ats_result"]
            breakdown = ats["breakdown"]
            comps = [float(breakdown[c]) for c in COMPONENTS if breakdown.get(c) is not None]
            required = {s.strip().lower() for s in res.get("_required", [])}
            rows.append({
                "pair_id": pair["pair_id"],
                "human_ats": pair["human_ats"],
                "human_verdict": pair["human_verdict"],
                "pred_verdict": ats["verdict"].lower(),
                "expected_missing": {s.lower() for s in pair["expected_missing"]},
                "required": required,
                "preferred": {s.strip().lower() for s in res.get("_preferred", [])},
                "system": float(ats["score"]),
                "keyword_only": float(breakdown["keyword"]),
                "unweighted": round(sum(comps) / len(comps), 1) if comps else 0.0,
                "pred_missing": {m["skill"].strip().lower() for m in res["skill_gap"]["missing"]},
            })
            if use_llm:
                rows[-1]["llm_zero_shot"] = _llm_score(pair["resume_text"], pair["jd_text"])
    finally:
        if prev is None:
            os.environ.pop("CAREERPILOT_SEMANTIC", None)
        else:
            os.environ["CAREERPILOT_SEMANTIC"] = prev

    humans = [r["human_ats"] for r in rows]
    n = len(rows)

    # Leave-one-out constant predictor (the "predict the train mean" baseline).
    loo = [
        round(sum(h for j, h in enumerate(humans) if j != i) / max(1, n - 1), 1)
        for i in range(n)
    ]

    methods = {
        "constant (LOO mean)": _metrics(loo, humans),
        "keyword-only": _metrics([r["keyword_only"] for r in rows], humans),
        "unweighted mean": _metrics([r["unweighted"] for r in rows], humans),
        "full system": _metrics([r["system"] for r in rows], humans),
    }
    if use_llm:
        llm_preds = [r.get("llm_zero_shot") for r in rows]
        if all(p is not None for p in llm_preds):
            methods["llm zero-shot (gpt-oss-20b)"] = _metrics(
                [float(p) for p in llm_preds], humans)
        else:
            methods["llm zero-shot (gpt-oss-20b)"] = {"error": "incomplete"}

    # --- missing-skill baselines ---
    exp_total = sum(len(r["expected_missing"]) for r in rows)

    def _count(pred_fn) -> dict:
        tp = fp = 0
        for r in rows:
            pred = pred_fn(r)
            tp += len(pred & r["expected_missing"])
            fp += len(pred - r["expected_missing"])
        return _prf(tp, fp, exp_total - tp)

    missing = {
        "predict-nothing": _prf(0, 0, exp_total),
        "predict-all-required": _count(lambda r: r["required"]),
        "predict-all-preferred": _count(lambda r: r["preferred"]),
        "predict-all-JD-skills": _count(lambda r: r["required"] | r["preferred"]),
        "full system": _count(lambda r: r["pred_missing"]),
    }

    # --- verdict baseline ---
    counts: dict[str, int] = {}
    for r in rows:
        counts[r["human_verdict"]] = counts.get(r["human_verdict"], 0) + 1
    majority = max(counts, key=counts.get) if counts else ""
    majority_hits = sum(1 for r in rows if r["human_verdict"] == majority)
    system_hits = sum(1 for r in rows if r["human_verdict"] == r["pred_verdict"])
    verdict = {
        "majority_class": majority,
        "majority_agreement": f"{majority_hits}/{n}",
        "system_agreement": f"{system_hits}/{n}",
    }

    return {
        "semantic": semantic,
        "n": n,
        "methods": methods,
        "missing": missing,
        "verdict": verdict,
        "rows": rows,
        "loo_preds": loo,
    }


def _print(report: dict) -> None:
    print(f"\n=== Baselines — {report['n']} human-labelled pairs "
          f"(semantic {'ON' if report['semantic'] else 'OFF'}) ===")
    print(f"{'method':32s} {'MAE':>7s} {'RMSE':>7s} {'bias':>7s} {'max|err|':>9s}")
    for name, m in report["methods"].items():
        if "mae" not in m:
            print(f"{name:32s} {'n/a':>7s}")
            continue
        print(f"{name:32s} {m['mae']:7.2f} {m['rmse']:7.2f} "
              f"{m['bias']:+7.2f} {m['max_abs_error']:9.1f}")

    print("\nMissing-skill detection")
    for name, m in report["missing"].items():
        print(f"  {name:24s} P={m['precision']:.2f} R={m['recall']:.2f} "
              f"F1={m['f1']:.2f} (tp={m['tp']} fp={m['fp']} fn={m['fn']})")

    v = report["verdict"]
    print(f"\nVerdict agreement")
    print(f"  majority class ({v['majority_class']}): {v['majority_agreement']}")
    print(f"  full system: {v['system_agreement']}")

    print("\nPer-pair scores")
    print(f"{'pair':8s} {'human':>6s} {'sys':>6s} {'kw':>6s} {'mean':>6s} {'const':>6s} "
          f"{'llm':>6s}")
    for r, c in zip(report["rows"], report["loo_preds"]):
        llm = r.get("llm_zero_shot")
        print(f"{r['pair_id']:8s} {r['human_ats']:6.1f} {r['system']:6.1f} "
              f"{r['keyword_only']:6.1f} {r['unweighted']:6.1f} {c:6.1f} "
              f"{(f'{llm:6.1f}' if llm is not None else '   n/a')}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--semantic", action="store_true", help="force embeddings on")
    ap.add_argument("--no-semantic", action="store_true", help="force embeddings off")
    ap.add_argument("--llm", action="store_true", help="add the LLM zero-shot baseline")
    ap.add_argument("--json", action="store_true", help="emit JSON")
    args = ap.parse_args()

    semantic = os.getenv("CAREERPILOT_SEMANTIC") == "1"
    if args.semantic:
        semantic = True
    if args.no_semantic:
        semantic = False

    report = evaluate(semantic=semantic, use_llm=args.llm)
    if args.json:
        print(json.dumps(report, indent=2, default=sorted))
    else:
        _print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
