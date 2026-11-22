"""Cut the four recorded MuJoCo comparisons into a square, silent film for X.

Run with Python, Pillow and ffmpeg. The source films are in article/public.
"""

from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "article/public/assets/writings/arcbench"
OUTPUT = ROOT / "media/so101-x-demo.mp4"
FPS = 20


def title_font():
    for name in ("seguisb.ttf", "DejaVuSans-Bold.ttf"):
        try:
            return ImageFont.truetype(name, 46)
        except OSError:
            continue
    raise RuntimeError("Install Segoe UI or DejaVu Sans to render the captions.")


def ffmpeg(*args):
    subprocess.run(["ffmpeg", "-nostdin", "-loglevel", "error", "-y", *map(str, args)], check=True)


def cut(temp, task, title, start, duration, crop=None, speed=1):
    header = Image.new("RGB", (1080, 104), "#17191b")
    ImageDraw.Draw(header).text((40, 52), title, font=title_font(), fill="#f4f4f1", anchor="lm")
    header_file = temp / f"{task}.png"
    header.save(header_file)
    output = temp / f"{task}.mp4"
    if crop:
        graph = (f"[0:v]crop={crop},scale=1080:976:flags=lanczos,setsar=1,"
                 f"setpts=(PTS-STARTPTS)/{speed},fps={FPS}[scene];")
    else:
        # Identical close-ups keep the nut and peg at the same scale on both sides.
        graph = ("[0:v]split[l][r];[l]crop=326:592:218:90,scale=538:976[left];"
                 "[r]crop=326:592:938:90,scale=538:976[right];"
                 "[left][right]xstack=inputs=2:layout=0_0|542_0:fill=0x17191b,"
                 "setsar=1,tpad=stop_mode=clone:stop_duration=2[scene];")
    graph += "[scene]pad=1080:1080:0:104[stage];[stage][1:v]overlay=0:0"
    ffmpeg("-ss", start, "-i", ASSETS / f"{task}.mp4", "-i", header_file,
           "-filter_complex", graph, "-t", duration, "-an", "-r", FPS,
           "-c:v", "libx264", "-crf", 17, "-preset", "fast", "-pix_fmt", "yuv420p",
           "-video_track_timescale", 20000, output)
    return output


def main():
    OUTPUT.parent.mkdir(exist_ok=True)
    with TemporaryDirectory(dir=OUTPUT.parent) as directory:
        temp = Path(directory)
        chapters = [
            cut(temp, "reach", "Reach around the obstacle", 0.7, 3.25, "696:630:732:80"),
            cut(temp, "shelf", "Reach inside the shelf and return", 0.65, 6.25, "696:630:732:80", 1.2),
            cut(temp, "pickup", "Lift the nut by its handle", 0.6, 4.3, "600:542:785:130"),
            cut(temp, "placement", "Fit the nut onto the peg", 0.6, 10.9),
        ]
        playlist = temp / "cuts.txt"
        playlist.write_text("".join(f"file '{clip.name}'\n" for clip in chapters), encoding="utf-8")
        draft = temp / "film.mp4"
        ffmpeg("-f", "concat", "-safe", 0, "-i", playlist, "-c", "copy", "-movflags", "+faststart", draft)
        draft.replace(OUTPUT)
    print(OUTPUT)


if __name__ == "__main__":
    main()
