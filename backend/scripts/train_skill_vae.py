"""Train the skill VAE and save data/skill_vae.pt (idempotent — re-run anytime).

Corpus = real skill sets (sample resumes/JDs via the taxonomy extractor,
KB question skills grouped by category) + seeded category-subset variations
from the taxonomy itself (the co-occurrence prior). Seeded RNG => same
weights every run.

    python scripts/train_skill_vae.py [--epochs 400]
"""
import csv
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import torch

from app.core.config import SKILL_TAXONOMY_CSV
from app.services import kb_service as kb
from app.services.skill_vae import MODEL_PATH, train_vae
from app.tools import skill_extract

EPOCHS = int(sys.argv[sys.argv.index("--epochs") + 1]) if "--epochs" in sys.argv else 400


def canonical_taxonomy() -> dict[str, list[str]]:
    cats: dict[str, set[str]] = {}
    with open(SKILL_TAXONOMY_CSV, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            name, alias, cat = (row.get("name") or "").strip(), \
                (row.get("alias_of") or "").strip(), (row.get("category") or "").strip()
            if name and not alias and cat:
                cats.setdefault(cat, set()).add(name)
    return {c: sorted(s) for c, s in cats.items()}


def main() -> int:
    rng = random.Random(7)
    tax = skill_extract.load_taxonomy(SKILL_TAXONOMY_CSV)
    cats = canonical_taxonomy()

    docs: list[set[str]] = []
    # 1. Real docs: sample resumes + JDs.
    samples = sorted((Path(__file__).resolve().parents[2] / "data" / "samples").glob("*.md"))
    for path in samples:
        skills = skill_extract.extract_skills(path.read_text(encoding="utf-8"), tax)
        if len(skills) >= 2:
            docs.append(set(skills))
    # 2. KB question skills grouped by category (technical topics that co-occur).
    by_cat: dict[str, set[str]] = {}
    for q in kb.QUESTIONS:
        if q.get("skill") not in (None, "", "General"):
            by_cat.setdefault(q["category"], set()).add(q["skill"])
    docs.extend(s for s in by_cat.values() if len(s) >= 2)
    # 3. Seeded taxonomy prior: random subsets within each category (stacks
    # that co-occur in practice) + a few cross-category bridges.
    for skills in cats.values():
        if len(skills) < 3:
            continue
        for _ in range(6):
            k = rng.randint(3, min(6, len(skills)))
            docs.append(set(rng.sample(skills, k)))
    bridges = [("frontend", "backend"), ("backend", "database"), ("backend", "devops"),
               ("data", "ml"), ("language", "testing")]
    for a, b in bridges:
        if a in cats and b in cats:
            docs.append(set(rng.sample(cats[a], min(3, len(cats[a])))
                              + rng.sample(cats[b], min(3, len(cats[b])))))

    vocab = sorted({s for d in docs for s in d})
    pos = {s: i for i, s in enumerate(vocab)}
    idx_docs = [[pos[s] for s in d] for d in docs]
    print(f"docs={len(idx_docs)} vocab={len(vocab)}")

    blob = train_vae(idx_docs, len(vocab), epochs=EPOCHS)
    torch.save({"vocab": vocab, **blob}, MODEL_PATH)
    size_kb = MODEL_PATH.stat().st_size / 1024
    print(f"saved {MODEL_PATH} ({size_kb:.1f} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
