"""Replay both frozen controllers on matched layouts with different sliding friction."""
import argparse
from concurrent.futures import ProcessPoolExecutor
import json
import numpy as np
from puck import WEIGHTS, engine, layout, predict, simulate

CONDITIONS = (.16, .48, .80)


def evaluate(seed):
    bench, model = engine()
    start, goal = layout(seed)
    offset = predict(model, start, goal)
    pad, disk = bench.m.geom("pad").id, bench.puck
    output = []
    for friction in CONDITIONS:
        # The contacting surfaces share this sliding coefficient. Paddle friction stays 1.
        bench.m.geom_friction[[pad, disk], 0] = friction
        for method, action in (("straight", (0., 0.)), ("learned", offset)):
            run = simulate(bench, start, goal, action, detailed=False)
            output.append(dict(seed=seed, friction=friction, method=method,
                               error_mm=run["error_mm"], outcome=run["outcome"]))
    return output


def main(workers):
    original = json.loads(WEIGHTS.with_name("episodes.json").read_text())
    with ProcessPoolExecutor(workers) as pool:
        rows = [r for group in pool.map(evaluate, [r["seed"] for r in original]) for r in group]
    old = {r["seed"]:r for r in original}
    for r in rows:
        if r["friction"] == .48:
            baseline = old[r["seed"]][r["method"]]
            if baseline["error_mm"] != r["error_mm"] or baseline["outcome"] != r["outcome"]:
                raise ValueError(f"Nominal replay disagrees on layout {r['seed']}")
    out = WEIGHTS.with_name("transfer.json")
    out.write_bytes((json.dumps(rows,separators=(",",":"))+"\n").encode())
    for mu in CONDITIONS:
        for method in ["straight","learned"]:
            cases = [r for r in rows if r["friction"] == mu and r["method"] == method]
            print(mu,method,sum(r["outcome"]=="reached" for r in cases),round(np.mean([r["error_mm"] for r in cases]),2))


if __name__ == "__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--workers",type=int,default=6)
    main(parser.parse_args().workers)
