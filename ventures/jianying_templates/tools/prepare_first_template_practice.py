"""Create font-free geometric practice inputs; never produce a Jianying template."""
from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path

from PIL import Image, ImageDraw

CASE = Path(__file__).resolve().parents[1]
OUTPUT = CASE / "practice_20261029"
COLORS = ["#C58E76", "#829A85", "#8D9FAE", "#BEA36D", "#A48FAD", "#7AA6A0"]
DIGITS = {"0": "abcedf", "1": "bc", "2": "abged", "3": "abgcd", "4": "fgbc",
          "5": "afgcd", "6": "afgecd", "9": "abfgcd"}


def number(draw, label, center, scale, color):
    """Seven-segment digits drawn from original rectangles; no font dependency."""
    width, height, thickness = 100 * scale, 180 * scale, 16 * scale
    gap = 28 * scale
    x = center[0] - (len(label) * width + (len(label) - 1) * gap) / 2
    y = center[1] - height / 2
    for digit in label:
        boxes = {
            "a": (x + thickness, y, x + width - thickness, y + thickness),
            "b": (x + width - thickness, y + thickness, x + width, y + height / 2 - thickness / 2),
            "c": (x + width - thickness, y + height / 2 + thickness / 2, x + width, y + height - thickness),
            "d": (x + thickness, y + height - thickness, x + width - thickness, y + height),
            "e": (x, y + height / 2 + thickness / 2, x + thickness, y + height - thickness),
            "f": (x, y + thickness, x + thickness, y + height / 2 - thickness / 2),
            "g": (x + thickness, y + height / 2 - thickness / 2,
                  x + width - thickness, y + height / 2 + thickness / 2),
        }
        for segment in DIGITS[digit]:
            draw.rounded_rectangle(boxes[segment], radius=4 * scale, fill=color)
        x += width + gap


def background(size):
    image = Image.new("RGB", size, "#F5F0E8")
    draw = ImageDraw.Draw(image)
    width, height = size
    draw.rounded_rectangle((width * .06, height * .04, width * .94, height * .96),
                           radius=36, outline="#D4C8B7", width=3)
    draw.line((width * .37, height * .16, width * .63, height * .16), fill="#BEA68C", width=4)
    draw.line((width * .37, height * .84, width * .63, height * .84), fill="#BEA68C", width=4)
    return image


def save(image, path, kind):
    with path.open("xb") as handle:
        image.save(handle, format="PNG")
    return {"file": path.name, "width": image.width, "height": image.height,
            "kind": kind, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    if OUTPUT.exists() and any(OUTPUT.iterdir()):
        raise FileExistsError("Practice folder is non-empty; refusing to overwrite")
    OUTPUT.mkdir(exist_ok=True)
    entries = [save(background((1080, 1920)), OUTPUT / "00_background.png", "fixed_background")]
    for index, color in enumerate(COLORS, 1):
        image = background((1080, 1920))
        draw = ImageDraw.Draw(image)
        draw.rounded_rectangle((145, 390, 935, 1530), radius=42, fill="#FFFCF7", outline=color, width=6)
        number(draw, f"0{index}", (540, 960), 2.4, color)
        for dot in range(index):
            x = 540 + (dot - (index - 1) / 2) * 38
            draw.ellipse((x - 7, 1420, x + 7, 1434), fill=color)
        entries.append(save(image, OUTPUT / f"0{index}_practice.png", "numbered_placeholder_not_real_photo"))
    wide = background((1600, 900))
    number(ImageDraw.Draw(wide), "99", (800, 450), 2.5, "#B55E53")
    entries.append(save(wide, OUTPUT / "07_replace_wide.png", "landscape_replacement_test"))
    manifest = {
        "purpose": "Offline first-project practice only; not a native template or paid product",
        "source": "Original geometric drawing by the included Python script; no third-party photo, music or font",
        "script": "tools/prepare_first_template_practice.py", "assets": entries,
    }
    with (OUTPUT / "manifest.json").open("x", encoding="utf-8") as handle:
        json.dump(manifest, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    with zipfile.ZipFile(OUTPUT / "first_template_practice.zip", "x", zipfile.ZIP_DEFLATED) as archive:
        for entry in entries:
            archive.write(OUTPUT / entry["file"], entry["file"])
        archive.write(OUTPUT / "manifest.json", "manifest.json")
    print("Created 8 PNG practice assets, manifest and zip; no app project or template was created.")


if __name__ == "__main__":
    main()
