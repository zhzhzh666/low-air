"""Timestamped Bayesian filtering; assimilate delayed labels at acquisition time."""
import numpy as np


class BeliefTracker:
    def __init__(self, config):
        self.step = config["simulation"]["weather_step_min"]
        self.transition = np.array(config["weather"]["transition_matrix"], float)
        n = config["map"]["weather_grid_rows"] * config["map"]["weather_grid_cols"]
        self.anchor = np.tile(config["weather"]["initial_prob"], (n, 1)).astype(float)
        self.anchor_slot = np.zeros(n, int)

    def get(self, time):
        slot = int(time // self.step)
        return np.array([p @ np.linalg.matrix_power(self.transition, max(0, slot-int(s)))
                         for p, s in zip(self.anchor, self.anchor_slot)])

    def assimilate(self, report, now, accuracy):
        if now + 1e-9 < report["arrival"]:
            raise ValueError("Report has not arrived")
        # Stored prior at acquisition incorporates all earlier delivered reports.
        p = np.array(report["prior"], float)
        likelihood = np.full(3, (1-accuracy)/2)
        likelihood[report["label"]] = accuracy
        posterior = p * likelihood
        if posterior.sum() <= 0:
            raise ValueError("Impossible observation under prior")
        self.anchor[report["region"]] = posterior / posterior.sum()
        self.anchor_slot[report["region"]] = int(report["start"] // self.step)


def posterior_given_label(prior, label, accuracy):
    likelihood = np.full(3, (1-accuracy)/2)
    likelihood[label] = accuracy
    weights = np.asarray(prior) * likelihood
    return weights / weights.sum() if weights.sum() > 0 else np.asarray(prior).copy()
