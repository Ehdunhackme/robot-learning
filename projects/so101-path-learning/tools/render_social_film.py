"""Cut the four recorded MuJoCo comparisons into a square, silent film for X.

Run with Python, Pillow and ffmpeg. The source films and mask are in article/public.
"""

import base64
import json
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "article/public/assets/writings/arcbench"
OUTPUT = ROOT / "media/so101-x-demo.mp4"
PAPER = "#17191b"
WHITE = "#f4f4f1"
MUTED = "#b8bbb9"
FPS = 20


def font(size, bold=False):
    names = ("seguisb.ttf", "DejaVuSans-Bold.ttf") if bold else ("segoeui.ttf", "DejaVuSans.ttf")
    for name in names:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    raise RuntimeError("Install Segoe UI or DejaVu Sans to render the captions.")


def add_mask(layer):
    observation = json.loads((ASSETS / "replay/pickup.json").read_text())["observation"]
    size = observation["size"]
    mask = Image.frombytes("P", (size, size), base64.b64decode(observation["mask"]))
    mask.putpalette([38, 42, 44, 246, 179, 104, 112, 149, 242] + [0] * 759)
    layer.paste(mask.convert("RGB").resize((164, 164), Image.Resampling.NEAREST), (850, 193))
    draw = ImageDraw.Draw(layer)
    draw.rectangle((850, 357, 1013, 393), fill=PAPER)
    draw.text((932, 362), f"{size} × {size} input", font=font(21), fill=WHITE, anchor="mt")


def caption_layer(task, title, headline, note):
    layer = Image.new("RGBA", (1080, 1080), PAPER)
    draw = ImageDraw.Draw(layer)
    draw.text((40, 32), "SO-101   /   Supervised learning in MuJoCo", font=font(28, True), fill=MUTED, anchor="lt")
    draw.text((1040, 32), "Dun Li Chan", font=font(28), fill=MUTED, anchor="rt")
    draw.text((37, 84), title, font=font(61, True), fill=WHITE, anchor="lt")
    if task == "placement":
        for x, label in [(40, "Average peg pose"), (544, "Pose from the image")]:
            draw.rectangle((x, 169, x + 495, 231), fill="#e8e9e7")
            draw.text((x + 20, 185), label, font=font(30, True), fill=PAPER, anchor="lt")
            draw.rectangle((x, 232, x + 495, 881), fill=(0, 0, 0, 0))
    else:
        draw.rectangle((40, 168, 1039, 881), fill=(0, 0, 0, 0))
    if task == "pickup":
        add_mask(layer)
    draw.text((40, 916), headline, font=font(43, True), fill=WHITE, anchor="lt")
    draw.text((40, 991), note, font=font(33), fill=MUTED, anchor="lt")
    return layer


def results_layer():
    layer = Image.new("RGBA", (1080, 1080))
    draw = ImageDraw.Draw(layer)
    draw.rectangle((0, 882, 1079, 1079), fill=PAPER)
    for x, score in [(40, "2 / 32 seated"), (544, "32 / 32 seated")]:
        draw.text((x, 913), score, font=font(48, True), fill=WHITE, anchor="lt")
    draw.text((40, 991), "Successful placements on the same 32 held-out layouts.", font=font(33), fill=MUTED, anchor="lt")
    return layer


def ffmpeg(*args):
    subprocess.run(["ffmpeg", "-nostdin", "-loglevel", "error", "-y", *map(str, args)], check=True)


def cut(temp, task, title, headline, note, start, duration, crop=None, speed=1):
    layer = temp / f"{task}.png"
    caption_layer(task, title, headline, note).save(layer)
    output = temp / f"{task}.mp4"
    inputs = ["-ss", start, "-i", ASSETS / f"{task}.mp4", "-i", layer]
    if crop:
        graph = (f"[0:v]crop={crop},scale=1000:714:flags=lanczos,setsar=1,"
                 f"setpts=(PTS-STARTPTS)/{speed},fps={FPS},pad=1080:1080:40:168[stage];"
                 "[stage][1:v]overlay")
    else:
        results = temp / "results.png"
        results_layer().save(results)
        inputs.extend(["-i", results])
        # Identical close-ups keep the nut and peg at the same scale on both sides.
        graph = ("[0:v]split[l][r];[l]crop=372:488:170:105,scale=496:650[left];"
                 "[r]crop=372:488:890:105,scale=496:650[right];"
                 "[left][right]xstack=inputs=2:layout=0_0|504_0:fill=black,"
                 "setsar=1,pad=1080:1080:40:232,tpad=stop_mode=clone:stop_duration=2[stage];"
                 "[stage][1:v]overlay[labeled];[labeled][2:v]overlay=enable='gte(t,6.5)'")
    ffmpeg(*inputs, "-filter_complex", graph, "-t", duration, "-an", "-r", FPS,
           "-c:v", "libx264", "-crf", 17, "-preset", "fast", "-pix_fmt", "yuv420p",
           "-video_track_timescale", 20000, output)
    return output


def main():
    OUTPUT.parent.mkdir(exist_ok=True)
    with TemporaryDirectory(dir=OUTPUT.parent) as directory:
        temp = Path(directory)
        chapters = [
            cut(temp, "reach", "Reaching around an obstacle", "Learned routes reached 87 of 96 targets",
                "A direct reach worked on 18 of the same layouts.", 0.7, 3.25, "720:514:720:78"),
            cut(temp, "shelf", "Reaching into a shelf", "0.75 mm between the jaw and the roof",
                "The arm reaches in, holds its position and comes back out.", 0.65, 6.25, "718:512:720:102", 1.2),
            cut(temp, "pickup", "Picking up the nut", "A 51 mm lift",
                "The nut’s silhouette tells the arm where to close its jaws.", 0.6, 4.3, "530:378:820:180"),
            cut(temp, "placement", "Fitting the nut onto a peg", "Both arms use the same grasp.",
                "The square hole leaves 2 mm on each side of the peg.", 0.6, 10.9),
        ]
        playlist = temp / "cuts.txt"
        playlist.write_text("".join(f"file '{clip.name}'\n" for clip in chapters), encoding="utf-8")
        draft = temp / "film.mp4"
        ffmpeg("-f", "concat", "-safe", 0, "-i", playlist, "-c", "copy", "-movflags", "+faststart", draft)
        draft.replace(OUTPUT)
    print(OUTPUT)


if __name__ == "__main__":
    main()
