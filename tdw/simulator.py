"""Event-accurate execution. Committed motion cannot be retracted by replanning."""
from __future__ import annotations
import heapq
import time as clock
from dataclasses import dataclass
import numpy as np
from .belief import BeliefTracker
from .flight import FlightModel
from .instance import generate_instance, road_km, truck_minutes
from .observation import ObservationManager
from .policies import Context, make_policy
from .scheduler import validate_plan
from .weather import WeatherEnvironment


class HorizonReached(Exception):
    pass


@dataclass
class Episode:
    metrics: dict
    events: list
    instance: object
    truth: np.ndarray
    truck_edges: list
    sorties: list
    queries: list
    pickups: dict
    plans: list
    voi: list


class Simulator:
    def __init__(self, config, policy="prior", seed=42, instance=None, environment=None):
        self.cfg, self.seed = config, seed
        self.instance = instance or generate_instance(config, seed)
        self.env = environment or WeatherEnvironment(config, seed)
        self.flight = FlightModel(self.instance, config)
        self.belief = BeliefTracker(config)
        self.obs = ObservationManager(config, seed)
        self.policy = make_policy(policy, config, seed, self.env.snapshot if policy == "oracle" else None)
        self.now, self.current = 0., self.instance.start
        self.remaining = set(self.instance.customers)
        self.on_truck, self.pickups, self.forced = set(), {}, set()
        self.drone_status, self.truck_status = "ON_TRUCK", "AT_NODE"
        self.commit = None
        self.travel = None
        self.truck_xy = tuple(self.instance.coords[self.current])
        self.events, self.edges, self.sorties, self.plans = [], [], [], []
        self.queue, self.counter = [], 0
        self.truck_km = self.energy = self.drone_km = self.truck_wait = self.query_wait = 0.
        self.incidents = self.canceled = self.planning_cpu = 0
        self.moves = {}
        self.horizon = float(config["simulation"]["duration_min"])
        period = config["simulation"]["replan_every_min"]
        for t in np.arange(period, self.horizon+1e-9, period):
            self.push(float(t), "PERIODIC", None)
        step = config["simulation"]["weather_step_min"]
        for t in np.arange(step, self.horizon+1e-9, step):
            self.push(float(t), "WEATHER_TICK", None)

    def push(self, t, typ, payload):
        self.counter += 1
        heapq.heappush(self.queue, (float(t), self.counter, typ, payload))

    def total_cost(self):
        c = self.cfg["cost"]
        late = sum(max(0.,t-self.instance.customers[j].latest) for j,t in self.pickups.items())
        return (self.truck_km*c["truck_per_km"] + self.energy*c["drone_per_wh"]
                + self.obs.count*self.cfg["observation"]["cost_per_query"] + self.now*c["elapsed_per_min"]
                + late*c["late_per_min"] + self.incidents*c["safety_incident"])

    def log(self, typ, **kw):
        e = dict(episode_seed=self.seed,policy=self.policy.name,event_time_min=round(self.now,8),
                 event_type=typ,node_id=self.current,drone_sortie_id=None,zone_id=None,
                 truck_position=list(self.truck_xy),drone_status=self.drone_status,
                 truck_status=self.truck_status,observation_available=False,
                 budget_left=self.obs.budget_left,cumulative_cost=self.total_cost(),
                 committed_recovery=self.commit)
        e.update(kw); self.events.append(e)

    def context(self):
        return Context(self.instance,self.cfg,self.flight,self.now,self.current,
                       tuple(sorted(self.remaining)),self.belief.get(self.now),
                       tuple(q[0] for q in self.obs.public_pending()),frozenset(self.forced))

    def advance(self, target):
        if target < self.now-1e-9: raise AssertionError("Time reversal")
        limited = min(target,self.horizon)
        while self.queue and self.queue[0][0] <= limited+1e-9:
            t, _, typ, payload = heapq.heappop(self.queue)
            self.update_travel(t)
            self.now = max(self.now,t)
            if typ == "QUERY_RESULT":
                for report in self.obs.deliver(self.now):
                    self.belief.assimilate(report,self.now,self.cfg["observation"]["correct_classification_probability"])
                    self.log("QUERY_RESULT",zone_id=report["region"],query_id=report["query_id"],
                             report_label=report["label"],observation_available=True)
                    self.log("REPLAN",reason="query_result",deferred=self.commit is not None or self.truck_status!="AT_NODE")
            elif typ == "DRONE_PICKUP":
                a,sid=payload
                if a.customer in self.pickups: raise AssertionError("Duplicate pickup")
                self.pickups[a.customer]=self.now
                self.log(typ,node_id=a.customer,drone_sortie_id=sid)
            elif typ == "DRONE_LAND":
                a,sid=payload; self.drone_status="LANDED_WAITING"
                self.log(typ,node_id=a.recover,drone_sortie_id=sid)
            elif typ == "PERIODIC":
                self.log("REPLAN",reason="periodic",deferred=self.truck_status!="AT_NODE" or self.commit is not None)
            elif typ == "WEATHER_TICK": self.log(typ)
        self.update_travel(limited)
        self.now=limited
        if target > self.horizon+1e-9: raise HorizonReached()

    def update_travel(self, time):
        if self.travel is None: return
        origin, destination, start, end, km, last = self.travel
        upto = min(time, end)
        duration = end-start
        if duration > 1e-12:
            self.truck_km += km*max(0.,upto-last)/duration
            frac = max(0.,min(1.,(upto-start)/duration))
            self.truck_xy = tuple((1-frac)*np.array(self.instance.coords[origin])+frac*np.array(self.instance.coords[destination]))
        self.travel = (origin,destination,start,end,km,upto)

    def drive(self, destination):
        origin,start=self.current,self.now
        duration=truck_minutes(self.instance,self.cfg,origin,destination)
        km=road_km(self.instance,self.cfg,origin,destination)
        self.truck_status="DRIVING"
        self.log("TRUCK_DEPART",origin=origin,destination=destination)
        end=start+duration
        self.travel=(origin,destination,start,end,km,start)
        try:
            self.advance(end)
        finally:
            fraction=1. if duration<1e-12 else max(0.,min(1.,(self.now-start)/duration))
            self.edges.append(dict(origin=origin,destination=destination,start=start,end=self.now,km=km*fraction,
                                   fraction=fraction,end_xy=list(self.truck_xy)))
            self.travel=None
        self.current,self.truck_xy,self.truck_status=destination,self.instance.coords[destination],"AT_NODE"
        self.log("TRUCK_ARRIVE"); self.log("REPLAN",reason="truck_arrival",deferred=self.commit is not None)

    def truck_pickup(self):
        j=self.current
        if j not in self.remaining: return
        customer=self.instance.customers[j]
        if self.now<customer.earliest:
            self.log("TRUCK_WAIT_START",reason="time_window")
            wait=customer.earliest-self.now; self.advance(customer.earliest); self.truck_wait+=wait
            self.log("TRUCK_WAIT_END",reason="time_window")
        self.truck_status="SERVICING"; self.log("TRUCK_SERVICE_START")
        self.advance(self.now+self.cfg["truck"]["pickup_service_min"]); self.truck_status="AT_NODE"
        if j in self.pickups: raise AssertionError("Duplicate truck pickup")
        self.pickups[j]=self.now; self.remaining.remove(j); self.on_truck.add(j)
        self.log("TRUCK_PICKUP")

    def maybe_query(self):
        if self.obs.budget_left<=0 or len(self.obs.pending)>=self.cfg["observation"]["max_concurrent"]: return
        started=clock.process_time(); region=self.policy.query_region(self.context())
        self.planning_cpu+=clock.process_time()-started
        if region is None or not self.obs.can_start(region): return
        report=self.obs.start(region,self.now,self.belief.get(self.now)[region],self.env.snapshot(self.now)[region])
        self.log("QUERY_START",zone_id=region,query_id=report["query_id"],result_due=report["arrival"])
        self.push(report["arrival"],"QUERY_RESULT",None)
        if self.policy.name=="voi_query":
            self.log("TRUCK_WAIT_START",reason="query")
            delay=report["arrival"]-self.now
            self.advance(report["arrival"]); self.query_wait+=delay
            self.log("TRUCK_WAIT_END",reason="query")
        elif report["arrival"]==self.now: self.advance(self.now)

    def execute_sortie_block(self, plan, a):
        sid=len(self.sorties); self.commit=a.recover
        self.drone_status="PREPARING"; self.log("DRONE_PREP_START",drone_sortie_id=sid)
        self.advance(self.now+self.cfg["drone"]["launch_prep_min"])
        mins,wh,bad,outbound,km=self.flight.evaluate(a,self.env.snapshot(self.now))
        if bad[0]:
            self.incidents+=1; self.canceled+=1; self.forced.add(a.customer)
            self.drone_status="ON_TRUCK"; self.commit=None
            self.log("SORTIE_CANCELED",drone_sortie_id=sid,customer=a.customer,reason="physical_interlock")
            return
        launch=self.now; customer=self.instance.customers[a.customer]
        pickup=max(launch+float(outbound[0]),customer.earliest)+self.cfg["drone"]["pickup_service_min"]
        land=pickup+float(mins[0])-float(outbound[0])
        record=dict(id=sid,launch=a.launch,customer=a.customer,recover=a.recover,
                    start=launch,pickup=pickup,land=land,end=None,wh=float(wh[0]),km=km)
        self.sorties.append(record); self.energy+=float(wh[0]); self.drone_km+=km
        self.drone_status="AIRBORNE"; self.log("DRONE_LAUNCH",drone_sortie_id=sid,customer=a.customer,recover=a.recover)
        self.push(pickup,"DRONE_PICKUP",(a,sid)); self.push(land,"DRONE_LAND",(a,sid))
        finish=plan.route.index(a.recover)
        for node in plan.route[1:finish+1]:
            self.drive(node)
            if node!=a.recover: self.truck_pickup()
        if self.now<land:
            self.log("TRUCK_WAIT_START",reason="drone")
            wait=land-self.now; self.advance(land); self.truck_wait+=wait
            self.log("TRUCK_WAIT_END",reason="drone")
        self.drone_status="RECOVERING"; self.log("DRONE_RECOVERY_START",drone_sortie_id=sid)
        self.advance(self.now+self.cfg["drone"]["recovery_min"])
        self.on_truck.add(a.customer); self.remaining.remove(a.customer)
        self.drone_status="ON_TRUCK"; self.commit=None; record["end"]=self.now
        self.log("DRONE_RECOVERED",drone_sortie_id=sid,customer=a.customer)
        self.log("REPLAN",reason="drone_recovered",deferred=False); self.truck_pickup()

    def run(self):
        wall=clock.perf_counter(); self.log("EPISODE_START"); error=""
        try:
            if sum(c.weight for c in self.instance.customers.values())>self.cfg["truck"]["capacity_kg"]+1e-9:
                raise ValueError("Total pickup weight exceeds truck capacity")
            while self.remaining or self.current!=self.instance.end:
                self.maybe_query(); started=clock.process_time()
                plan,moves=self.policy.plan(self.context()); self.planning_cpu+=clock.process_time()-started
                validate_plan(plan,self.remaining,self.current,self.instance,self.cfg)
                self.plans.append(dict(time=self.now,route=plan.route,sorties=[vars(a) for a in plan.sorties]))
                self.log("REPLAN",reason="safe_boundary",deferred=False)
                for key,v in moves.items(): self.moves[key]=self.moves.get(key,0)+v
                a=next((a for a in plan.sorties if a.launch==self.current),None)
                if a is not None: self.execute_sortie_block(plan,a)
                else: self.drive(plan.route[1]); self.truck_pickup()
        except (HorizonReached,ValueError) as exc:
            error=str(exc) or "simulation_horizon_exceeded"
        complete=(not self.remaining and self.current==self.instance.end
                  and self.on_truck==set(self.instance.customers) and self.drone_status=="ON_TRUCK")
        if not complete and not error: error="unfinished_orders_or_cargo"
        lateness=[max(0.,t-self.instance.customers[j].latest) for j,t in self.pickups.items()]
        on_time=sum(t<=self.instance.customers[j].latest+1e-9 for j,t in self.pickups.items())
        self.log("EPISODE_END",completed=complete,error=error)
        metrics=dict(policy=self.policy.name,seed=self.seed,n_customers=len(self.instance.customers),
                     total_cost=self.total_cost(),completion_time_min=self.now,truck_km=self.truck_km,
                     drone_km=self.drone_km,drone_energy_Wh=self.energy,query_count=self.obs.count,
                     query_cost=self.obs.count*self.cfg["observation"]["cost_per_query"],query_wait_min=self.query_wait,
                     drone_sortie_count=len(self.sorties),truck_wait_min=self.truck_wait,on_time_rate=on_time/len(self.instance.customers),
                     total_lateness_min=sum(lateness),incident_count=self.incidents,canceled_sortie_count=self.canceled,
                     tasks_completed=len(self.on_truck),infeasible_flag=int(not complete),planning_cpu_sec=self.planning_cpu,
                     total_wall_sec=clock.perf_counter()-wall,error=error,order_hash=self.instance.fingerprint(),weather_hash=self.env.fingerprint())
        episode=Episode(metrics,self.events,self.instance,self.env.audit(),self.edges,self.sorties,self.obs.starts,self.pickups,self.plans,self.policy.audit_voi)
        episode.config=self.cfg
        return episode


def run_episode(config,policy="prior",seed=42):
    return Simulator(config,policy,seed).run()
