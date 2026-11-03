from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime

import numpy as np
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression

from forecaster.aggregate import to_logodds


@dataclass
class CalibratorVersion:
    method: str
    date: str
    n_train: int


class IdentityCalibrator:
    method = "identity"

    def predict(self, probs: np.ndarray) -> np.ndarray:
        return np.asarray(probs, dtype=float)

    def to_dict(self) -> dict:
        return {"method": self.method, "params": {}}

    @classmethod
    def from_dict(cls, d: dict) -> IdentityCalibrator:
        return cls()


@dataclass
class PlattCalibrator:
    a: float
    b: float
    method: str = "platt"

    def predict(self, probs: np.ndarray) -> np.ndarray:
        x = to_logodds(np.asarray(probs, dtype=float))
        z = self.a * x + self.b
        return 1 / (1 + np.exp(-z))

    def to_dict(self) -> dict:
        return {"method": self.method, "params": {"a": self.a, "b": self.b}}

    @classmethod
    def from_dict(cls, d: dict) -> PlattCalibrator:
        return cls(a=d["params"]["a"], b=d["params"]["b"])

    @classmethod
    def fit(cls, raw_probs: np.ndarray, outcomes: np.ndarray) -> PlattCalibrator:
        x = to_logodds(raw_probs).reshape(-1, 1)
        clf = LogisticRegression()
        clf.fit(x, outcomes)
        return cls(a=float(clf.coef_[0][0]), b=float(clf.intercept_[0]))


@dataclass
class IsotonicCalibrator:
    x_thresholds: list[float] = field(default_factory=list)
    y_thresholds: list[float] = field(default_factory=list)
    method: str = "isotonic"

    def predict(self, probs: np.ndarray) -> np.ndarray:
        x = np.asarray(self.x_thresholds, dtype=float)
        y = np.asarray(self.y_thresholds, dtype=float)
        return np.interp(np.asarray(probs, dtype=float), x, y)

    def to_dict(self) -> dict:
        return {
            "method": self.method,
            "params": {"x_thresholds": self.x_thresholds, "y_thresholds": self.y_thresholds},
        }

    @classmethod
    def from_dict(cls, d: dict) -> IsotonicCalibrator:
        return cls(
            x_thresholds=d["params"]["x_thresholds"], y_thresholds=d["params"]["y_thresholds"]
        )

    @classmethod
    def fit(cls, raw_probs: np.ndarray, outcomes: np.ndarray) -> IsotonicCalibrator:
        model = IsotonicRegression(out_of_bounds="clip")
        model.fit(raw_probs, outcomes)
        return cls(
            x_thresholds=model.X_thresholds_.tolist(), y_thresholds=model.y_thresholds_.tolist()
        )


_CLASSES = {
    "identity": IdentityCalibrator,
    "platt": PlattCalibrator,
    "isotonic": IsotonicCalibrator,
}


def temporal_split(
    timestamps: list[datetime], train_frac: float = 0.7
) -> tuple[list[int], list[int]]:
    order = sorted(range(len(timestamps)), key=lambda i: timestamps[i])
    n_train = int(len(order) * train_frac)
    return order[:n_train], order[n_train:]


def choose_method(n: int) -> str:
    if n < 50:
        return "identity"
    if n < 300:
        return "platt"
    return "isotonic"


def fit(raw_probs: np.ndarray, outcomes: np.ndarray, method: str = "auto"):
    n = len(outcomes)
    if method == "auto":
        method = choose_method(n)
    if method == "identity":
        return IdentityCalibrator()
    if method == "platt":
        return PlattCalibrator.fit(raw_probs, outcomes)
    if method == "isotonic":
        return IsotonicCalibrator.fit(raw_probs, outcomes)
    raise ValueError(f"unknown calibration method: {method}")


def save(calibrator, path: str, n_train: int) -> None:
    version = CalibratorVersion(
        method=calibrator.method, date=datetime.now(UTC).isoformat(), n_train=n_train
    )
    payload = {**calibrator.to_dict(), "version": version.__dict__}
    with open(path, "w") as f:
        json.dump(payload, f, indent=2)


def load(path: str):
    with open(path) as f:
        payload = json.load(f)
    cls = _CLASSES[payload["method"]]
    return cls.from_dict(payload), payload.get("version")
