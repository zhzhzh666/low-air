import copy
import numpy as np
import pytest
from tdw.models import load_config,Customer,Instance,Plan,Sortie
from tdw.routing import initial_route
from tdw.simulator import Simulator
from tdw.weather import WeatherEnvironment
from tdw.policies.policies import net_voi

def tiny():
    c=load_config("configs/base.yaml"); c["map"].update(n_customers=1,weather_grid_rows=1,weather_grid_cols=1)
    c["simulation"]["weather_step_min"]=1000
    c["weather"]["transition_matrix"]=np.eye(3).tolist()
    inst=Instance({1:Customer(1,(7.,4.),.5,0.,100.)},{0:(4.,4.),1:(7.,4.),2:(4.,4.)},0,2,0)
    return c,inst

def test_voi_expected_min_and_cost():
    costs=np.array([[0.,10.],[6.,6.]])
    # min E = 5, E min = 3: perfect report's value is 2, before fee.
    assert net_voi(costs,[.5,.5],np.eye(2),0)==pytest.approx(2)
    assert net_voi(costs,[.5,.5],np.eye(2),3)==pytest.approx(-1)
    assert net_voi([[1,2],[3,4]],[.5,.5],np.eye(2),1)==pytest.approx(-1)
    assert net_voi(costs,[.5,.5],np.eye(2),0,delay_cost=5)==pytest.approx(-3)

def test_information_isolation_future_truth():
    c,inst=tiny(); a=Simulator(c,"prior",11,instance=inst); b=Simulator(c,"prior",11,instance=inst)
    b.env._truth[:]=2
    assert not np.array_equal(a.env.audit(),b.env.audit())
    assert vars(a.context()).keys()==vars(b.context()).keys()
    assert not hasattr(a.policy,"env") and a.policy.oracle is None
    assert a.policy.plan(a.context())[0].signature()==b.policy.plan(b.context())[0].signature()
    for sim in [a,b]:
        sim.policy.name="voi_query"
    assert a.policy.query_region(a.context())==b.policy.query_region(b.context())

def test_pending_labels_hidden_until_delivery():
    c,inst=tiny(); c["observation"]["correct_classification_probability"]=1
    a=Simulator(c,"voi_query",0,instance=inst); b=Simulator(c,"voi_query",0,instance=inst)
    for sim,true in [(a,0),(b,2)]:
        sim.obs.start(0,0,sim.belief.get(0)[0],true)
    assert a.obs.pending[0]["label"]!=b.obs.pending[0]["label"]
    np.testing.assert_array_equal(a.context().beliefs,b.context().beliefs)
    assert a.context().pending_regions==b.context().pending_regions==(0,)
    assert a.policy.plan(a.context())[0].signature()==b.policy.plan(b.context())[0].signature()

def test_positive_information_and_expensive_refusal():
    c,inst=tiny(); c["observation"].update(delay_min=0,cost_per_query=.01,correct_classification_probability=1.)
    s=Simulator(c,"voi_query",0,instance=inst)
    assert s.policy.query_region(s.context())==0
    assert max(v["net_voi"] for v in s.policy.audit_voi)>0
    c["observation"].update(cost_per_query=1000,delay_min=50)
    s=Simulator(c,"voi_query",0,instance=inst)
    assert s.policy.query_region(s.context()) is None

def test_prior_can_fly_without_query_and_cargo_returns():
    c,inst=tiny(); c["weather"]["initial_prob"]=[1.,0.,0.]
    ep=Simulator(c,"prior",0,instance=inst).run()
    assert ep.metrics["drone_sortie_count"]==1 and ep.metrics["query_count"]==0
    assert ep.metrics["tasks_completed"]==1 and not ep.metrics["infeasible_flag"]
    a=ep.sorties[0]; assert a["start"]<=a["pickup"]<=a["land"]<=a["end"]<=ep.metrics["completion_time_min"]
    assert a["wh"]<=80

def test_interlock_cancel_then_truck_recovery():
    c,inst=tiny(); c["weather"]["initial_prob"]=[0.,0.,1.]
    s=Simulator(c,"prior",0,instance=inst)
    def plan(ctx):
        if not ctx.forced_truck:
            return Plan([0,2],[Sortie(0,1,2)]),{}
        return Plan(initial_route(inst,c,ctx.current,ctx.remaining)),{}
    s.policy.plan=plan
    ep=s.run()
    assert ep.metrics["incident_count"]==ep.metrics["canceled_sortie_count"]==1
    assert ep.metrics["tasks_completed"]==1 and not ep.metrics["infeasible_flag"]
    assert ep.metrics["total_cost"]>=c["cost"]["safety_incident"]
    assert sum(e["event_type"]=="TRUCK_PICKUP" for e in ep.events)==1
    assert not any(e["event_type"]=="DRONE_PICKUP" for e in ep.events)

@pytest.mark.parametrize("case",["strong","overweight","no_budget","long_delay","late","coincident"])
def test_edge_cases(case):
    c,inst=tiny(); policy="random_query"
    if case=="strong": c["weather"]["initial_prob"]=[0.,0.,1.]
    if case=="overweight": inst.customers[1]=Customer(1,(7.,4.),2.5,0,100)
    if case=="no_budget": c["observation"]["max_queries"]=0
    if case=="long_delay": c["observation"]["delay_min"]=1000
    if case=="late": inst.customers[1]=Customer(1,(7.,4.),.5,0,.01)
    if case=="coincident":
        inst.coords[1]=(4.,4.); inst.customers[1]=Customer(1,(4.,4.),.5,0,100)
    ep=Simulator(c,policy,3,instance=inst).run()
    assert ep.metrics["tasks_completed"]==1 and not ep.metrics["infeasible_flag"]
    if case in ["strong","overweight"]: assert ep.metrics["drone_sortie_count"]==0
    if case=="no_budget": assert ep.metrics["query_count"]==0
    if case=="long_delay": assert not any(e["event_type"]=="QUERY_RESULT" for e in ep.events)
    if case=="late": assert ep.metrics["total_lateness_min"]>0
    times=[e["event_time_min"] for e in ep.events]; assert times==sorted(times)

def test_horizon_partial_drive_and_capacity():
    c,inst=tiny(); c["simulation"]["duration_min"]=1
    ep=Simulator(c,"truck_only",0,instance=inst).run()
    assert ep.metrics["infeasible_flag"]==1 and ep.metrics["tasks_completed"]==0
    assert ep.metrics["truck_km"]==pytest.approx(.48)
    assert ep.truck_edges[0]["fraction"]<1
    c["truck"]["capacity_kg"]=.1
    ep=Simulator(c,"prior",0,instance=inst).run()
    assert ep.metrics["infeasible_flag"] and "capacity" in ep.metrics["error"]

def test_committed_motion_and_reproducibility():
    c,inst=tiny(); c["weather"]["initial_prob"]=[1.,0.,0.]
    a=Simulator(c,"prior",1,instance=inst).run(); b=Simulator(c,"prior",1,instance=inst).run()
    for k in a.metrics:
        if k not in ["planning_cpu_sec","total_wall_sec"]: assert a.metrics[k]==b.metrics[k]
    assert a.events==b.events
    for e in a.truck_edges:
        assert e["end"]-e["start"]==pytest.approx(e["km"]*1000/c["truck"]["speed_mps"]/60)
    for e in a.events:
        if e["event_type"]=="REPLAN" and e["truck_status"]=="DRIVING": assert e["deferred"]
    assert [x["event_time_min"] for x in a.events]==sorted(x["event_time_min"] for x in a.events)
