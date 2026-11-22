"""Render the X film at 1920 x 1080 from the three featured MuJoCo replays.

Requires Playwright with Chromium and ffmpeg. All replay data and meshes are local.
"""

import base64
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory
from urllib.parse import urlsplit

from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[1]
REPLAYS = ROOT / "article/public/assets/writings/arcbench/replay"
OUTPUT = ROOT / "media/so101-x-demo.mp4"
FPS = 20
CHAPTERS = [
    ("reach", "Reach around the obstacle", ["learned"], 1.0),
    ("shelf", "Reach inside the shelf and return", ["learned"], 1.2),
    ("placement", "Fit the nut onto the peg", ["direct", "learned"], 1.0),
]

PLAYER = """<!doctype html><meta charset=utf-8>
<style>*{box-sizing:border-box}body{margin:0}#view{height:1080px}.surface-note{display:none}</style>
<script type="importmap">{"imports":{"three":"./vendor/three.module.min.js"}}</script>
<div id="view"></div>
<script type="module">
import {buildScene} from "./scene.js";
const container=document.querySelector("#view"), view=await buildScene(container);
const film=document.createElement("canvas");film.width=1920;film.height=1080;
const ctx=film.getContext("2d");
let run, modes, title;
window.loadChapter=async ([key, description, methods])=>{
  run=await (await fetch("./"+key+".json")).json();
  modes=methods;title=description;container.style.width=(film.width/modes.length)+"px";
  await new Promise(done=>requestAnimationFrame(()=>requestAnimationFrame(done)));
  view.setup(run);view.reset();view.paths(false);
  return Math.max(...modes.map(mode=>run[mode].seconds));
};
window.frameAt=time=>{
  for(const [side,mode] of modes.entries()){
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
        browser = pw.chromium.launch(args=["--enable-unsafe-swiftshader"])
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
                    duration = page.evaluate("args=>loadChapter(args)", [task, title, modes])
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
