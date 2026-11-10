import numpy as np
from .scheduler import schedule
from .instance import truck_minutes


class DeterministicEvaluator:
    def __init__(self, instance, config, flight, start_time=0, states=None):
        self.instance, self.config, self.flight, self.start_time = instance, config, flight, start_time
        self.states = np.zeros(flight.n_regions, int) if states is None else states
        self.cache = {}

    def stats(self, a):
        mins, wh, bad, outbound, km = self.flight.evaluate(a, self.states)
        return (float(mins[0]), float(wh[0]), float(outbound[0]), km), bool(bad[0])

    def __call__(self, plan):
        key = plan.signature()
        if key in self.cache:
            return self.cache[key]
        stats = {}
        for a in plan.sorties:
            vals, bad = self.stats(a)
            if bad:
                return float("inf")
            stats[a] = vals
        result = schedule(plan, self.instance, self.config, self.start_time, stats)["cost"]
        self.cache[key] = result
        return result


class BeliefEvaluator:
    """Shared random uniforms per search, independent final safety samples."""
    def __init__(self, instance, config, flight, beliefs, start_time, rng, oracle=None):
        self.instance, self.config, self.flight = instance, config, flight
        self.beliefs, self.start_time = np.asarray(beliefs), start_time
        p = config["planning"]
        self.cost_u = rng.random((p["scenarios"], flight.n_regions))
        self.safe_u = rng.random((p["safety_samples"], flight.n_regions))
        self.hold_u = rng.random((p["safety_samples"], flight.n_regions))
        self.transition = np.array(config["weather"]["transition_matrix"])
        self.step = config["simulation"]["weather_step_min"]
        self.flight_cache, self.cache = {}, {}
        self.oracle = oracle

    def forecast(self, time):
        ticks = max(0, int(time // self.step)-int(self.start_time // self.step))
        return self.beliefs @ np.linalg.matrix_power(self.transition, ticks)

    def _states(self, time, u):
        if self.oracle is not None:
            return np.tile(self.oracle(time), (len(u), 1))
        return (u[:, :, None] > np.cumsum(self.forecast(time), axis=1)[None, :, :]).sum(2)

    def stats(self, a, time, held_out=False):
        # Five-minute weather buckets allow exact cache reuse across neighboring plans.
        slot = int(time // self.step)
        key = (a, slot, held_out)
        if key in self.flight_cache:
            return self.flight_cache[key]
        cu = self.flight.evaluate(a, self._states(time, self.cost_u))
        su = self.flight.evaluate(a, self._states(time, self.hold_u if held_out else self.safe_u))
        stats = (float(cu[0].mean()), float(cu[1].mean()), float(cu[3].mean()), cu[4])
        risk = float(su[2].mean())
        self.flight_cache[key] = (stats, risk)
        return stats, risk

    def _scheduled(self, plan, held_out=False):
        # Sequential iteration to use estimated launch times rather than current weather
        # for every future sortie. Frozen-at-launch field is the declared approximation.
        stats = {a: self.stats(a, self.start_time, held_out)[0] for a in plan.sorties}
        out = schedule(plan, self.instance, self.config, self.start_time, stats)
        for _ in range(2):
            stats = {a: self.stats(a, out["launches"][a], held_out)[0] for a in plan.sorties}
            out = schedule(plan, self.instance, self.config, self.start_time, stats)
        for a in plan.sorties:
            if self.stats(a, out["launches"][a], held_out)[1] > self.config["planning"]["unsafe_probability_tolerance"]+1e-12:
                return None
        return out

    def __call__(self, plan):
        key = plan.signature()
        if key not in self.cache:
            out = None if any(a.customer in getattr(self, "forced_truck", ()) for a in plan.sorties) else self._scheduled(plan)
            self.cache[key] = float("inf") if out is None else self.expected_cost(plan,out)
        return self.cache[key]

    def expected_cost(self,plan,mean_schedule):
        """Average cost of ONE common plan over scenarios, with sample timing/late."""
        n=len(self.cost_u); times=np.full(n,self.start_time); late=np.zeros(n)
        wh=np.zeros(n); pending={}
        launches={a.launch:a for a in plan.sorties}
        recoveries={a.recover:a for a in plan.sorties}
        for ix,node in enumerate(plan.route):
            if node in recoveries:
                times=np.maximum(times,pending[recoveries[node]])+self.config["drone"]["recovery_min"]
            if ix>0 and node in self.instance.customers:
                c=self.instance.customers[node]
                times=np.maximum(times,c.earliest)+self.config["truck"]["pickup_service_min"]
                late+=np.maximum(0,times-c.latest)
            if node in launches:
                a=launches[node]; times=times+self.config["drone"]["launch_prep_min"]
                f,e,_,out,_=self.flight.evaluate(a,self._states(mean_schedule["launches"][a],self.cost_u))
                c=self.instance.customers[a.customer]
                pickup=np.maximum(times+out,c.earliest)+self.config["drone"]["pickup_service_min"]
                late+=np.maximum(0,pickup-c.latest); pending[a]=pickup+f-out; wh+=e
            if ix+1<len(plan.route):
                times=times+truck_minutes(self.instance,self.config,node,plan.route[ix+1])
        c=self.config["cost"]
        return float(mean_schedule["road_km"]*c["truck_per_km"]+np.mean(wh)*c["drone_per_wh"]
                     +np.mean(times-self.start_time)*c["elapsed_per_min"]+np.mean(late)*c["late_per_min"])

    def certify_plan(self, plan):
        return self._scheduled(plan, held_out=True) is not None
