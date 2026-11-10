#!/usr/bin/env python3
"""Low-altitude logistics simulation with active weather information acquisition.

The model captures a truck route with drone pickup sorties.  Local wind is a
latent state for each zone.  A dispatcher can pay a small time cost to query
one zone before deciding whether to fly there.  The active policy uses a
one-step value-of-information rule; the remaining policies provide useful
baselines and bounds.

All times are minutes.  The script is deterministic for a supplied seed and
writes summary CSV/JSON files so that the experiment is reproducible.
"""

from __future__ import annotations

import csv
import json
import math
import random
import statistics
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, List, Tuple


STATES = ("calm", "moderate", "strong")
WIND_MPS = {"calm": 2.0, "moderate": 6.0, "strong": 10.0}


@dataclass(frozen=True)
class Zone:
    name: str
    road_leg_km: float
    road_detour_km: float
    air_distance_km: float
    demand_kg: float
    priority: float
    # Schematic local-map coordinates (km). They represent the operating area
    # used by the map version of the simulator, rather than latitude/longitude.
    x_km: float
    y_km: float


@dataclass
class ScenarioResult:
    policy: str
    seed: int
    completion_time_min: float
    total_cost: float
    drone_share: float
    queries: int
    failures: int
    truck_pickups: int
    drone_pickups: int
    safe_drone_pickups: int
    trace: List[dict]


ZONES: Tuple[Zone, ...] = (
    Zone("A", 5.8, 2.6, 2.0, 2.2, 1.00, 12.0, 18.0),
    Zone("B", 6.4, 3.1, 2.8, 3.7, 0.95, 25.0, 27.0),
    Zone("C", 5.1, 2.3, 1.7, 1.8, 0.85, 38.0, 17.0),
    Zone("D", 7.0, 3.6, 3.4, 4.1, 1.20, 51.0, 36.0),
    Zone("E", 6.0, 2.8, 2.5, 2.8, 1.05, 65.0, 29.0),
    Zone("F", 5.5, 2.4, 1.9, 1.6, 0.75, 76.0, 43.0),
    Zone("G", 6.8, 3.3, 3.0, 3.9, 1.10, 88.0, 33.0),
    Zone("H", 5.9, 2.5, 2.2, 2.4, 0.90, 95.0, 49.0),
)

# A common regional prior: calm wind dominates, while strong wind is a small
# but material tail risk for a low-altitude sortie.
PRIOR = {"calm": 0.52, "moderate": 0.30, "strong": 0.18}
DRONE_MAX_WIND_MPS = 8.0
TRUCK_SPEED_KM_PER_MIN = 0.50
DRONE_SPEED_KM_PER_MIN = 1.00
QUERY_TIME_MIN = 2.0
SORTIE_OVERHEAD_MIN = 4.0
FAILURE_PENALTY_MIN = 18.0
FAILURE_RISK_COST = 12.0
DRONE_PAYLOAD_KG = 4.5
QUERY_BUDGET = 3


def safe_state(state: str) -> bool:
    return WIND_MPS[state] <= DRONE_MAX_WIND_MPS


def normalise(p: Dict[str, float]) -> Dict[str, float]:
    z = sum(p.values())
    return {k: v / z for k, v in p.items()}


def drone_sortie_time(zone: Zone, state: str) -> float:
    """Round trip from a truck rendezvous point, including wind drag."""
    # Wind drag makes the sortie slower even when it remains safe.
    drag = 1.0 + 0.025 * max(0.0, WIND_MPS[state] - 2.0)
    return SORTIE_OVERHEAD_MIN + 2.0 * zone.air_distance_km / DRONE_SPEED_KM_PER_MIN * drag


def stage_cost(zone: Zone, state: str, action: str) -> Tuple[float, bool]:
    """Return time added by this zone and whether the drone flight was safe."""
    base_leg = zone.road_leg_km / TRUCK_SPEED_KM_PER_MIN
    if action == "truck":
        return base_leg + zone.road_detour_km / TRUCK_SPEED_KM_PER_MIN + 4.0, True
    if zone.demand_kg > DRONE_PAYLOAD_KG:
        return base_leg + zone.road_detour_km / TRUCK_SPEED_KM_PER_MIN + 4.0, True
    if not safe_state(state):
        # The truck recovers the order after a rejected/failed sortie.
        return base_leg + FAILURE_PENALTY_MIN + 4.0, False
    # The truck continues its route while the drone flies.  Only the excess
    # sortie time delays the route, which models a rendezvous at the next stop.
    return base_leg + max(0.0, drone_sortie_time(zone, state) - base_leg), True


def expected_stage_cost(zone: Zone, posterior: Dict[str, float], action: str) -> float:
    return sum(posterior[s] * stage_cost(zone, s, action)[0] for s in STATES)


def safe_probability(posterior: Dict[str, float]) -> float:
    return sum(posterior[s] for s in STATES if safe_state(s))


def choose_action(zone: Zone, posterior: Dict[str, float], policy: str) -> str:
    """Choose truck/drone after any weather information is available."""
    if zone.demand_kg > DRONE_PAYLOAD_KG:
        return "truck"
    if policy == "blind_aggressive":
        # A useful stress-test baseline: fly whenever the payload fits and
        # accept the latent-wind risk without buying information.
        return "drone"
    truck = expected_stage_cost(zone, posterior, "truck")
    drone = expected_stage_cost(zone, posterior, "drone")
    # With no observation, require a high confidence level before flying.  This
    # is the safety constraint a dispatcher uses when local wind is uncertain.
    if policy in {"none", "random", "active", "all_query"} and safe_probability(posterior) < 0.95:
        return "truck"
    return "drone" if drone + 1e-9 < truck else "truck"


def value_of_information(zone: Zone, posterior: Dict[str, float]) -> float:
    """Expected reduction in stage time from revealing the local wind."""
    no_query = min(expected_stage_cost(zone, posterior, "truck"),
                   expected_stage_cost(zone, posterior, "drone"))
    revealed = sum(
        posterior[s]
        * min(stage_cost(zone, s, "truck")[0], stage_cost(zone, s, "drone")[0])
        for s in STATES
    )
    # A priority multiplier makes urgent or high-value orders more attractive
    # when two zones offer similar information value.
    return max(0.0, (no_query - revealed) * zone.priority)


def active_query_decision(zone: Zone, posterior: Dict[str, float], remaining_budget: int) -> bool:
    if remaining_budget <= 0 or zone.demand_kg > DRONE_PAYLOAD_KG:
        return False
    voi = value_of_information(zone, posterior)
    uncertainty = 1.0 - max(posterior.values())
    # Query when the expected time saving covers its two-minute cost and the
    # posterior is genuinely uncertain.  This is a one-step rollout policy.
    return voi >= QUERY_TIME_MIN * 0.90 and uncertainty >= 0.12


def sample_weather(rng: random.Random) -> Dict[str, str]:
    # A shared regional component induces realistic spatial correlation while
    # preserving local variation between zones.
    regional = rng.random()
    if regional < 0.15:
        prior = {"calm": 0.28, "moderate": 0.42, "strong": 0.30}
    elif regional > 0.85:
        prior = {"calm": 0.68, "moderate": 0.25, "strong": 0.07}
    else:
        prior = PRIOR
    states = []
    for _ in ZONES:
        x = rng.random()
        acc = 0.0
        for s in STATES:
            acc += prior[s]
            if x <= acc:
                states.append(s)
                break
    return {z.name: s for z, s in zip(ZONES, states)}


def run_scenario(seed: int, policy: str, query_budget: int = QUERY_BUDGET,
                 keep_trace: bool = False) -> ScenarioResult:
    rng = random.Random(seed)
    weather = sample_weather(rng)
    total_time = 0.0
    queries = failures = truck_pickups = drone_pickups = safe_drone_pickups = 0
    trace: List[dict] = []
    observed: Dict[str, str] = {}
    # Active sensing allocates the limited budget to the regions with the
    # largest one-step value of information.  The truck still visits regions
    # in route order, so a query can be made before that region is served.
    active_targets = set()
    if policy == "active":
        candidates = [z for z in ZONES if z.demand_kg <= DRONE_PAYLOAD_KG]
        active_targets = {
            z.name for z in sorted(candidates,
                                   key=lambda z: value_of_information(z, PRIOR),
                                   reverse=True)[:query_budget]
        }

    for zone in ZONES:
        posterior = dict(PRIOR)
        query = False
        if policy == "oracle":
            observed[zone.name] = weather[zone.name]
            posterior = {s: 1.0 if s == weather[zone.name] else 0.0 for s in STATES}
        elif policy == "all_query" and zone.demand_kg <= DRONE_PAYLOAD_KG:
            query = True
        elif policy == "random" and query_budget > 0 and zone.demand_kg <= DRONE_PAYLOAD_KG:
            query = rng.random() < (query_budget / max(1, len(ZONES)))
        elif policy == "active":
            query = zone.name in active_targets and active_query_decision(zone, posterior, query_budget)

        if query and query_budget > 0:
            query_budget -= 1
            queries += 1
            total_time += QUERY_TIME_MIN
            observed[zone.name] = weather[zone.name]
            posterior = {s: 1.0 if s == weather[zone.name] else 0.0 for s in STATES}

        if zone.name in observed and policy != "oracle":
            posterior = {s: 1.0 if s == observed[zone.name] else 0.0 for s in STATES}
        action = choose_action(zone, posterior, policy)
        state = weather[zone.name]
        stage, safe = stage_cost(zone, state, action)
        total_time += stage
        if action == "truck":
            truck_pickups += 1
        else:
            drone_pickups += 1
            if safe:
                safe_drone_pickups += 1
            else:
                failures += 1
        if keep_trace:
            trace.append({
                "zone": zone.name,
                "weather_real": state,
                "query": query,
                "posterior_safe": round(safe_probability(posterior), 3),
                "voi_min": round(value_of_information(zone, posterior), 3),
                "action": action,
                "stage_time_min": round(stage, 2),
                "safe": safe,
            })

    total_cost = total_time + FAILURE_RISK_COST * failures
    share = drone_pickups / max(1, len(ZONES))
    return ScenarioResult(policy, seed, total_time, total_cost, share, queries,
                           failures, truck_pickups, drone_pickups,
                           safe_drone_pickups, trace)


def summarise(results: List[ScenarioResult]) -> dict:
    def mean(xs): return round(statistics.mean(xs), 3)
    def p95(xs):
        ys = sorted(xs)
        idx = min(len(ys) - 1, math.ceil(0.95 * len(ys)) - 1)
        return round(ys[idx], 3)
    return {
        "policy": results[0].policy,
        "scenarios": len(results),
        "mean_completion_time_min": mean([r.completion_time_min for r in results]),
        "p95_completion_time_min": p95([r.completion_time_min for r in results]),
        "mean_total_cost": mean([r.total_cost for r in results]),
        "mean_drone_share": mean([r.drone_share for r in results]),
        "mean_queries": mean([r.queries for r in results]),
        "mean_failures": mean([r.failures for r in results]),
        "failure_rate": round(sum(r.failures for r in results) / max(1, sum(r.drone_pickups for r in results)), 4),
    }


def run_experiment(out_dir: Path, n_scenarios: int = 500, base_seed: int = 20261011) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    policies = ["none", "blind_aggressive", "random", "active", "all_query", "oracle"]
    summary_rows = []
    all_rows = []
    traces = {}
    for policy in policies:
        results = [run_scenario(base_seed + i, policy, keep_trace=(i == 0))
                   for i in range(n_scenarios)]
        summary_rows.append(summarise(results))
        for r in results:
            all_rows.append({
                "policy": r.policy, "seed": r.seed,
                "completion_time_min": round(r.completion_time_min, 4),
                "total_cost": round(r.total_cost, 4),
                "drone_share": round(r.drone_share, 4), "queries": r.queries,
                "failures": r.failures,
            })
        traces[policy] = {
            "weather_and_actions": results[0].trace,
            "summary": summary_rows[-1],
        }

    with (out_dir / "policy_summary.csv").open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=summary_rows[0].keys())
        writer.writeheader(); writer.writerows(summary_rows)
    with (out_dir / "scenario_results.csv").open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=all_rows[0].keys())
        writer.writeheader(); writer.writerows(all_rows)
    with (out_dir / "representative_traces.json").open("w", encoding="utf-8") as f:
        json.dump(traces, f, ensure_ascii=False, indent=2)
    with (out_dir / "model_parameters.json").open("w", encoding="utf-8") as f:
        json.dump({
            "zones": [asdict(z) for z in ZONES],
            "prior": PRIOR,
            "query_budget": QUERY_BUDGET,
            "query_time_min": QUERY_TIME_MIN,
            "drone_max_wind_mps": DRONE_MAX_WIND_MPS,
            "failure_penalty_min": FAILURE_PENALTY_MIN,
            "failure_risk_cost": FAILURE_RISK_COST,
            "scenarios": n_scenarios,
            "base_seed": base_seed,
        }, f, ensure_ascii=False, indent=2)

    # Budget sensitivity for the active policy.  The same seeds are reused so
    # differences reflect the budget rather than a different weather sample.
    sens_rows = []
    for budget in range(0, 7):
        rs = [run_scenario(base_seed + i, "active", query_budget=budget)
              for i in range(n_scenarios)]
        sens_rows.append({
            "query_budget": budget,
            "mean_completion_time_min": round(statistics.mean(r.completion_time_min for r in rs), 3),
            "p95_completion_time_min": round(sorted(r.completion_time_min for r in rs)[min(n_scenarios - 1, math.ceil(0.95 * n_scenarios) - 1)], 3),
            "mean_drone_share": round(statistics.mean(r.drone_share for r in rs), 3),
            "mean_queries": round(statistics.mean(r.queries for r in rs), 3),
        })
    with (out_dir / "budget_sensitivity.csv").open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=sens_rows[0].keys())
        writer.writeheader(); writer.writerows(sens_rows)

    print(json.dumps({"summary": summary_rows, "output": str(out_dir)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    run_experiment(Path(__file__).resolve().parent / "results")
