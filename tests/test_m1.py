import copy
import numpy as np
import pytest
from tdw.models import load_config, Plan, Sortie
from tdw.instance import generate_instance
from tdw.flight import FlightModel, split_segment
from tdw.routing import optimize
from tdw.scheduler import validate_plan, schedule
from tdw.evaluator import DeterministicEvaluator


@pytest.fixture
def setup():
    c = load_config("configs/base.yaml")
    inst = generate_instance(c, 42)
    return c, inst, FlightModel(inst, c)


def test_service_exactly_once(setup):
    c, inst, f = setup
    ev = DeterministicEvaluator(inst, c, f)
    plan, moves = optimize(inst, c, 0, list(inst.customers), ev, np.random.default_rng(42))
    validate_plan(plan, list(inst.customers), 0, inst, c)
    out = schedule(plan, inst, c, 0, {a: ev.stats(a)[0] for a in plan.sorties})
    assert set(out["pickup"]) == set(inst.customers)
    assert out["completion"] >= max(out["pickup"].values())
    assert len(plan.sorties) > 0


def test_launch_recovery_and_overlap(setup):
    c, inst, f = setup
    route = [0] + list(inst.customers) + [inst.end]
    p = Plan([j for j in route if j != 1], [Sortie(3, 1, 2)])
    with pytest.raises(ValueError, match="precedence"):
        validate_plan(p, list(inst.customers), 0, inst, c)
    p = Plan([j for j in route if j not in [1, 2]], [Sortie(0, 1, 5), Sortie(3, 2, 6)])
    # Both customers are known eligible for this seed or force payload ample.
    c["drone"]["capacity_kg"] = 10
    with pytest.raises(ValueError, match="Overlapping"):
        validate_plan(p, list(inst.customers), 0, inst, c)


def test_flight_grid_payload_energy(setup):
    c, inst, f = setup
    parts = split_segment((0, 0), (8, 8), c)
    assert len(parts) == 3
    assert sum(v[1] for v in parts) == pytest.approx(np.sqrt(128))
    a = Sortie(0, 1, inst.end)
    mins, wh, bad, outbound, km = f.evaluate(a, np.zeros(f.n_regions, int))
    assert wh[0] > 0 and mins[0] >= outbound[0]
    assert np.isfinite(wh).all()
    dc = copy.deepcopy(c)
    dc["drone"]["battery_wh"] = 1
    assert FlightModel(inst, dc).evaluate(a, np.zeros(f.n_regions, int))[2][0]


def test_one_customer_coincident(setup):
    c, _, _ = setup
    c["map"]["n_customers"] = 1
    inst = generate_instance(c, 2)
    inst.coords[1] = inst.coords[0]
    f = FlightModel(inst, c)
    ev = DeterministicEvaluator(inst, c, f)
    p, _ = optimize(inst, c, 0, [1], ev, np.random.default_rng(0))
    assert np.isfinite(ev(p))
