"""Skill VAE tests: math on a micro-model, graceful fallback, live weights."""
import pytest

torch = pytest.importorskip("torch")

from app.services import skill_vae as vae


def test_elbo_finite_and_probs_bounded():
    torch.manual_seed(0)
    docs = [[0, 1, 2], [1, 2, 3], [0, 3], [2, 3, 4], [0, 1, 4], [5, 6, 7]]
    blob = vae.train_vae(docs, vocab_size=8, epochs=10, seed=1)
    model = vae.SkillVAE(8)  # default hidden/latent must match train_vae
    model.load_state_dict(blob["state_dict"])
    model.eval()
    x = torch.zeros(1, 8)
    x[0, [0, 1]] = 1.0
    with torch.no_grad():
        logits, mu, logvar = model(x)
        loss = vae._elbo_loss(logits, x, mu, logvar)
    assert torch.isfinite(loss)
    probs = model.probs(x)
    assert probs.shape == (1, 8) and bool(((probs >= 0) & (probs <= 1)).all())


def test_suggest_graceful_without_model(monkeypatch, tmp_path):
    monkeypatch.setattr(vae, "MODEL_PATH", tmp_path / "absent.pt")
    monkeypatch.setattr(vae, "_model_cache", None)
    assert vae.suggest_skills(["Python"]) == []
    gaps = {"strong": ["Python"], "partial": [], "missing": [], "critical_missing": []}
    out = vae.enrich_gaps(gaps, ["Python"])
    assert out["suggested"] == []


def test_live_weights_suggest_new_skills():
    if not vae.MODEL_PATH.exists():
        pytest.skip("train first: python scripts/train_skill_vae.py")
    out = vae.suggest_skills(["React", "JavaScript"], top_n=3)
    assert len(out) == 3
    assert all(0.0 <= s["confidence"] <= 1.0 for s in out)
    assert all(s["skill"] not in {"React", "JavaScript"} for s in out)
    gaps = {"strong": ["React", "JavaScript"], "partial": [],
            "missing": [{"skill": "Docker", "criticality": "High",
                         "reason": "r", "weeks_to_learn": 3}],
            "critical_missing": ["Docker"]}
    enriched = vae.enrich_gaps(dict(gaps), ["React", "JavaScript"])
    assert all(s["skill"] not in {"React", "JavaScript", "Docker"}
               for s in enriched["suggested"])
