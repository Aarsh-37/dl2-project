"""User KB ingest: validate data/kb/*.csv rows (pure function, unit-tested).

Formats (headers must match data/kb/*.example.csv):
  learning_resources.csv → skill,title,url_documentation,url_youtube
      (legacy 3-col skill,title,url,type also accepted)
  questions.csv          → skill,category,difficulty,q,ideal_answer,key_points
key_points use | as separator, e.g. "STAR|Trade-offs|Outcome".
One CSV row becomes up to two KB rows (docs + video).
"""
from __future__ import annotations

import csv
from pathlib import Path

RESOURCE_TYPES = {"docs", "video", "course", "practice"}


def _resource_row(skill: str, title: str, url: str, rtype: str,
                  line: str) -> dict | None:
    if not (skill and title and url.startswith("http")):
        print(f"SKIP {line} — need skill, title, http(s) url")
        return None
    if rtype not in RESOURCE_TYPES:
        print(f"SKIP {line} — type must be {sorted(RESOURCE_TYPES)}")
        return None
    return {"skill": skill, "title": title, "url": url, "type": rtype}


def load_user_csvs(kb_dir: str | Path) -> tuple[list[dict], list[dict]]:
    """Read + validate user CSVs. Bad rows are skipped with a printed
    warning; a missing file simply yields []. Never raises."""
    resources, questions = [], []
    kb_dir = Path(kb_dir)
    res_path, q_path = kb_dir / "learning_resources.csv", kb_dir / "questions.csv"
    try:
        if res_path.exists():
            with open(res_path, newline="", encoding="utf-8") as fh:
                reader = csv.DictReader(fh)
                four_col = (reader.fieldnames or []) and \
                    "url_documentation" in (reader.fieldnames or [])
                for i, row in enumerate(reader, start=2):
                    skill = (row.get("skill") or "").strip()
                    title = (row.get("title") or "").strip()
                    if four_col:
                        docs = _resource_row(
                            skill, title, (row.get("url_documentation") or "").strip(),
                            "docs", f"learning_resources.csv:{i}")
                        if docs:
                            resources.append(docs)
                        yt = _resource_row(
                            skill, f"{title} (video)",
                            (row.get("url_youtube") or "").strip(),
                            "video", f"learning_resources.csv:{i}")
                        if yt:
                            resources.append(yt)
                    else:  # legacy 3-col: skill,title,url,type
                        row_out = _resource_row(
                            skill, title, (row.get("url") or "").strip(),
                            (row.get("type") or "docs").strip().lower(),
                            f"learning_resources.csv:{i}")
                        if row_out:
                            resources.append(row_out)
        if q_path.exists():
            with open(q_path, newline="", encoding="utf-8") as fh:
                for i, row in enumerate(csv.DictReader(fh), start=2):
                    q = (row.get("q") or "").strip()
                    if not q:
                        print(f"SKIP questions.csv:{i} — q is required")
                        continue
                    points = [p.strip() for p in (row.get("key_points") or "").split("|") if p.strip()]
                    questions.append({
                        "skill": (row.get("skill") or "General").strip() or "General",
                        "category": (row.get("category") or "technical").strip() or "technical",
                        "difficulty": (row.get("difficulty") or "Medium").strip() or "Medium",
                        "q": q, "ideal_answer": (row.get("ideal_answer") or "").strip(),
                        "key_points": points or ["Concrete example"],
                    })
    except Exception as exc:  # unreadable dir/file — ingest nothing, never crash
        print(f"SKIP kb csvs: {exc}")
    return resources, questions
