from __future__ import annotations

from dataclasses import dataclass, field
from typing import Tuple
import copy
import hashlib
import json
import numpy as np
import yaml


def keyed_seed(*parts):
    return int.from_bytes(hashlib.sha256(repr(parts).encode()).digest()[:8], "little")


def load_config(path):
    with open(path, encoding="utf-8-sig") as f:
        c = yaml.safe_load(f)
    for key in ("map", "truck", "drone", "weather", "observation", "planning", "cost", "simulation"):
        if key not in c:
            raise ValueError("Missing configuration section: " + key)
    p = np.array(c["weather"]["initial_prob"], float)
    tr = np.array(c["weather"]["transition_matrix"], float)
    if p.shape != (3,) or tr.shape != (3, 3) or np.any(p < 0) or np.any(tr < 0) or not np.isclose(p.sum(), 1) or not np.allclose(tr.sum(1), 1):
        raise ValueError("Weather probabilities must be nonnegative and normalized")
    if not 0 <= c["observation"]["correct_classification_probability"] <= 1:
        raise ValueError("Invalid observation accuracy")
    if c["observation"]["delay_min"] < 0 or c["observation"]["max_queries"] < 0 or c["observation"]["max_concurrent"] < 0:
        raise ValueError("Invalid observation resources")
    if c["planning"]["scenarios"] < 1 or c["planning"]["safety_samples"] < 1:
        raise ValueError("Scenario counts must be positive")
    if c["map"]["n_customers"] < 1 or c["simulation"]["weather_step_min"] <= 0 or c["simulation"]["replan_every_min"] <= 0:
        raise ValueError("Invalid instance/time parameters")
    return c


@dataclass(frozen=True)
class Customer:
    id: int
    xy: Tuple[float, float]
    weight: float
    earliest: float
    latest: float


@dataclass
class Instance:
    customers: dict
    coords: dict
    start: int
    end: int
    seed: int

    def fingerprint(self):
        return hashlib.sha256(json.dumps({k: vars(v) for k, v in self.customers.items()}, sort_keys=True).encode()).hexdigest()


@dataclass(frozen=True)
class Sortie:
    launch: int
    customer: int
    recover: int


@dataclass
class Plan:
    route: list
    sorties: list = field(default_factory=list)

    def signature(self):
        return (tuple(self.route), tuple(sorted((a.launch, a.customer, a.recover) for a in self.sorties)))

    def copy(self):
        return Plan(self.route[:], self.sorties[:])


@dataclass(frozen=True)
class PolicyState:
    time: float
    current_node: int
    remaining: tuple
    beliefs: tuple
    budget_left: int
    pending_regions: tuple
    truck_status: str
    drone_status: str
    committed_recovery: int | None = None


def clone_config(c):
    return copy.deepcopy(c)
