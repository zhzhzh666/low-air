"""Environment-only truth. Ordinary policies never receive this object."""
import hashlib
import numpy as np
from .models import keyed_seed


class WeatherEnvironment:
    def __init__(self, config, seed):
        self.step = config["simulation"]["weather_step_min"]
        self.n_regions = config["map"]["weather_grid_rows"] * config["map"]["weather_grid_cols"]
        p = np.array(config["weather"]["initial_prob"])
        transition = np.array(config["weather"]["transition_matrix"])
        count = int(config["simulation"]["duration_min"] / self.step) + 3
        rng = np.random.default_rng(keyed_seed(seed, "environment"))
        self._truth = np.empty((count, self.n_regions), int)
        self._truth[0] = rng.choice(3, size=self.n_regions, p=p)
        for t in range(1, count):
            u = rng.random(self.n_regions)
            self._truth[t] = (u[:, None] > np.cumsum(transition[self._truth[t-1]], axis=1)).sum(1)

    def snapshot(self, time):
        return self._truth[min(len(self._truth)-1, max(0, int(time // self.step)))].copy()

    def audit(self):
        return self._truth.copy()

    def fingerprint(self):
        return hashlib.sha256(self._truth.tobytes()).hexdigest()
