"""Record both browser replays at the same simulation times with the local studio running."""
from io import BytesIO
from pathlib import Path
import subprocess

from PIL import Image, ImageDraw
from playwright.sync_api import sync_playwright

from record_demo import font

ROOT = Path(__file__).resolve().parent
FPS = 20


def main():
    with sync_playwright() as pw:
        browser = pw.chromium.launch(args=["--enable-unsafe-swiftshader"])
        page = browser.new_page(viewport={"width": 780, "height": 820}, reduced_motion="reduce")
        page.goto("http://127.0.0.1:8766/?task=puck")
        page.wait_for_function("!document.getElementById('play').disabled")
        page.add_style_tag(content=".shell{width:642px}#viewport{height:350px!important;width:640px}")
        viewport = page.locator("#viewport")
        total = float(page.locator("#duration").inner_text().split()[1])
        frames = []
        for mode in ("direct", "learned"):
            page.select_option("#controller", mode)
            shots = []
            for k in range(round(total*FPS)+1):
                tick = min(1000,round(1000*k/(total*FPS)))
                page.locator("#scrub").fill(str(tick))
                # The viewer limits WebGL redraw frequency; allow the requested pose to paint.
                page.wait_for_timeout(55)
                shots.append((viewport.screenshot(),page.locator("#outcome").text_content()))
            frames.append(shots)
        browser.close()
    cmd=["ffmpeg","-hide_banner","-loglevel","error","-y","-f","rawvideo","-pix_fmt","rgb24",
         "-s","1280x464","-r",str(FPS),"-i","-","-an","-c:v","libx264","-crf","18","-pix_fmt","yuv420p",
         "-movflags","+faststart",str(ROOT/"web/puck.mp4")]
    title,small=font(22,True),font(17)
    with subprocess.Popen(cmd,stdin=subprocess.PIPE) as proc:
        try:
            for n in range(len(frames[0])+28):
                i=min(len(frames[0])-1,max(0,n-5))
                canvas=Image.new("RGB",(1280,464),"#fafbf9")
                d=ImageDraw.Draw(canvas)
                for side,name in enumerate(("Straight push","Learned push")):
                    x=640*side
                    image,status=frames[side][i]
                    canvas.paste(Image.open(BytesIO(image)).convert("RGB"),(x,53))
                    d.text((x+19,13),name,font=title,fill="#243c30")
                    d.text((x+19,418),status,font=small,fill="#213e30")
                d.line((639,0,639,464),fill="#cbd5ce",width=1)
                proc.stdin.write(canvas.tobytes())
        finally:
            proc.stdin.close()
        if proc.wait():
            raise RuntimeError("ffmpeg could not encode the recorded frames.")


if __name__=="__main__":
    main()
