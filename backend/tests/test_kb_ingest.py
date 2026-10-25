"""KB ingest tests: user CSV validation (pure function, offline)."""
from pathlib import Path

from app.services.kb_ingest import load_user_csvs


def test_valid_csvs_parse(tmp_path):
    (tmp_path / "learning_resources.csv").write_text(
        "skill,title,url,type\n"
        "Docker,Docker video,https://www.youtube.com/results?search_query=x,video\n",
        encoding="utf-8",
    )
    (tmp_path / "questions.csv").write_text(
        "skill,category,difficulty,q,ideal_answer,key_points\n"
        'Docker,technical,Easy,What is Docker?,An image runner.,"a|b"\n',
        encoding="utf-8",
    )
    res, qs = load_user_csvs(tmp_path)
    assert res == [{"skill": "Docker", "title": "Docker video",
                    "url": "https://www.youtube.com/results?search_query=x", "type": "video"}]
    assert qs[0]["key_points"] == ["a", "b"]


def test_bad_rows_skipped_and_defaults(tmp_path):
    (tmp_path / "learning_resources.csv").write_text(
        "skill,title,url,type\n"
        ",No skill,https://example.com,docs\n"
        "Git,Git docs,not-a-url,docs\n"
        "Git,Git docs,https://git-scm.com/doc,weirdtype\n"
        "Git,Git docs,https://git-scm.com/doc,\n",
        encoding="utf-8",
    )
    (tmp_path / "questions.csv").write_text(
        "skill,category,difficulty,q,ideal_answer,key_points\n"
        ",,,,""\n"
        ",hr,,Tell me about yourself.,Be brief,Present\n",
        encoding="utf-8",
    )
    res, qs = load_user_csvs(tmp_path)
    assert len(res) == 1 and res[0]["type"] == "docs"
    assert len(qs) == 1
    assert qs[0]["skill"] == "General" and qs[0]["category"] == "hr"


def test_missing_files_yield_empty(tmp_path):
    assert load_user_csvs(tmp_path) == ([], [])


def test_four_col_format_emits_docs_and_video(tmp_path):
    (tmp_path / "learning_resources.csv").write_text(
        "skill,title,url_documentation,url_youtube\n"
        "FastAPI,FastAPI Tutorial,https://fastapi.tiangolo.com/tutorial/,"
        "https://www.youtube.com/results?search_query=FastAPI+full+course\n",
        encoding="utf-8",
    )
    res, qs = load_user_csvs(tmp_path)
    assert qs == []
    assert [(r["type"], r["url"]) for r in res] == [
        ("docs", "https://fastapi.tiangolo.com/tutorial/"),
        ("video", "https://www.youtube.com/results?search_query=FastAPI+full+course"),
    ]
    assert res[0]["skill"] == "FastAPI" and res[1]["title"].endswith("(video)")


def test_repo_csv_covers_taxonomy():
    from app.core.config import SKILL_TAXONOMY_CSV
    from app.services import kb_service as kb

    import csv as _csv

    repo = Path(__file__).resolve().parents[2] / "data" / "kb" / "learning_resources.csv"
    with open(repo, newline="", encoding="utf-8") as fh:
        rows = list(_csv.DictReader(fh))
    assert len(rows) >= 250, f"expected full coverage, got {len(rows)}"
    assert all(set(r) == {"skill", "title", "url_documentation", "url_youtube"} for r in rows)
    assert all(r["url_documentation"].startswith("https://") for r in rows)
    assert all("youtube.com" in r["url_youtube"] for r in rows)
    canon = {r["name"].strip() for r in _csv.DictReader(
        open(SKILL_TAXONOMY_CSV, encoding="utf-8")) if not (r.get("alias_of") or "").strip()}
    assert canon <= {r["skill"] for r in rows}
    assert len(kb.RESOURCES) >= 50  # curated fallback intact
