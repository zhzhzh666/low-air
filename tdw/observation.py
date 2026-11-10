import numpy as np
from .models import keyed_seed


class ObservationManager:
    def __init__(self, config, seed):
        self.cfg = config["observation"]
        self.seed = seed
        self.pending = {}
        self.count = 0
        self.starts = []

    @property
    def budget_left(self):
        return self.cfg["max_queries"] - self.count

    def can_start(self, region):
        return (self.budget_left > 0 and len(self.pending) < self.cfg["max_concurrent"]
                and region not in self.pending)

    def start(self, region, now, prior, true_class):
        if not self.can_start(region):
            return None
        # Stable common noise key independent of policy query ordering.
        # Slot is absolute simulation minute, not ordinal query count.
        slot = round(float(now), 6)
        u = np.random.default_rng(keyed_seed(self.seed, "observation", region, slot)).random()
        likelihood = np.full(3, (1-self.cfg["correct_classification_probability"])/2)
        likelihood[int(true_class)] = self.cfg["correct_classification_probability"]
        label = min(2, int(np.searchsorted(np.cumsum(likelihood), u)))
        item = dict(region=int(region), start=float(now), arrival=float(now+self.cfg["delay_min"]),
                    prior=np.asarray(prior).tolist(), label=label, query_id=self.count)
        self.pending[region] = item
        self.starts.append(item.copy())
        self.count += 1
        return item

    def deliver(self, now):
        reports = sorted([q for q in self.pending.values() if q["arrival"] <= now+1e-9],
                         key=lambda x: x["arrival"])
        for report in reports:
            del self.pending[report["region"]]
        return reports

    def public_pending(self):
        return tuple((q["region"], q["start"], q["arrival"]) for q in self.pending.values())
