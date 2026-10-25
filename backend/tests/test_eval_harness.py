"""Eval harness: labeled pairs score deterministically (offline, no LLM, no DB)."""
from scripts.eval_ats import evaluate, load_pairs


def test_eval_set_has_labeled_pairs():
    pairs = load_pairs()
    assert len(pairs) >= 3
    assert all(p["human_ats"] > 0 for p in pairs)
    assert all(p["resume_text"] and p["jd_text"] for p in pairs)


def test_evaluate_reports_metrics_offline():
    report = evaluate(semantic=False)
    assert report["n"] >= 3
    assert report["ats"]["mae"] is not None
    assert report["verdict"]["agreement_pct"] is not None
    assert 0.0 <= report["missing"]["f1"] <= 1.0
    # every pair carries a prediction + human baseline for diffing
    assert all("delta" in r and "pred_ats" in r for r in report["rows"])
