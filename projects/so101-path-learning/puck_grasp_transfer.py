"""Repeat the fixed-paddle test layouts with a loose paddle in the jaws."""
from concurrent.futures import ProcessPoolExecutor
import json

from puck import WEIGHTS, engine, layout, predict, simulate


def trial(seed):
    bench, model = engine(held=True)
    start, goal = layout(seed)
    result = {"seed": seed}
    for method, offset in (("straight", (0., 0.)), ("learned", predict(model, start, goal))):
        run = simulate(bench, start, goal, offset, detailed=False)
        result[method] = {k: run[k] for k in ("outcome", "error_mm", "push_steps", "gripped_push_steps")}
    return result


if __name__ == "__main__":
    seeds = [row["seed"] for row in json.loads(WEIGHTS.with_name("episodes.json").read_text())]
    with ProcessPoolExecutor(4) as pool:
        results = list(pool.map(trial, seeds))
    bench, model = engine(held=True)
    start, goal = layout(2402, 60)
    offset = predict(model, start, goal)
    closed = simulate(bench, start, goal, offset, detailed=False)
    released = simulate(bench, start, goal, offset, detailed=False, close=False)
    assert closed["gripped_push_steps"] == closed["push_steps"] > 0
    assert released["gripped_push_steps"] == 0 and released["outcome"] == "contact"
    report = dict(layouts=results, release_control=dict(seed=2402, distance_mm=60,
                  closed_contact_steps=closed["gripped_push_steps"], open_contact_steps=released["gripped_push_steps"],
                  dropped_at_s=released["seconds"]))
    WEIGHTS.with_name("grasp-transfer.json").write_text(json.dumps(report, separators=(",", ":")) + "\n")
    print({method: sum(r[method]["outcome"] == "reached" for r in results) for method in ("straight","learned")})
