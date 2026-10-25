"""Job Discovery (deterministic): Adzuna v1 fan-out. No key -> permitted search links."""
from __future__ import annotations

import os
import urllib.parse


def _links(query: str) -> list[dict]:
    q = urllib.parse.quote_plus(query or "software developer")
    return [
        {"title": "Adzuna search", "company": "", "location": "",
         "url": f"https://www.adzuna.com/search?q={q}", "source": "link",
         "match_pct": 0, "matched_skills": []},
        {"title": "Google Jobs search", "company": "", "location": "",
         "url": f"https://www.google.com/search?q={q}+jobs", "source": "link",
         "match_pct": 0, "matched_skills": []},
    ]


def discover_jobs(profile: dict, max_results: int = 20) -> tuple[list[dict], list[dict]]:
    errors: list[dict] = []
    skills = (profile or {}).get("technical", [])[:5]
    query = " ".join(skills) if skills else "software developer"
    app_id = os.getenv("ADZUNA_APP_ID", "")
    app_key = os.getenv("ADZUNA_APP_KEY", "")
    if not app_id or not app_key:
        errors.append({"node": "discovery", "message": "Adzuna key missing — returning search links."})
        return _links(query), errors
    try:
        import httpx
        r = httpx.get("https://api.adzuna.com/v1/api/jobs/in/what/1",
                      params={"app_id": app_id, "app_key": app_key,
                              "what": query, "results_per_page": min(max_results, 50)},
                      timeout=15)
        r.raise_for_status()
        jobs = [{
            "title": j.get("title", ""), "company": (j.get("company") or {}).get("display_name", ""),
            "location": (j.get("location") or {}).get("display_name", ""),
            "url": j.get("redirect_url", ""), "source": "adzuna",
            "match_pct": 0, "matched_skills": [],
            "description": (j.get("description", "") or "")[:2000],
        } for j in r.json().get("results", [])]
        return jobs or _links(query), errors
    except Exception as exc:  # noqa: BLE001
        errors.append({"node": "discovery", "message": f"Adzuna failed: {exc}"})
        return _links(query), errors
