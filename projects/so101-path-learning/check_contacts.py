"""Cross-check collision queries against individual geom distances on varying boxes."""
import mujoco
import numpy as np
from arm import Bench

if __name__ == "__main__":
    b=Bench()
    zero=np.zeros(6)
    rng=np.random.default_rng(315)
    errors=0
    for i in range(1000):
        task=b.draw_task(i)
        q=b.paths(task,41)[rng.integers(13),rng.integers(41)]
        b.pose(q)
        broad=b.contact()
        direct=any(mujoco.mj_geomDistance(b.m,b.d,g,o,.002,zero)<0
                   for g in b.arm_geoms for o in b.obstacles)
        mujoco.mj_forward(b.m,b.d)
        forward=b.contact()
        if broad!=forward or (direct and not broad):
            errors+=1
    print("Mismatch count",errors)
    assert errors==0

