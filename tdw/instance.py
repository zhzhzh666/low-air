import math
import numpy as np
from .models import Customer, Instance, keyed_seed


def generate_instance(config, seed):
    rng = np.random.default_rng(keyed_seed(seed, "orders"))
    n = config["map"]["n_customers"]
    size = config["map"]["size_km"]
    depot = tuple(config["map"]["depot_xy_km"])
    end = n + 1
    coords = {0: depot, end: depot}
    customers = {}
    for j in range(1, n + 1):
        xy = tuple(rng.uniform(0.25, size - 0.25, 2))
        # Loose enough to avoid dominating every instance, still allows lateness.
        earliest = float(rng.uniform(0, 12))
        latest = earliest + float(rng.uniform(55, 110))
        customers[j] = Customer(j, xy, float(rng.uniform(.3, 2.5)), earliest, latest)
        coords[j] = xy
    return Instance(customers, coords, 0, end, seed)


def road_km(instance, config, i, k):
    a, b = instance.coords[i], instance.coords[k]
    return math.hypot(a[0]-b[0],a[1]-b[1]) * config["map"]["road_detour_factor"]


def truck_minutes(instance, config, i, k):
    return road_km(instance, config, i, k) * 1000 / config["truck"]["speed_mps"] / 60
