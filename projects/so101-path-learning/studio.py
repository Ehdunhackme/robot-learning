"""Local SO-101 studio and closed-loop MuJoCo position-servo replay."""
import argparse
from functools import lru_cache, partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from threading import Lock
from urllib.parse import parse_qs,urlsplit
import webbrowser
import mujoco
import numpy as np
from arm import ROOT, Bench, FAMILIES
from policy import predict

SCENES=[("Low fence",700000,0),("Tall post",700007,1),("Overhead zone",700007,2)]
SHELF_SEED=720001
SHELF_EXAMPLES=[("Roof clearance",SHELF_SEED,110,75),
                ("Learned route succeeds",610002,180,102),
                ("Fixed route succeeds",610014,125,97)]
lock=Lock()

@lru_cache(maxsize=1)
def engine():
    b=Bench()
    b.m.opt.integrator=mujoco.mjtIntegrator.mjINT_IMPLICITFAST
    entry=json.loads((ROOT/"experiments/champion.json").read_text())
    return b,np.load(ROOT/f"experiments/{entry['tag']}/model.npz")

def execute(b,task,choice):
    trajectory=b.paths(task,1501)[choice]
    target=b.tip_at(task[6:12])
    preview=np.array([b.tip_at(q) for q in trajectory[::15]])
    mujoco.mj_resetData(b.m,b.d)
    b.set_fixture(task);b.d.qpos[:]=task[:6];b.d.ctrl[:]=task[:6]
    mujoco.mj_forward(b.m,b.d)
    frames=[];outcome="miss";collision=False;distance=0.;contact_point=None;contact_link=None
    last=b.d.site_xpos[b.tip].copy()
    for step in range(1851):
        if step:
            b.d.ctrl[:]=trajectory[min(step,1500)]
            mujoco.mj_step(b.m,b.d)
            pair=next((c for c in b.d.contact if c.dist<=0 and (
                (int(c.geom1) in b.arm_geoms and int(c.geom2) in b.obstacles|b.arm_geoms) or
                (int(c.geom2) in b.arm_geoms and int(c.geom1) in b.obstacles)
            )),None)
            collision=pair is not None
            if collision:
                contact_point=pair.pos.copy().tolist()
                link=pair.geom1 if int(pair.geom1) in b.arm_geoms else pair.geom2
                contact_link=b.m.body(b.m.geom_bodyid[link]).name
        if step%12==0 or collision or step==1850:
            mujoco.mj_kinematics(b.m,b.d)
            tip=b.d.site_xpos[b.tip].copy()
            distance+=float(np.linalg.norm(tip-last));last=tip
            error=float(np.linalg.norm(tip-target))
            poses=np.column_stack([b.d.xpos[1:8],b.d.xquat[1:8]])
            frames.append([round(step*b.m.opt.timestep,4),np.round(tip,6).tolist(),
                           np.round(poses,6).reshape(-1).tolist(),np.round(b.d.qpos,5).tolist()])
            if collision:
                outcome="contact";break
            if step>=1500 and error<=.008:
                outcome="reached";break
    return dict(choice=int(choice),outcome=outcome,frames=frames,seconds=frames[-1][0],
                error_mm=round(error*1000,1),distance_mm=round(distance*1000),
                contact_point=contact_point,contact_link=contact_link,preview=preview.round(6).tolist())

@lru_cache(maxsize=48)
def replay(seed,family,offset,angle):
    with lock:
        b,model=engine()
        task=b.draw_task(seed,family)
        task[13]+=offset/1000;task[6]+=np.deg2rad(angle)
        task[6]=np.clip(task[6],*b.m.jnt_range[0])
        b.set_fixture(task)
        if b.hits([task[:6],task[6:12]]):
            raise ValueError("A fixture intersects an endpoint. Reduce the offset or target angle.")
        selected=int(predict(model,task[None])[0])
        goal=b.tip_at(task[6:12]);start=b.tip_at(task[:6])
        learned=execute(b,task,selected)
        direct=execute(b,task,0) if selected else learned
        return dict(family=FAMILIES[family],seed=seed,fixture=task[12:18].tolist(),goal=goal.tolist(),
                    start=start.tolist(),learned=learned,direct=direct)

@lru_cache(maxsize=1)
def shelf_engine():
    from shelf import ShelfBench
    return ShelfBench(),np.load(ROOT/"experiments/shelf/model.npz")

@lru_cache(maxsize=32)
def shelf_replay(seed,width,depth):
    from shelf import PANELS,scene,rollout
    from shelf_policy import describe,choose
    with lock:
        b,model=shelf_engine()
        start,_,_,goal,boxes=scene(b,seed,width,depth)
        features,penalty,_=describe(b,seed,width,depth)
        selected=int(choose(model,features,penalty))
        learned=rollout(b,seed,width,depth,selected)
        direct=rollout(b,seed,width,depth,0) if selected else learned
        fixed_choice=json.loads((ROOT/"experiments/shelf/results.json").read_text())["fixed"]
        fixed=learned if selected==fixed_choice else rollout(b,seed,width,depth,fixed_choice)
        return dict(family="Shelf inspection",seed=seed,width=width,depth=depth,fixed=fixed,
                    panels=[dict(name=name,box=box.tolist()) for name,box in zip(PANELS,boxes)],
                    start=b.tip_at(start).tolist(),goal=goal.tolist(),learned=learned,direct=direct)


@lru_cache(maxsize=24)
def puck_replay(seed,distance):
    from puck import replay as push
    with lock:
        return push(seed,distance)

class Handler(SimpleHTTPRequestHandler):
    def send_json(self,body,code=200):
        payload=json.dumps(body,allow_nan=False,separators=(",",":")).encode()
        self.send_response(code);self.send_header("Content-Type","application/json")
        self.send_header("Content-Length",str(len(payload)));self.end_headers()
        try:self.wfile.write(payload)
        except (BrokenPipeError,ConnectionAbortedError,ConnectionResetError):pass
    def do_GET(self):
        url=urlsplit(self.path)
        if url.path=="/api/info":
            report=json.loads((ROOT/"experiments/final.json").read_text())
            shelf_report=json.loads((ROOT/"experiments/shelf/results.json").read_text())
            puck_report=json.loads((ROOT/"experiments/puck/results.json").read_text())
            return self.send_json(dict(scenes=SCENES+[("Shelf inspection",SHELF_SEED,3)],report=report,
                                       shelf=shelf_report,puck=puck_report,examples=SHELF_EXAMPLES))
        if url.path=="/api/run":
            query=parse_qs(url.query)
            try:
                value=lambda name,default: int(query.get(name,[default])[0])
                f=value("family",0);seed=value("seed",SHELF_SEED if f==3 else SCENES[0][1])
                if f in (6,7):
                    from gripper_courses import course_replay
                    transfer=f==6
                    gap=value("clearance",2)
                    level=value("rail" if transfer else "bias",52 if transfer else 8)
                    low,high=(38,62) if transfer else (0,10)
                    if not (0<=seed<=2**31-1 and 1<=gap<=4 and low<=level<=high):
                        raise ValueError("Choose settings within the displayed range.")
                    return self.send_json(course_replay("transfer" if transfer else "relay",seed,gap,level))
                if f==5:
                    from nut_assembly import assembly_replay
                    gap=value("clearance",3); error=value("error",5)
                    if not 0<=seed<=2**31-1 or not 1<=gap<=4 or not 0<=error<=8:
                        raise ValueError("Choose settings within the displayed range.")
                    return self.send_json(assembly_replay(seed,gap,error))
                if f==4:
                    distance=value("distance",60)
                    if not (0<=seed<=2**31-1 and 45<=distance<=77):
                        raise ValueError("Choose a push distance from 45 to 77 mm.")
                    return self.send_json(puck_replay(seed,distance))
                if f==3:
                    width=value("width",110);depth=value("depth",75)
                    if not 0<=seed<=2**31-1 or not 85<=width<=190 or not 45<=depth<=105:
                        raise ValueError("Choose a width between 85 and 190 mm and a depth between 45 and 105 mm.")
                    return self.send_json(shelf_replay(seed,width,depth))
                offset=value("offset",0);angle=value("angle",0)
                if not(0<=f<3 and 0<=seed<=2**31-1 and -55<=offset<=55 and -18<=angle<=18):
                    raise ValueError("Choose settings within the displayed range.")
                return self.send_json(replay(seed,f,offset,angle))
            except (ValueError,RuntimeError) as exc:return self.send_json({"error":str(exc)},400)
        return super().do_GET()

if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--port",type=int,default=8766);p.add_argument("--open",action="store_true")
    args=p.parse_args()
    app=ThreadingHTTPServer(("127.0.0.1",args.port),partial(Handler,directory=str(ROOT/"web")))
    url=f"http://127.0.0.1:{args.port}/"
    print(url,flush=True)
    if args.open:webbrowser.open(url)
    app.serve_forever()
