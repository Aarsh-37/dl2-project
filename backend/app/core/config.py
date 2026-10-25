"""Backend core config. Frozen values mirror contracts.md (ATS weights, verdicts).

Repo layout anchor: backend/app/core/config.py -> parents[3] is the project root
(CareerPilot AI), so data/ paths work from anywhere.
"""
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = REPO_ROOT / "data"
SKILL_TAXONOMY_CSV = DATA_DIR / "skill_taxonomy.csv"
SAMPLES_DIR = DATA_DIR / "samples"
EVAL_CSV = DATA_DIR / "eval" / "eval_set.csv"

# Frozen in contracts.md §3 — change only with a contract bump.
ATS_WEIGHTS_V1 = {
    "keyword": 0.25,
    "skill": 0.25,
    "semantic": 0.20,
    "experience": 0.15,
    "education": 0.05,
    "project_relevance": 0.10,
}
ATS_VERDICTS = {"strong": 75, "moderate": 50}  # heuristics, not standards

# Rough learning-time defaults per taxonomy category (overridden by gap LLM later).
WEEKS_TO_LEARN_BY_CATEGORY = {
    "language": 4, "frontend": 3, "backend": 3, "database": 2,
    "devops": 3, "cloud": 4, "data": 3, "ml": 6, "mobile": 4,
    "testing": 2, "tools": 1, "security": 4, "fundamentals": 3,
}
DEFAULT_WEEKS_TO_LEARN = 3
