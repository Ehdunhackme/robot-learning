"""Final scene-level evaluation following model selection on validation cost."""
from concurrent.futures import ProcessPoolExecutor
import csv
import hashlib
import json
import numpy as np
from arm import ROOT, Bench
from kinematics import sparse_features
from policy import predict, length_penalty
from prepare import path_cost, score

robot=None
def servo_pair(job):
    global robot
    if robot is None:
        import mujoco
        robot=Bench();robot.m.opt.integrator=mujoco.mjtIntegrator.mjINT_IMPLICITFAST
    from studio import execute
    task,selected=job
    rows=[]
    for choice in (0,int(selected)):
        r=execute(robot,task,choice)
        rows.append({k:r[k] for k in ("outcome","error_mm","seconds","distance_mm","choice")})
    return rows

def main():
    folder=ROOT/"experiments"
    best=json.loads((folder/"champion.json").read_text())["tag"]
    test=np.load(ROOT/"data/test.npz");val=np.load(ROOT/"data/validation.npz")
    x=test["tasks"];valid=test["clear"];length=test["length"];n=len(x)
    cost=path_cost(valid,length)
    fixed=path_cost(val["clear"],val["length"]).mean(0).argmin()
    raw=predict(np.load(folder/"baseline/model.npz"),x)
    selected=predict(np.load(folder/best/"model.npz"),x)
    # An additional geometric comparator chooses the shortest apparently clear candidate.
    approx=sparse_features(x);count=valid.shape[1]
    margin=np.minimum(approx[:,:5*count].reshape(n,count,5).min(2),approx[:,5*count:])
    heuristic=np.where(margin>=0,length_penalty(x),1-margin).argmin(1)
    picks={"Direct joint path":np.zeros(n,int),"Fixed detour":np.full(n,fixed),"Sparse geometry rule":heuristic,
           "First learned model":raw,"Selected model":selected,"Candidate oracle":cost.argmin(1)}
    stats={label:score(ids,valid,length) for label,ids in picks.items()}
    for label,ids in picks.items():stats[label]["clear_count"]=int(valid[np.arange(n),ids].sum())
    rng=np.random.default_rng(6601)
    diff=cost[np.arange(n),raw]-cost[np.arange(n),selected]
    interval=np.percentile(diff[rng.integers(n,size=(5000,n))].mean(1),[2.5,97.5]).tolist()
    with ProcessPoolExecutor(8) as executor:
        servo=list(executor.map(servo_pair,zip(x[:96],selected[:96]),chunksize=4))
    dynamics={}
    for i,label in enumerate(("Direct joint path","Selected model")):
        outcomes=[example[i]["outcome"] for example in servo]
        dynamics[label]={k:outcomes.count(k) for k in ("contact","miss","reached")}
    with (folder/"results.tsv").open() as f:trials=list(csv.DictReader(f,delimiter="\t"))
    for trial in trials:
        config=json.loads((folder/trial["trial"]/"result.json").read_text())
        trial["mean_joint_length_rad"]=config["validation"]["mean_joint_length_rad"]
    summary=dict(best=best,train=4096,validation=640,test=n,fixed_path=int(fixed),metrics=stats,trials=trials,
                 paired_cost_reduction_95=interval,servo=dynamics,servo_tasks=96,
                 hashes={s:hashlib.sha256((ROOT/f"data/{s}.npz").read_bytes()).hexdigest()
                         for s in ("train","validation","test")})
    (folder/"final.json").write_text(json.dumps(summary,indent=2))
    (folder/"servo.json").write_text(json.dumps(servo))
    np.savez_compressed(folder/"decisions.npz",seeds=test["seeds"],**picks)
    print(json.dumps(summary))
if __name__=="__main__":main()

