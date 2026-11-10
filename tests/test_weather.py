import numpy as np
import pytest
from tdw.models import load_config
from tdw.weather import WeatherEnvironment
from tdw.belief import BeliefTracker, posterior_given_label
from tdw.observation import ObservationManager


def test_delayed_bayes_and_propagation():
    c = load_config("configs/base.yaml")
    b = BeliefTracker(c)
    obs = ObservationManager(c, 42)
    prior = b.get(0)
    q = obs.start(2, 0., prior[2], 0)
    assert obs.deliver(2) == []
    assert np.allclose(b.get(2), prior)
    with pytest.raises(ValueError, match="arrived"):
        b.assimilate(q, 2, .85)
    report = obs.deliver(3)[0]
    b.assimilate(report, 3, .85)
    expected = posterior_given_label(prior[2], q["label"], .85)
    assert np.allclose(b.get(3)[2], expected)
    assert np.allclose(b.get(7)[2], expected @ np.array(c["weather"]["transition_matrix"]))
    assert 0 < b.get(3)[2].max() < 1


def test_budget_concurrency_duplicate_perfect_observation():
    c = load_config("configs/base.yaml")
    c["observation"]["max_queries"] = 1
    c["observation"]["correct_classification_probability"] = 1
    obs = ObservationManager(c, 0)
    q = obs.start(0, 0, [.55,.30,.15], 2)
    assert q["label"] == 2
    assert obs.start(0, 0, [.55,.30,.15], 0) is None
    assert obs.start(1, 0, [.55,.30,.15], 0) is None
    obs.deliver(4)
    assert obs.start(1, 4, [.55,.30,.15], 0) is None
    c["observation"]["max_queries"] = 0
    assert not ObservationManager(c, 0).can_start(0)


def test_truth_and_noise_reproducible():
    c = load_config("configs/base.yaml")
    a, b = WeatherEnvironment(c, 1), WeatherEnvironment(c, 1)
    assert a.fingerprint() == b.fingerprint()
    one, two = ObservationManager(c, 1), ObservationManager(c, 1)
    two.start(3, 0, [.55,.3,.15], 0)
    two.deliver(4)
    assert one.start(2, 5, [.55,.3,.15], 1)["label"] == two.start(2, 5, [.55,.3,.15], 1)["label"]
