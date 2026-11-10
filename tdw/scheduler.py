"""A deterministic resource-feasible scheduler for a complete residual plan."""
import numpy as np
from .instance import road_km, truck_minutes


def validate_plan(plan, remaining, current, instance, config):
    if not plan.route or plan.route[0] != current or plan.route[-1] != instance.end:
        raise ValueError("Route must begin at current node and finish at depot")
    if len(set(plan.route)) != len(plan.route):
        raise ValueError("Repeated route node / implicit cycle")
    truck_customers = [j for j in plan.route[1:-1] if j in remaining]
    served = truck_customers + [a.customer for a in plan.sorties]
    if len(served) != len(set(served)) or set(served) != set(remaining):
        raise ValueError("Every remaining order must be assigned exactly once")
    if any(j not in remaining for j in plan.route[1:-1]):
        raise ValueError("Unexpected truck route stop")
    intervals = []
    for a in plan.sorties:
        if a.launch not in plan.route or a.recover not in plan.route:
            raise ValueError("Unreachable launch/recovery node")
        i, k = plan.route.index(a.launch), plan.route.index(a.recover)
        if i >= k or a.customer in plan.route:
            raise ValueError("Invalid sortie precedence/customer assignment")
        if instance.customers[a.customer].weight > config["drone"]["capacity_kg"] + 1e-9:
            raise ValueError("Drone payload exceeded")
        intervals.append((i, k))
    intervals.sort()
    if any(b[0] < a[1] for a, b in zip(intervals, intervals[1:])):
        raise ValueError("Overlapping drone sorties")
    if sum(j.weight for j in instance.customers.values()) > config["truck"]["capacity_kg"] + 1e-9:
        raise ValueError("Truck capacity exceeded")


def schedule(plan, instance, config, start_time, flight_stats):
    """Stats: sortie -> (flight minutes, Wh, outbound minutes, km)."""
    time = float(start_time)
    arrivals, departures, pickup = {}, {}, {}
    launches, recoveries = {}, {}
    drone_wait, truck_wait, road = 0., 0., 0.
    by_launch = {a.launch: a for a in plan.sorties}
    by_recover = {a.recover: a for a in plan.sorties}
    pending = {}
    for idx, node in enumerate(plan.route):
        arrivals[node] = time
        if node in by_recover:
            a = by_recover[node]
            land, wh = pending[a]
            truck_wait += max(0., land-time)
            drone_wait += max(0., time-land)
            time = max(time, land) + config["drone"]["recovery_min"]
            recoveries[a] = time
        if idx > 0 and node in instance.customers:
            customer = instance.customers[node]
            time = max(time, customer.earliest) + config["truck"]["pickup_service_min"]
            pickup[node] = time
        if node in by_launch:
            a = by_launch[node]
            time += config["drone"]["launch_prep_min"]
            launches[a] = time
            flight, wh, outbound, km = flight_stats[a]
            cust = instance.customers[a.customer]
            service_end = max(time+outbound, cust.earliest) + config["drone"]["pickup_service_min"]
            pickup[cust.id] = service_end
            pending[a] = (service_end + flight-outbound, wh)
        departures[node] = time
        if idx + 1 < len(plan.route):
            nxt = plan.route[idx+1]
            time += truck_minutes(instance, config, node, nxt)
            road += road_km(instance, config, node, nxt)
    late = sum(max(0., t-instance.customers[j].latest) for j, t in pickup.items())
    wh = sum(v[1] for v in flight_stats.values())
    cost = road*config["cost"]["truck_per_km"] + wh*config["cost"]["drone_per_wh"] + (time-start_time)*config["cost"]["elapsed_per_min"] + late*config["cost"]["late_per_min"]
    return dict(cost=cost, completion=time, road_km=road, pickup=pickup, arrivals=arrivals,
                departures=departures, launches=launches, recoveries=recoveries,
                truck_wait=truck_wait, drone_wait=drone_wait, late=late)
