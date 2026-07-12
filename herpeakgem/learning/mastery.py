"""Mastery scoring policies with a backwards-compatible BKT option.

``compute_mastery`` remains the established recency-weighted policy.  The BKT
engine is explicit so existing learning paths do not silently change pedagogy;
callers can opt into a calibrated knowledge-tracing estimate per course.
"""
from __future__ import annotations

from dataclasses import dataclass

_RECENCY_WEIGHTS: tuple[float, ...] = (0.5, 0.7, 0.85, 0.95, 1.0)
_CONFIDENCE_CAP: dict[int, float] = {1: 0.5, 2: 0.8}


@dataclass(frozen=True)
class BKTParameters:
    """Bayesian Knowledge Tracing parameters for one knowledge-point family."""

    prior: float = 0.2
    learn: float = 0.15
    guess: float = 0.2
    slip: float = 0.1

    def __post_init__(self) -> None:
        for name, value in vars(self).items():
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be within 0..1")
        if self.guess + self.slip >= 1.0:
            raise ValueError("guess + slip must be less than 1 for identifiable BKT updates")


def compute_bkt_mastery(correctness: list[bool], params: BKTParameters | None = None) -> float:
    """Return a 0..1 BKT posterior after chronological answer outcomes.

    Each observation first updates the posterior using slip/guess likelihoods,
    then applies the learning transition. Empty history returns the calibrated
    prior instead of pretending the learner has no latent knowledge.
    """
    params = params or BKTParameters()
    mastery = params.prior
    for correct in correctness:
        if correct:
            likelihood = mastery * (1.0 - params.slip) + (1.0 - mastery) * params.guess
            posterior = (mastery * (1.0 - params.slip)) / likelihood
        else:
            likelihood = mastery * params.slip + (1.0 - mastery) * (1.0 - params.guess)
            posterior = (mastery * params.slip) / likelihood
        mastery = posterior + (1.0 - posterior) * params.learn
    return min(1.0, max(0.0, mastery))


def compute_mastery(correctness: list[bool]) -> float:
    """Return the established recency-weighted 0..1 display mastery score."""
    if not correctness:
        return 0.0
    recent = correctness[-len(_RECENCY_WEIGHTS) :]
    weights = _RECENCY_WEIGHTS[-len(recent) :]
    score = sum(weight * float(correct) for weight, correct in zip(weights, recent, strict=True)) / sum(weights)
    return min(score, _CONFIDENCE_CAP.get(len(recent), 1.0))


__all__ = ["BKTParameters", "compute_bkt_mastery", "compute_mastery"]
