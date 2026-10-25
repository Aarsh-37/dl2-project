"""Skill VAE recommender — deep learning inside CareerPilot AI.

Syllabus map:
- Unit V: Variational Autoencoder (neural + graphical-model view). A
  candidate's skill set is a high-dimensional observation; the encoder
  compresses it to a low-dimensional latent "profile" (Unit II: latent
  variables), the decoder reconstructs P(skill | profile). Skills with high
  reconstructed probability that the candidate LACKS are suggestions:
  "people with your stack usually also know X".
- Unit III (RBMs): the conceptual predecessor — same idea (learn P(data)
  over binary vectors via latent factors), superseded here by the VAE +
  transformer embeddings used for semantic match.
- Unit IV (MCMC/Gibbs/CD): how energy-based models like RBMs are trained.
  VAEs train instead by maximizing the ELBO with the reparameterization
  trick (see train_vae) — no sampling loop needed at inference.

Honest scope: this is a small prior model over skill co-occurrence, NOT a
replacement for gap analysis. Suggestions are labeled experimental, never
override deterministic gaps, and the pipeline works identically with the
model file absent (suggest_skills -> []).
"""
from __future__ import annotations

import json
import os
from pathlib import Path

try:
    import torch
    import torch.nn as nn

    _TORCH = True
except ImportError:  # pragma: no cover
    torch, nn, _TORCH = None, None, False  # type: ignore

REPO_ROOT = Path(__file__).resolve().parents[3]
MODEL_PATH = Path(os.getenv("SKILL_VAE_PATH", REPO_ROOT / "data" / "skill_vae.pt"))

LATENT_DIM = 16
HIDDEN_DIM = 64


if _TORCH:
    class SkillVAE(nn.Module):
        def __init__(self, vocab_size: int, hidden: int = HIDDEN_DIM,
                     latent: int = LATENT_DIM):
            super().__init__()
            self.enc = nn.Sequential(nn.Linear(vocab_size, hidden), nn.ReLU())
            self.mu = nn.Linear(hidden, latent)
            self.logvar = nn.Linear(hidden, latent)
            self.dec = nn.Sequential(nn.Linear(latent, hidden), nn.ReLU(),
                                     nn.Linear(hidden, vocab_size))

        def forward(self, x):
            h = self.enc(x)
            mu, logvar = self.mu(h), self.logvar(h)
            std = torch.exp(0.5 * logvar)
            z = mu + std * torch.randn_like(std)  # reparameterization trick
            return self.dec(z), mu, logvar

        @torch.no_grad()
        def probs(self, x) -> "torch.Tensor":
            self.eval()
            h = self.enc(x)
            return torch.sigmoid(self.dec(self.mu(h)))  # use mean: deterministic


def _elbo_loss(logits, x, mu, logvar, beta: float = 0.5) -> "torch.Tensor":
    bce = nn.functional.binary_cross_entropy_with_logits(logits, x, reduction="sum")
    kld = -0.5 * torch.sum(1 + logvar - mu.pow(2) - logvar.exp())
    return bce + beta * kld


def train_vae(docs: list[list[int]], vocab_size: int, epochs: int = 400,
              seed: int = 7, lr: float = 1e-2) -> dict:
    """Train on multi-hot doc indices. Returns {vocab_size, state_dict}."""
    torch.manual_seed(seed)
    x = torch.zeros(len(docs), vocab_size)
    for i, doc in enumerate(docs):
        for idx in doc:
            x[i, idx] = 1.0
    model = SkillVAE(vocab_size)
    opt = torch.optim.Adam(model.parameters(), lr=lr)
    model.train()
    for _ in range(epochs):
        opt.zero_grad()
        logits, mu, logvar = model(x)
        loss = _elbo_loss(logits, x, mu, logvar)
        loss.backward()
        opt.step()
    return {"vocab_size": vocab_size, "state_dict": model.state_dict()}


_model_cache: dict | None = None


def _load() -> dict | None:
    global _model_cache
    if _model_cache is not None:
        return _model_cache
    if not _TORCH or not MODEL_PATH.exists():
        return None
    try:
        blob = torch.load(MODEL_PATH, map_location="cpu", weights_only=True)
        model = SkillVAE(blob["vocab_size"])
        model.load_state_dict(blob["state_dict"])
        model.eval()
        _model_cache = {"model": model, "vocab": blob["vocab"]}
        return _model_cache
    except Exception:
        return None


def suggest_skills(candidate: list[str], top_n: int = 3) -> list[dict]:
    """Suggest missing skills from the latent profile.

    Returns [{skill, confidence (0-1), reason}]. [] when the model file is
    absent — callers treat suggestions as optional enrichment only.
    """
    bundle = _load()
    if not bundle:
        return []
    vocab: list[str] = bundle["vocab"]
    have = {s for s in (candidate or []) if s in vocab}
    if not have:
        return []
    import torch as _t

    x = _t.zeros(1, len(vocab))
    pos = {s: i for i, s in enumerate(vocab)}
    for s in have:
        x[0, pos[s]] = 1.0
    probs = bundle["model"].probs(x)[0]
    ranked = sorted(((float(probs[pos[s]]), s) for s in vocab if s not in have),
                    reverse=True)[:top_n]
    return [{"skill": s, "confidence": round(p, 2),
             "reason": "Often co-occurs with your stack (VAE latent model, experimental)."}
            for p, s in ranked]


def enrich_gaps(gaps: dict, candidate: list[str], top_n: int = 3) -> dict:
    """Attach VAE `suggested` to a gaps dict (best-effort, never raises).

    Only genuinely new skills (outside strong/partial/missing) are kept,
    so suggestions complement the deterministic analysis instead of
    echoing it. Frontend Zod strips the key safely (optional field).
    """
    try:
        known = set(gaps.get("strong", [])) | set(gaps.get("partial", []))
        known |= {m["skill"] for m in gaps.get("missing", [])}
        gaps["suggested"] = [s for s in suggest_skills(candidate, top_n)
                             if s["skill"] not in known][:top_n]
    except Exception:
        gaps.setdefault("suggested", [])
    return gaps


def vocab_of(bundle_path: str | Path = MODEL_PATH) -> list[str]:
    p = Path(bundle_path)
    if not p.exists():
        return []
    try:
        import torch as _t
        return list(_t.load(p, map_location="cpu", weights_only=True).get("vocab", []))
    except Exception:
        return []
