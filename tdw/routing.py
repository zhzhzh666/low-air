"""Joint route/assignment/launch/recovery local search, without a commercial solver."""
import numpy as np
from .models import Plan, Sortie
from .instance import road_km
from .scheduler import validate_plan


def initial_route(instance, config, current, remaining):
    todo, route = set(remaining), [current]
    while todo:
        node = min(todo, key=lambda j: (road_km(instance, config, route[-1], j), j))
        route.append(node)
        todo.remove(node)
    return route + [instance.end]


def optimize(instance, config, current, remaining, evaluator, rng, allow_drone=True):
    best = Plan(initial_route(instance, config, current, remaining))
    best_score = evaluator(best)
    moves = {"relocate": 0, "swap": 0, "2opt": 0, "truck_to_drone": 0, "drone_to_truck": 0, "anchors": 0}
    for it in range(config["planning"]["local_search_iterations"]):
        candidate = best.copy()
        mode = it % 6
        internal = candidate.route[1:-1]
        if mode < 3 and len(internal) >= 2:
            i, k = sorted(rng.choice(np.arange(1, len(candidate.route)-1), 2, replace=False).tolist())
            if mode == 0:
                node = candidate.route.pop(i)
                candidate.route.insert(k, node)
            elif mode == 1:
                candidate.route[i], candidate.route[k] = candidate.route[k], candidate.route[i]
            else:
                candidate.route[i:k+1] = reversed(candidate.route[i:k+1])
        elif mode == 3 and allow_drone and internal:
            eligible = [j for j in internal if instance.customers[j].weight <= config["drone"]["capacity_kg"]]
            if not eligible:
                continue
            j = int(rng.choice(eligible))
            old_index = candidate.route.index(j)
            candidate.route.remove(j)
            # Local anchor enumeration through repeated proposals, can span >1 edge.
            i = max(0, min(len(candidate.route)-2, old_index-1 + int(rng.integers(-1, 2))))
            k = min(len(candidate.route)-1, i + int(rng.integers(1, 4)))
            candidate.sorties.append(Sortie(candidate.route[i], j, candidate.route[k]))
        elif mode == 4 and candidate.sorties:
            a = candidate.sorties.pop(int(rng.integers(len(candidate.sorties))))
            k = int(rng.integers(1, len(candidate.route)))
            candidate.route.insert(k, a.customer)
        elif mode == 5 and candidate.sorties:
            ix = int(rng.integers(len(candidate.sorties)))
            a = candidate.sorties[ix]
            i = int(rng.integers(len(candidate.route)-1))
            k = int(rng.integers(i+1, len(candidate.route)))
            candidate.sorties[ix] = Sortie(candidate.route[i], a.customer, candidate.route[k])
        else:
            continue
        try:
            validate_plan(candidate, remaining, current, instance, config)
        except ValueError:
            continue
        score = evaluator(candidate)
        if score < best_score - 1e-8:
            best, best_score = candidate, score
            moves[list(moves)[mode]] += 1
    # Independent held-out sample gate on the returned plan, remove unsafe sorties.
    if hasattr(evaluator, "certify_plan") and not evaluator.certify_plan(best):
        # Conservative, feasible fallback. Re-certification is independent of search.
        for a in best.sorties[:]:
            best.sorties.remove(a)
            pos = best.route.index(a.recover)
            best.route.insert(pos, a.customer)
    validate_plan(best, remaining, current, instance, config)
    return best, moves
