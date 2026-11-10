"""Grid-integrated, frozen-at-launch synthetic flight proxy. No weather access."""
import math
import numpy as np


def region_of(xy, config):
    m = config["map"]
    r = min(m["weather_grid_rows"] - 1, max(0, int(xy[1] / m["size_km"] * m["weather_grid_rows"])))
    c = min(m["weather_grid_cols"] - 1, max(0, int(xy[0] / m["size_km"] * m["weather_grid_cols"])))
    return r * m["weather_grid_cols"] + c


def split_segment(p, q, config):
    """Exact straight line/grid intersections, returns (region, km, unit direction)."""
    p, q = np.array(p, float), np.array(q, float)
    delta = q-p
    length = float(np.linalg.norm(delta))
    if length < 1e-12:
        return []
    cuts = [0., 1.]
    m = config["map"]
    for axis, count in [(0, m["weather_grid_cols"]), (1, m["weather_grid_rows"])]:
        if abs(delta[axis]) > 1e-12:
            for k in range(1, count):
                f = (m["size_km"] * k / count - p[axis]) / delta[axis]
                if 0 < f < 1:
                    cuts.append(float(f))
    cuts = sorted(set(cuts))
    direction = delta / length
    return [(region_of(p + (a+b)/2*delta, config), length*(b-a), direction)
            for a, b in zip(cuts, cuts[1:])]


class FlightModel:
    def __init__(self, instance, config):
        self.instance, self.config = instance, config
        self.cache = {}
        self.n_regions = config["map"]["weather_grid_rows"] * config["map"]["weather_grid_cols"]

    def coefficients(self, a):
        """Lookup arrays region x windstate. Separate empty/loaded flight legs."""
        if a in self.cache:
            return self.cache[a]
        c, inst = self.config, self.instance
        times = np.zeros((self.n_regions, 3))
        energy = np.zeros_like(times)
        used = set()
        distance = 0.
        first_times = np.zeros_like(times)
        for leg, (p, q, payload) in enumerate([(a.launch, a.customer, 0.), (a.customer, a.recover, inst.customers[a.customer].weight)]):
            for reg, km, direction in split_segment(inst.coords[p], inst.coords[q], c):
                used.add(reg)
                distance += km
                angle = 2 * math.pi * (reg + .5) / self.n_regions
                wind_direction = np.array([math.cos(angle), math.sin(angle)])
                for w, speed in enumerate(c["weather"]["speeds_mps"]):
                    ground = max(3., c["drone"]["airspeed_mps"] + speed * float(wind_direction @ direction))
                    sec = km * 1000 / ground
                    power = c["drone"]["power_base_w"] + c["drone"]["power_payload_w_per_kg"] * payload + c["drone"]["power_wind_w_per_mps2"] * speed**2
                    times[reg, w] += sec/60
                    energy[reg, w] += power * sec/3600
                    if leg == 0:
                        first_times[reg, w] += sec/60
        self.cache[a] = (times, energy, tuple(sorted(used)), distance, first_times)
        return self.cache[a]

    def evaluate(self, a, states):
        states = np.atleast_2d(states).astype(int)
        times, energy, used, distance, first = self.coefficients(a)
        idx = np.arange(self.n_regions)[None, :]
        mins = times[idx, states].sum(1)
        wh = energy[idx, states].sum(1)
        outbound = first[idx, states].sum(1)
        dc = self.config["drone"]
        speeds = np.array(self.config["weather"]["speeds_mps"])
        wind_bad = (speeds[states[:, used]] > dc["wind_limit_mps"]).any(1) if used else np.zeros(len(states), bool)
        unsafe = wind_bad | (wh > dc["battery_wh"]*(1-dc["reserve_fraction"]) + 1e-9)
        return mins, wh, unsafe, outbound, distance
