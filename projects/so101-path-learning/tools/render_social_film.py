"""Render the X film at 1920 x 1080 with the planned paths for each controller.

Requires the project's simulator dependencies, Playwright with Chromium and ffmpeg.
"""

import base64
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
from urllib.parse import urlsplit

from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from runs import replay

REPLAYS = ROOT / "article/public/assets/writings/arcbench/replay"
OUTPUT = ROOT / "media/so101-x-demo.mp4"
FPS = 20
OBSTACLE_LAYOUTS = {
    "fence": (700011, 0),
    "post": (700007, 1),
    "overhead": (700033, 2),
}
CHAPTERS = [
    ("fence", "Reach past the low fence", ["learned"], 1.0),
    ("post", "Reach around the tall post", ["learned"], 1.0),
    ("overhead", "Avoid the overhead block", ["learned"], 1.0),
    ("shelf", "Reach inside the shelf and return", ["learned"], 1.2),
    ("placement", "Fit the nut onto the peg", ["direct", "learned"], 1.0),
]

PLAYER = """<!doctype html><meta charset=utf-8>
<style>*{box-sizing:border-box}body{margin:0}#view{height:1080px}.surface-note{display:none}</style>
<script type="importmap">{"imports":{"three":"./vendor/three.module.min.js"}}</script>
<div id="view"></div>
<script type="module">
import {buildScene} from "./scene.js";
const container=document.querySelector("#view"), view=await buildScene(container,{pathRadius:0.00145});
const film=document.createElement("canvas");film.width=1920;film.height=1080;
const ctx=film.getContext("2d");
let run, modes, title;
window.loadChapter=async ([data, description, methods])=>{
  run=data;modes=methods;title=description;container.style.width=(film.width/modes.length)+"px";
  await new Promise(done=>requestAnimationFrame(()=>requestAnimationFrame(done)));
  view.setup(run);view.cameraView("work",run.fixture ? 0.84 : 1);view.paths(true);
  return Math.max(...modes.map(mode=>run[mode].seconds));
};
window.frameAt=time=>{
  for(const [side,mode] of modes.entries()){
    view.showRoute(mode);
    const frames=run[mode].frames;
    let i=frames.findIndex(f=>f[0]>time);
    if(i<0)i=frames.length;
    const a=frames[Math.max(0,i-1)], b=frames[Math.min(i,frames.length-1)];
    const fraction=b[0]>a[0]?Math.max(0,(time-a[0])/(b[0]-a[0])):0;
    view.pose(a,b,fraction);view.render();
    ctx.drawImage(container.querySelector("canvas"),side*container.clientWidth,0);
  }
  ctx.font='600 46px "Segoe UI", Arial, sans-serif';ctx.fillStyle="#202326";
  ctx.textBaseline="top";ctx.fillText(title,50,40);
  return film.toDataURL("image/jpeg",0.96).split(",")[1];
};
</script>"""


def serve(route):
    path = urlsplit(route.request.url).path.lstrip("/")
    if path == "film.html":
        route.fulfill(content_type="text/html", body=PLAYER)
        return
    asset = (REPLAYS / path).resolve()
    if asset.is_relative_to(REPLAYS) and asset.is_file():
        media_types = {".js": "text/javascript", ".json": "application/json"}
        route.fulfill(path=asset, content_type=media_types.get(asset.suffix, "application/octet-stream"))
    else:
        route.fulfill(status=404, body="Missing replay asset")


def main():
    OUTPUT.parent.mkdir(exist_ok=True)
    with TemporaryDirectory(dir=OUTPUT.parent) as directory, sync_playwright() as pw:
        draft = Path(directory) / "film.mp4"
        gpu_args = ["--enable-gpu", "--enable-unsafe-swiftshader"]
        if sys.platform == "win32":
            gpu_args.extend(["--use-gl=angle", "--use-angle=d3d11"])
        browser = pw.chromium.launch(args=gpu_args)
        page = browser.new_page(viewport={"width": 1920, "height": 1080}, device_scale_factor=1)
        page.route("http://replay.local/**", serve)
        page.goto("http://replay.local/film.html")
        page.wait_for_function("typeof frameAt === 'function'")
        command = ["ffmpeg", "-nostdin", "-v", "error", "-f", "image2pipe", "-framerate", str(FPS),
                   "-c:v", "mjpeg", "-i", "-", "-an", "-c:v", "libx264", "-crf", "18",
                   "-preset", "fast", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(draft)]
        with subprocess.Popen(command, stdin=subprocess.PIPE) as encoder:
            try:
                for task, title, modes, speed in CHAPTERS:
                    if task in OBSTACLE_LAYOUTS:
                        seed, family = OBSTACLE_LAYOUTS[task]
                        run = replay(seed, family, 0, 0)
                    else:
                        run = json.loads((REPLAYS / f"{task}.json").read_text(encoding="utf-8"))
                    for mode in modes:
                        if len(run[mode].get("preview", [])) < 2:
                            raise ValueError(f"Missing planned path for {task}/{mode}")
                    duration = page.evaluate("args=>loadChapter(args)", [run, title, modes])
                    count = round(duration * FPS / speed)
                    for i in range(count + 1):
                        frame = page.evaluate("t=>frameAt(t)", duration * i / count)
                        pixels = base64.b64decode(frame)
                        encoder.stdin.write(pixels)
                    encoder.stdin.write(pixels * (FPS if task == "placement" else FPS // 3))
                    print(task, flush=True)
            finally:
                encoder.stdin.close()
            if encoder.wait():
                raise RuntimeError("ffmpeg could not encode the film")
        browser.close()
        draft.replace(OUTPUT)


if __name__ == "__main__":
    main()
