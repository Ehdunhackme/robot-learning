"""Render a synchronized shelf replay and a close-up of the measured nearest surfaces."""
from pathlib import Path
from tempfile import TemporaryDirectory
from xml.etree import ElementTree as ET
import subprocess

import mujoco
import numpy as np
from PIL import Image, ImageDraw

from arm import ROOT
from record_demo import font, line, marker
from shelf import DEFAULT_DEPTH, DEFAULT_WIDTH, ShelfBench, scene
from studio import SHELF_SEED, shelf_replay

FPS = 24
PANEL = (640, 392)
SIZE = (1280, 584)
INK = "#182e3a"
PAPER = "#eef2ee"
TEAL = "#007978"
RUST = "#aa4b35"
TITLES = (font(29, True), font(22, True), font(17), font(15, True))
MODES = (("direct", "Direct reach", RUST, [.90, .33, .19, 1]),
         ("learned", "Learned route", TEAL, [.02, .74, .67, 1]))


def camera(focus, distance, azimuth, elevation):
    cam = mujoco.MjvCamera()
    cam.lookat[:] = focus
    cam.distance, cam.azimuth, cam.elevation = distance, azimuth, elevation
    return cam


def shot(bench, renderer, opt, cam, run, path, index, color, detail=False):
    frames = path["frames"]
    bench.pose(frames[index][3])
    mujoco.mj_forward(bench.m, bench.d)
    renderer.update_scene(bench.d, camera=cam, scene_option=opt)
    marker(renderer.scene, run["goal"], .004, [.66, .45, .85, 1])
    if detail:
        for point in path["gaps"][index]["points"]:
            marker(renderer.scene, point, .0021, [1, .72, .1, 1])
    else:
        line(renderer.scene, [f[1] for f in frames[:index:3]] + [frames[index][1]], color)
    if index == len(frames) - 1 and path["contact_point"]:
        marker(renderer.scene, path["contact_point"], .007, [1, .24, .08, 1])
    return Image.fromarray(renderer.render())


def pretty(name):
    return "moving jaw" if name == "moving_jaw_so101_v1" else name.replace("_", " ")


def film_bench():
    """Give the replay its own lighting and ground material without changing the study model."""
    bench = ShelfBench()
    with TemporaryDirectory() as temp:
        filename = str(Path(temp) / "film.xml")
        mujoco.mj_saveLastXML(filename, bench.m)
        root = ET.parse(filename).getroot()
    asset = root.find("asset")
    ET.SubElement(asset, "texture", type="skybox", builtin="gradient", width="256", height="1536",
                  rgb1=".25 .36 .44", rgb2=".62 .68 .70")
    ET.SubElement(asset, "texture", name="plate_finish", type="2d", builtin="flat",
                  mark="cross", rgb1=".56 .61 .63", markrgb=".41 .47 .49", width="128", height="128")
    ET.SubElement(asset, "material", name="plate", texture="plate_finish", texrepeat="28 28",
                  texuniform="true", specular=".10", shininess=".12")
    world = root.find("worldbody")
    world.find("geom[@name='table']").set("material", "plate")
    ET.SubElement(world, "light", pos="-.6 -.8 1.3", dir=".6 .8 -1.45",
                  directional="true", diffuse=".72 .69 .62", specular=".16 .16 .16")
    ET.SubElement(world, "light", pos="1 .6 1.1", dir="-1 -.6 -1.1", directional="true",
                  diffuse=".24 .32 .39", castshadow="false")
    for mat in asset.findall("material"):
        if mat.get("rgba", "").startswith("1 0.82"):
            mat.set("rgba", ".85 .50 .12 1")
    bench.m = mujoco.MjModel.from_xml_string(ET.tostring(root, encoding="unicode"))
    bench.d = mujoco.MjData(bench.m)
    return bench


def main():
    run = shelf_replay(SHELF_SEED, DEFAULT_WIDTH, DEFAULT_DEPTH)
    bench = film_bench()
    scene(bench, SHELF_SEED, DEFAULT_WIDTH, DEFAULT_DEPTH)
    for i, geom in enumerate(bench.panel_ids):
        bench.m.geom_rgba[geom] = [.22, .39, .48, .22 if i in (2, 3) else 1]
    bench.m.geom_rgba[bench.m.geom("table").id] = [1, 1, 1, 1]
    bench.m.vis.headlight.ambient[:] = .30
    bench.m.vis.headlight.diffuse[:] = .33
    bench.m.vis.global_.offwidth, bench.m.vis.global_.offheight = PANEL
    opt = mujoco.MjvOption()
    opt.geomgroup[3] = 0
    opt.sitegroup[:] = 0
    cam = camera([.17, -.005, .15], .66, 113, -18)
    times = {key: np.array([f[0] for f in run[key]["frames"]]) for key, *_ in MODES}
    nearest = {key: int(np.argmin([g["mm"] for g in run[key]["gaps"]])) for key, *_ in MODES}
    end = max(run[key]["seconds"] for key, *_ in MODES)
    filename = ROOT / "web/shelf.mp4"
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "rawvideo",
           "-pix_fmt", "rgb24", "-s", "1280x584", "-r", str(FPS), "-i", "-", "-an",
           "-c:v", "libx264", "-preset", "fast", "-crf", "18", "-pix_fmt", "yuv420p",
           "-movflags", "+faststart", str(filename)]
    title, heading, text, label = TITLES
    with mujoco.Renderer(bench.m, width=PANEL[0], height=PANEL[1]) as renderer:
        with subprocess.Popen(cmd, stdin=subprocess.PIPE) as video:
            try:
                cache = {}
                for n in range(int((end + 3.65) * FPS)):
                    t = np.clip(n / FPS - .42, 0, end)
                    closeup = n / FPS >= end + 1.1
                    frame = Image.new("RGB", SIZE, PAPER)
                    draw = ImageDraw.Draw(frame)
                    draw.text((22, 8), "Arcbench", font=title, fill=INK)
                    draw.text((185, 19), "Shelf inspection   /   SO-101", font=text, fill=INK)
                    draw.text((938, 19), f"{DEFAULT_WIDTH} mm opening     {DEFAULT_DEPTH} mm depth", font=text, fill=INK)
                    for pane, (key, name, accent, color) in enumerate(MODES):
                        path = run[key]
                        i = nearest[key] if closeup else max(0, np.searchsorted(times[key], t, side="right") - 1)
                        gap = path["gaps"][i]
                        x = pane * PANEL[0]
                        group = (key, i, closeup)
                        if group not in cache:
                            view = cam
                            if closeup:
                                focus = np.mean(gap["points"], axis=0)
                                view = camera(focus, .33, 78, -12)
                            cache[group] = shot(bench, renderer, opt, view, run, path, i, color, closeup)
                        frame.paste(cache[group], (x, 87))
                        if closeup:
                            # The detail camera looks directly at the midpoint of both surface witnesses.
                            u, v = x + PANEL[0] // 2, 87 + PANEL[1] // 2
                            draw.ellipse((u-13, v-13, u+13, v+13), outline="#fff3b4", width=2)
                            draw.line((u+10, v-10, u+34, v-34, u+62, v-34), fill="#fff3b4", width=2)
                        # Only the last frame is reused across adjacent ticks.
                        cache = {k:v for k,v in cache.items() if k[0] != key or k == group}
                        draw.rectangle((x, 54, x + 639, 86), fill=accent)
                        draw.text((x + 21, 59), name, font=label, fill="white")
                        sec = times[key][i]
                        draw.text((x + 517, 59), f"{sec:05.2f} s", font=label, fill="white")
                        if closeup:
                            stage = "Contact point" if key == "direct" else "Closest pass"
                            annotation = f"{pretty(gap['link']).capitalize()} / {gap['panel'].lower()}"
                            if key == "learned":
                                annotation += f"     {gap['mm']:.2f} mm simulated clearance"
                        else:
                            done = i == len(times[key])-1
                            stage = ("Contact" if path["outcome"] == "contact" else "Inspection complete") if done else (
                                "Entering shelf" if sec < 3.6 else "Holding at target" if sec < 4 else "Withdrawing")
                            annotation = (f"{pretty(gap['link']).capitalize()} / {gap['panel'].lower()}" if stage == "Contact"
                                          else f"Nearest shelf surface   {gap['mm']:.1f} mm")
                        draw.text((x + 21, 484), stage, font=heading, fill=accent)
                        draw.text((x + 21, 515), annotation, font=text, fill=INK)
                    draw.line((640, 87, 640, 539), fill="#87999e")
                    draw.rectangle((0, 549, 1280, 584), fill=INK)
                    footer = ("Surface detail   /   Each view is paused at its measured closest approach."
                              if closeup else "Synchronized servo replay   /   Contact stops the arm. The inspection requires a 0.4 s hold and a return home.")
                    draw.text((21, 555), footer, font=text, fill="#e1e9e5")
                    video.stdin.write(frame.tobytes())
            finally:
                video.stdin.close()
            if video.wait():
                raise RuntimeError("ffmpeg failed")
    print(filename)


if __name__ == "__main__":
    main()
