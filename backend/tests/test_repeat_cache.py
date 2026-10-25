"""Repeat-cache tests: identical analysis returns instantly (offline)."""
from fastapi.testclient import TestClient

from app.api import store
from app.main import app

RESUME = ("Aarav Sharma Backend dev, 2 years. Skills: Python, SQL. "
          "Projects: API with Python. Education: B.Tech. Extra words here.")
JD = ("Hiring Backend Developer. Required: Python, SQL, Go. Preferred: AWS. "
      "Must have 2 years experience building APIs for users.")


def test_content_hash_stable_and_sensitive():
    h1 = store.content_hash(RESUME, JD, 3)
    assert h1 == store.content_hash(RESUME, JD, 3)
    assert h1 != store.content_hash(RESUME, JD, 4)
    assert h1 != store.content_hash(RESUME + "x", JD, 3)


def test_repeat_analyze_returns_same_job_instantly():
    store._JOBS.clear()
    store._HASH_INDEX.clear()
    c = TestClient(app)
    body = {"resume_text": RESUME, "jd_text": JD}
    first = c.post("/analyze", data=body)
    assert first.status_code == 202, first.text
    job1 = first.json()["job_id"]
    assert "cached" not in first.json()
    second = c.post("/analyze", data=body)
    assert second.status_code == 202
    assert second.json()["job_id"] == job1
    assert second.json().get("cached") is True
    third = c.post("/analyze", data={**body, "hours_per_day": "5"})
    assert third.json()["job_id"] != job1  # different hours -> fresh run
