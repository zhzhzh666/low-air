from __future__ import annotations
from dataclasses import dataclass
import numpy as np
from ..belief import posterior_given_label
from ..evaluator import BeliefEvaluator
from ..instance import truck_minutes
from ..models import Plan, Sortie, keyed_seed
from ..routing import initial_route, optimize
from ..scheduler import validate_plan


@dataclass(frozen=True)
class Context:
    instance: object
    config: dict
    flight: object
    time: float
    current: int
    remaining: tuple
    beliefs: np.ndarray
    pending_regions: tuple = ()
    forced_truck: frozenset = frozenset()


def net_voi(cost_matrix, prior, noise, query_cost, delay_cost=0.):
    c, p, o = np.asarray(cost_matrix), np.asarray(prior), np.asarray(noise)
    no = float((c @ p).min())
    query = query_cost + delay_cost
    for z in range(o.shape[1]):
        weights = p * o[:, z]
        prob = weights.sum()
        if prob > 0:
            query += prob * float((c @ (weights/prob)).min())
    return no-query


class Policy:
    name = "prior"
    def __init__(self, config, seed, oracle=None):
        self.config, self.seed, self.oracle = config, seed, oracle
        self.audit_voi = []
        self.search_round = 0

    def evaluator(self, ctx, beliefs=None, time=None, salt="plan"):
        rng = np.random.default_rng(keyed_seed(self.seed, "search-weather", round(ctx.time, 6), salt))
        ev = BeliefEvaluator(ctx.instance, ctx.config, ctx.flight,
                             ctx.beliefs if beliefs is None else beliefs,
                             ctx.time if time is None else time, rng,
                             oracle=self.oracle if self.name == "oracle" else None)
        ev.forced_truck = ctx.forced_truck
        return ev

    def plan(self, ctx):
        rng = np.random.default_rng(keyed_seed(self.seed, "optimizer", round(ctx.time, 6), ctx.current, self.search_round))
        self.search_round += 1
        return optimize(ctx.instance, ctx.config, ctx.current, ctx.remaining,
                        self.evaluator(ctx), rng, allow_drone=self.name != "truck_only")

    def options(self, ctx):
        base = initial_route(ctx.instance, ctx.config, ctx.current, ctx.remaining)
        options, relevant = [Plan(base)], set()
        elapsed = 0.
        for ix, j in enumerate(base[1:-1], 1):
            elapsed += truck_minutes(ctx.instance, ctx.config, base[ix-1], j)
            if elapsed > ctx.config["planning"]["voi_lookahead_min"]:
                break
            if j in ctx.forced_truck or ctx.instance.customers[j].weight > ctx.config["drone"]["capacity_kg"]:
                continue
            route = [n for n in base if n != j]
            for delta in [0, 1]:
                i = max(0, ix-1-delta); k = min(len(route)-1, ix+delta)
                a = Sortie(route[i], j, route[k])
                candidate = Plan(route, [a])
                try: validate_plan(candidate, ctx.remaining, ctx.current, ctx.instance, ctx.config)
                except ValueError: continue
                options.append(candidate); relevant.update(ctx.flight.coefficients(a)[2])
        return options, sorted(relevant-set(ctx.pending_regions))

    def query_region(self, ctx):
        if self.name not in {"random_query","entropy_query","voi_query"} or not ctx.remaining:
            return None
        options, regions = self.options(ctx)
        if not regions: return None
        if self.name == "random_query":
            return int(np.random.default_rng(keyed_seed(self.seed,"query",round(ctx.time,6))).choice(regions))
        if self.name == "entropy_query":
            return max(regions, key=lambda r: float(-(ctx.beliefs[r]*np.log(np.maximum(ctx.beliefs[r],1e-15))).sum()))
        delay = ctx.config["observation"]["delay_min"]
        acc = ctx.config["observation"]["correct_classification_probability"]
        noev=self.evaluator(ctx,salt="voi-common")
        j_no=min(noev(p) for p in options)
        trans = np.array(ctx.config["weather"]["transition_matrix"])
        steps = int((ctx.time+delay)//ctx.config["simulation"]["weather_step_min"])-int(ctx.time//ctx.config["simulation"]["weather_step_min"])
        noise = np.full((3,3),(1-acc)/2); np.fill_diagonal(noise,acc)
        best, best_value = None, 1e-7
        for r in regions:
            j_query = ctx.config["observation"]["cost_per_query"] + delay*ctx.config["cost"]["elapsed_per_min"]
            for z in range(3):
                weights = ctx.beliefs[r]*noise[:,z]; prob = float(weights.sum())
                if prob <= 0: continue
                b2 = ctx.beliefs.copy(); b2[r] = weights/prob
                if steps: b2=b2 @ np.linalg.matrix_power(trans,steps)
                ev = self.evaluator(ctx, beliefs=b2, time=ctx.time+delay, salt="voi-common")
                j_query += prob*min(ev(p) for p in options)
            value = float(j_no-j_query)
            self.audit_voi.append({"time":ctx.time,"region":r,"J_no":j_no,"J_query":j_query,"net_voi":value})
            if value > best_value: best,best_value=r,value
        return best


def make_policy(name, config, seed, oracle=None):
    if name not in {"truck_only","prior","random_query","entropy_query","voi_query","oracle"}:
        raise ValueError("Unknown policy "+name)
    p = Policy(config,seed,oracle); p.name=name; return p
