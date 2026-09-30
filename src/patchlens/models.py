"""A CPU reference implementation with explicit, gradient-checked objectives.

These compact NumPy models are research baselines, not pretrained LLMs.
"""
from __future__ import annotations

from dataclasses import dataclass
import numpy as np


def sigmoid(x: np.ndarray) -> np.ndarray:
    return np.exp(-np.logaddexp(0., -x))


def contrastive_loss(z: np.ndarray, labels: np.ndarray, temperature: float = .15) -> tuple[float, np.ndarray]:
    """Masked paired InfoNCE/MNRL-style loss on [originals, positive views].

    The paired label-preserving view is positive; every opposite-label item is
    a negative. Same-label non-paired items and self-comparisons are excluded.
    Vulnerable/fixed siblings are opposite-label negatives, never positives.
    """
    m = len(z)
    if m < 4 or m % 2 or labels.shape != (m,) or not np.array_equal(labels[:m//2], labels[m//2:]):
        raise ValueError("Contrastive inputs must be equally ordered originals and same-label views")
    if set(labels.tolist()) != {0, 1} or temperature <= 0:
        raise ValueError("Both classes and a positive temperature are required")
    positive = (np.arange(m) + m//2) % m
    valid = labels[:, None] != labels[None, :]
    valid[np.arange(m), positive] = True
    logits = (z @ z.T) / temperature
    masked = np.where(valid, logits, -1e30)
    shifted = masked - masked.max(axis=1, keepdims=True)
    exp = np.where(valid, np.exp(shifted), 0.)
    partition = exp.sum(axis=1, keepdims=True)
    probabilities = exp / partition
    loss = float(np.mean(np.log(partition[:, 0])-shifted[np.arange(m), positive]))
    derivative = probabilities.copy()
    derivative[np.arange(m), positive] -= 1
    derivative /= m
    grad = (derivative + derivative.T) @ z / temperature
    return loss, grad


def objective(params: dict[str, np.ndarray], x: np.ndarray, y: np.ndarray,
              contrastive_weight: float = 0., positive_weight: float = 1.,
              temperature: float = .15, l2: float = 1e-4) -> tuple[float, dict, dict]:
    """Return objective, exact gradients and decomposed losses."""
    linear = "w1" not in params
    if linear:
        z = x
    else:
        hidden = np.tanh(x @ params["w1"] + params["b1"])
        raw = hidden @ params["w2"] + params["b2"]
        norm = np.sqrt((raw*raw).sum(axis=1, keepdims=True) + 1e-12)
        z = raw / norm
    logits = z @ params["head"] + params["bias"]
    weights = np.where(y == 1, positive_weight, 1.)
    weights = weights / weights.sum()
    ce = float(np.sum(weights * (np.logaddexp(0., logits) - y*logits)))
    d_logits = weights * (sigmoid(logits)-y)
    grads = {"head": z.T @ d_logits, "bias": np.asarray(d_logits.sum())}
    dz = d_logits[:, None] * params["head"][None, :]
    con = 0.
    if contrastive_weight:
        if linear:
            raise ValueError("Contrastive training requires the learned encoder")
        con, d_con = contrastive_loss(z, y, temperature)
        dz += contrastive_weight * d_con
    if not linear:
        d_raw = (dz - z*(dz*z).sum(axis=1, keepdims=True)) / norm
        grads["w2"] = hidden.T @ d_raw
        grads["b2"] = d_raw.sum(axis=0)
        dh = (d_raw @ params["w2"].T)*(1-hidden*hidden)
        grads["w1"] = x.T @ dh
        grads["b1"] = dh.sum(axis=0)
    penalty = 0.
    for key in ("w1", "w2", "head"):
        if key in params:
            penalty += .5*l2*float((params[key]**2).sum())
            grads[key] += l2*params[key]
    loss = ce + contrastive_weight*con + penalty
    return loss, grads, {"classification": ce, "contrastive": con, "regularization": penalty}


@dataclass
class Model:
    kind: str
    params: dict[str, np.ndarray]

    @classmethod
    def create(cls, n_features: int, kind: str, seed: int, hidden: int = 48, embedding: int = 16) -> "Model":
        if kind not in ("linear", "encoder") or n_features < 1:
            raise ValueError("Unknown model kind or empty feature space")
        rng = np.random.default_rng(seed)
        params = {"bias": np.asarray(0.)}
        if kind == "linear":
            params["head"] = np.zeros(n_features)
        else:
            params.update({"w1": rng.normal(0, 1/np.sqrt(n_features), (n_features, hidden)),
                           "b1": np.zeros(hidden), "w2": rng.normal(0, 1/np.sqrt(hidden), (hidden, embedding)),
                           "b2": np.zeros(embedding), "head": rng.normal(0, .05, embedding)})
        return cls(kind, params)

    def encode(self, x: np.ndarray) -> np.ndarray:
        if self.kind == "linear":
            return x
        p = self.params
        raw = np.tanh(x @ p["w1"] + p["b1"]) @ p["w2"] + p["b2"]
        return raw / np.sqrt((raw*raw).sum(axis=1, keepdims=True)+1e-12)

    def predict(self, x: np.ndarray) -> np.ndarray:
        return sigmoid(self.encode(x) @ self.params["head"] + self.params["bias"])

    def fit(self, x: np.ndarray, y: np.ndarray, *, epochs: int = 240, learning_rate: float = .012,
            contrastive_weight: float = 0., positive_weight: float = 1., temperature: float = .15) -> list[dict]:
        if not 1 <= epochs <= 10000 or not 0 < learning_rate <= 1 or not 0 < positive_weight <= 100 or not 0 <= contrastive_weight <= 10:
            raise ValueError("Training hyperparameters outside supported bounds")
        first = {key: np.zeros_like(value) for key, value in self.params.items()}
        second = {key: np.zeros_like(value) for key, value in self.params.items()}
        history = []
        for step in range(1, epochs+1):
            loss, gradients, parts = objective(self.params, x, y, contrastive_weight, positive_weight, temperature)
            if not np.isfinite(loss) or not all(np.isfinite(g).all() for g in gradients.values()):
                raise ValueError("Non-finite training objective; no result was accepted")
            if step == 1 or step % 5 == 0 or step == epochs:
                history.append({"epoch": step, "loss": loss, **parts})
            for key, grad in gradients.items():
                first[key] = .9*first[key] + .1*grad
                second[key] = .999*second[key] + .001*grad*grad
                m = first[key] / (1-.9**step)
                v = second[key] / (1-.999**step)
                self.params[key] -= learning_rate*m/(np.sqrt(v)+1e-8)
        return history

    def to_dict(self) -> dict:
        return {"kind": self.kind, "params": {key: value.tolist() for key, value in self.params.items()}}

    @classmethod
    def from_dict(cls, value: dict, n_features: int) -> "Model":
        kind = value["kind"]
        params = {key: np.asarray(v, dtype=float) for key, v in value["params"].items()}
        required = {"head", "bias"} | ({"w1", "b1", "w2", "b2"} if kind == "encoder" else set())
        if kind not in ("linear", "encoder") or set(params) != required or not all(np.isfinite(v).all() for v in params.values()):
            raise ValueError("Invalid model parameters")
        if params["bias"].shape != ():
            raise ValueError("Model bias must be scalar")
        if kind == "linear":
            valid = params["head"].shape == (n_features,)
        else:
            valid = (params["w1"].ndim == 2 and params["w2"].ndim == 2 and
                     params["w1"].shape[0] == n_features and params["w1"].shape[1] == params["w2"].shape[0] and
                     params["b1"].shape == (params["w1"].shape[1],) and params["b2"].shape == (params["w2"].shape[1],) and
                     params["head"].shape == (params["w2"].shape[1],))
        if not valid:
            raise ValueError("Inconsistent model shapes")
        return cls(kind, params)
