"""Render the website's comparison films from the live MuJoCo studio. Requires Playwright, Pillow, ffmpeg."""
import argparse
import base64
from io import BytesIO
from pathlib import Path
import subprocess

from PIL import Image, ImageDraw
from playwright.sync_api import sync_playwright
from record_demo import font

ROOT = Path(__file__).resolve().parent
WIDTH, HEIGHT, FPS = 720, 720, 20
SCENES = {
    "transfer": [(6, 2040)], "relay": [(7, 2026)],
    "assembly": [(5, 2026)],
    "puck": [(4, 2402)], "shelf": [(3, 720001)],
    "reach": [(0, 700000), (1, 700007), (2, 700007)],
}

HTML = """<!doctype html><meta charset=utf-8><style>
*{box-sizing:border-box}body{margin:0}#stage{position:relative;width:720px;height:720px}
canvas{display:block}.surface-note{display:none}</style><div id="stage"></div>
<script type="importmap">{"imports":{"three":"/vendor/three.module.min.js"}}</script>
<script type="module">
import {buildScene} from '/scene.js';
const stage=document.querySelector('#stage'), view=await buildScene(stage);
window.loadRun=async(family,seed)=>{
 const response=await fetch('/api/run?family='+family+'&seed='+seed);
 if(!response.ok)throw Error(await response.text());
 window.run=await response.json();view.setup(run);view.reset();view.paths(false);
 return run.assembly?run.scripted.seconds:Math.max(run.direct.seconds,run.learned.seconds);
};
window.shot=(mode,time)=>{
 const path=run[mode], frames=path.frames;
 let index=frames.length-1;
 while(index>0 && frames[index][0]>time)index--;
 view.pose(frames[index]);view.render();
 return stage.querySelector('canvas').toDataURL('image/jpeg',.96).split(',')[1];
};
</script>"""

def image(page, mode, time):
    encoded = page.evaluate("([mode,t])=>shot(mode,t)", [mode,time])
    return Image.open(BytesIO(base64.b64decode(encoded))).convert("RGB")

def record(page, task, output):
    video = output / (task + ".mp4")
    draft = video.with_suffix(".tmp.mp4")
    cmd = ["ffmpeg","-loglevel","error","-y","-f","rawvideo","-pix_fmt","rgb24",
           "-s",f"{WIDTH*2}x{HEIGHT}","-r",str(FPS),"-i","-","-an","-c:v","libx264",
           "-crf","18","-preset","fast","-pix_fmt","yuv420p","-movflags","+faststart",str(draft)]
    title = font(24,True)
    modes=("nominal","scripted") if task in ("assembly","transfer","relay") else ("direct","learned")
    with subprocess.Popen(cmd,stdin=subprocess.PIPE) as enc:
        try:
            for section,(family,seed) in enumerate(SCENES[task]):
                length = page.evaluate("([f,s])=>loadRun(f,s)",[family,seed])
                labels = ("Straight push","Learned push") if task=="puck" else ("Direct reach","Learned route")
                if task=="assembly": labels=("Initial peg estimate","Recheck peg position")
                if task=="transfer": labels=("Low carry","Clear the rail")
                if task=="relay": labels=("Estimated regrasp","Measured regrasp")
                for idx in range(round(length*FPS)+1):
                    frame=Image.new("RGB",(WIDTH*2,HEIGHT))
                    draw=ImageDraw.Draw(frame)
                    for side,mode in enumerate(modes):
                        pic=image(page,mode,idx/FPS)
                        frame.paste(pic,(WIDTH*side,0))
                        draw.text((WIDTH*side+22,18),labels[side],font=title,fill="#272b30")
                        if task=="reach":
                            draw.text((WIDTH*side+22,52),("Low fence","Tall post","Overhead zone")[section],
                                      font=font(18),fill="#555b62")
                        if task=="assembly" and side==1 and idx==round(length*FPS*.47):
                            pic.crop((0,85,720,463)).resize((1200,630),Image.Resampling.LANCZOS).save(output/"social.jpg",quality=91)
                    draw.line((WIDTH-1,0,WIDTH-1,HEIGHT),fill="#aeb2b6",width=1)
                    if not section and idx==round(length*FPS*.47):
                        frame.save(output/(task+".webp"),quality=89)
                    pixels=frame.tobytes()
                    for _ in range(12 if idx in (0,round(length*FPS)) else 1):
                        enc.stdin.write(pixels)
                print(task,seed,"rendered",flush=True)
        finally:
            enc.stdin.close()
        if enc.wait(): raise RuntimeError("ffmpeg could not encode "+task)
    draft.replace(video)

if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--studio",default="http://127.0.0.1:8766")
    parser.add_argument("--out",type=Path,required=True)
    parser.add_argument("--task",choices=SCENES)
    args=parser.parse_args()
    args.out.mkdir(parents=True,exist_ok=True)
    with sync_playwright() as pw:
        browser=pw.chromium.launch(args=["--enable-unsafe-swiftshader"])
        page=browser.new_page(viewport={"width":WIDTH,"height":HEIGHT},device_scale_factor=1)
        page.route("**/record-frame",lambda route: route.fulfill(body=HTML,content_type="text/html"))
        page.goto(args.studio.rstrip("/")+"/record-frame")
        page.wait_for_function("typeof shot === 'function'")
        for task in ([args.task] if args.task else SCENES): record(page,task,args.out)
        browser.close()
