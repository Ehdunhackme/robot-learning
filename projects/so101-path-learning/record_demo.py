"""Render two synchronized MuJoCo executions from the interactive studio to H.264."""
import argparse
from pathlib import Path
import subprocess
import numpy as np
from PIL import Image,ImageDraw,ImageFont
import mujoco
from studio import SCENES,replay
from arm import Bench, ROOT

def font(size,bold=False):
    names=["segoeuib.ttf" if bold else "segoeui.ttf","DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"]
    for name in names:
        try:return ImageFont.truetype(name,size)
        except OSError:pass
    return ImageFont.load_default()

def marker(scene,p,r,color):
    g=scene.geoms[scene.ngeom]
    mujoco.mjv_initGeom(g,mujoco.mjtGeom.mjGEOM_SPHERE,np.array([r]*3),np.array(p),np.eye(3).ravel(),np.array(color,np.float32))
    scene.ngeom+=1

def line(scene,points,color):
    for a,b in zip(points[:-1],points[1:]):
        g=scene.geoms[scene.ngeom]
        mujoco.mjv_initGeom(g,mujoco.mjtGeom.mjGEOM_CAPSULE,np.ones(3),np.zeros(3),np.eye(3).ravel(),np.array(color,np.float32))
        mujoco.mjv_connector(g,mujoco.mjtGeom.mjGEOM_CAPSULE,.00165,np.array(a),np.array(b))
        scene.ngeom+=1

def main():
    b=Bench()
    width,height=640,420;fps=24
    b.m.vis.global_.offwidth=width;b.m.vis.global_.offheight=height
    b.m.geom_rgba[b.m.geom("table").id]=[.37,.44,.49,1]
    b.m.geom_rgba[b.fixture]=[.48,.49,.68,.70]
    b.m.vis.headlight.ambient[:]=.48;b.m.vis.headlight.diffuse[:]=.65
    renderer=mujoco.Renderer(b.m,width=width,height=height)
    opt=mujoco.MjvOption();opt.geomgroup[3]=0;opt.sitegroup[:]=0
    cam=mujoco.MjvCamera();cam.lookat[:]=[.17,0,.206];cam.distance=.86;cam.azimuth=130;cam.elevation=-21
    target=ROOT/"web/demo.mp4";target.parent.mkdir(exist_ok=True)
    video=subprocess.Popen(["ffmpeg","-hide_banner","-loglevel","error","-y","-f","rawvideo","-pix_fmt","rgb24",
        "-s","1280x580","-r",str(fps),"-i","-","-an","-c:v","libx264","-preset","fast","-crf","18",
        "-pix_fmt","yuv420p","-movflags","+faststart",str(target)],stdin=subprocess.PIPE)
    title,heading,small=font(28,True),font(20,True),font(17)
    try:
        for i,(family,seed,f) in enumerate(SCENES):
            run=replay(seed,f,0,0);task=b.draw_task(seed,f);b.set_fixture(task)
            for frame_idx in range(100):
                t=np.clip((frame_idx-7)/fps,0,3.7)
                frame=Image.new("RGB",(1280,580),"#22333f");draw=ImageDraw.Draw(frame)
                draw.text((22,10),"Arcbench",font=title,fill="#fff0cf")
                draw.text((190,18),"SO-101 motion study",font=small,fill="#d5e1e8")
                draw.text((960,15),f"{i+1} / 3     {family}",font=heading,fill="white")
                for j,(key,label,color) in enumerate([("direct","Direct interpolation",[.82,.35,.23,1]),("learned","Learned path",[.08,.72,.65,1])]):
                    plan=run[key];frames=plan["frames"]
                    idx=min(len(frames)-1,max(0,np.searchsorted([v[0] for v in frames],t,side="right")-1))
                    cur=frames[idx];b.pose(cur[3]);mujoco.mj_forward(b.m,b.d)
                    renderer.update_scene(b.d,camera=cam,scene_option=opt)
                    marker(renderer.scene,run["goal"],.008,[.65,.48,.91,1])
                    trail=[v[1] for v in frames[:idx+1:2]]+[cur[1]]
                    if len(trail)>1:line(renderer.scene,trail,color)
                    if idx==len(frames)-1 and plan["contact_point"]:
                        marker(renderer.scene,plan["contact_point"],.008,[1,.30,.12,1])
                    image=Image.fromarray(renderer.render())
                    x=j*width;frame.paste(image,(x,57))
                    draw.rectangle((x+16,69,x+230,103),fill="#253744")
                    draw.text((x+27,73),label,font=heading,fill="#f6f8f9")
                    name=({"reached":"Target reached","contact":"Fixture contact","miss":"Missed target"}[plan["outcome"]]
                          if idx==len(frames)-1 else "Moving")
                    draw.text((x+22,491),name,font=heading,fill="#8ee2cd" if name=="Target reached" else "#fde1c8")
                    draw.text((x+22,526),f"{cur[0]:.2f} s    ·    {1000*np.linalg.norm(np.array(cur[1])-run['goal']):.1f} mm to target",
                              font=small,fill="#d5e1e8")
                draw.line((640,57,640,558),fill="#8c9da5",width=1)
                video.stdin.write(frame.tobytes())
    finally:
        video.stdin.close();returncode=video.wait();renderer.close()
    if returncode:raise RuntimeError("ffmpeg failed")
    print(target)
if __name__=="__main__":main()

