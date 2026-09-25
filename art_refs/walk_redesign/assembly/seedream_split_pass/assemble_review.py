"""Assemble supplied walk frames into an isolated review candidate.

This utility only reads experiment inputs below art_refs/walk_redesign and
writes review outputs below iterations/passing_frames/assembled. It does not
touch production assets or source sheets.
"""

from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont


PROJECT_ROOT = Path(__file__).resolve().parents[4]
WALK_ROOT = PROJECT_ROOT / "art_refs" / "walk_redesign"
PASS_ROOT = WALK_ROOT / "iterations" / "passing_frames"
OUTPUT_ROOT = PASS_ROOT / "assembled"
CANVAS = (1024, 1024)
TARGET_HEIGHT = 850
BASELINE = 982
LABELS = ("Contact A", "Passing A", "Contact B", "Passing B")
KEY_RGB = (255, 0, 255)

SOURCES = (
    WALK_ROOT / "iterations" / "seedream_pass3" / "frame_0.png",
    PASS_ROOT / "walk_right_f1.png",
    WALK_ROOT / "iterations" / "seedream_pass3" / "frame_2.png",
    PASS_ROOT / "walk_right_f3.png",
)


def load_font(size: int) -> ImageFont.ImageFont:
    for name in ("arial.ttf", "segoeui.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def remove_magenta_background(path: Path) -> tuple[Image.Image, dict[str, object]]:
    source = Image.open(path).convert("RGB")
    rgb = np.asarray(source)
    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
    hue, saturation, value = hsv[:, :, 0], hsv[:, :, 1], hsv[:, :, 2]

    # The generated backgrounds vary slightly in hue and brightness. Use a
    # broad magenta family mask, then retain only regions connected to a canvas
    # edge. A stricter mask also removes any isolated leftover key pixels.
    strict_key = (
        (hue >= 148) & (hue <= 178) & (saturation >= 78) & (value >= 55)
    )
    broad_key = (
        (hue >= 140) & (hue <= 179) & (saturation >= 22) & (value >= 35)
    )
    count, labels = cv2.connectedComponents(broad_key.astype(np.uint8), connectivity=8)
    border_labels = np.unique(
        np.concatenate((labels[0, :], labels[-1, :], labels[:, 0], labels[:, -1]))
    )
    exterior = np.isin(labels, border_labels) & broad_key
    background = exterior | strict_key

    alpha = np.where(background, 0, 255).astype(np.uint8)
    rgba = np.dstack((rgb, alpha))
    keyed = Image.fromarray(rgba, "RGBA")
    bbox = keyed.getchannel("A").getbbox()
    if bbox is None:
        raise ValueError(f"No subject remained after key removal: {path}")

    left, top, right, bottom = bbox
    width, height = source.size
    metadata = {
        "source": str(path.resolve()),
        "source_size": [width, height],
        "source_subject_bbox": list(bbox),
        "touches_source_edge": {
            "left": left == 0,
            "top": top == 0,
            "right": right == width,
            "bottom": bottom == height,
        },
    }
    return keyed.crop(bbox), metadata


def align_frame(subject: Image.Image) -> tuple[Image.Image, float]:
    width, height = subject.size
    max_width = CANVAS[0] - 96
    scale = min(TARGET_HEIGHT / height, max_width / width)
    resized = subject.resize(
        (max(1, round(width * scale)), max(1, round(height * scale))),
        Image.Resampling.LANCZOS,
    )
    canvas = Image.new("RGBA", CANVAS, (0, 0, 0, 0))
    x = (CANVAS[0] - resized.width) // 2
    y = BASELINE - resized.height
    canvas.alpha_composite(resized, (x, y))
    return canvas, scale


def on_white(frame: Image.Image, size: tuple[int, int]) -> Image.Image:
    card = Image.new("RGBA", frame.size, "white")
    card.alpha_composite(frame)
    return card.convert("RGB").resize(size, Image.Resampling.LANCZOS)


def write_reviews(frames: list[Image.Image]) -> None:
    font = load_font(30)
    panel = 512
    header = 52
    padding = 18

    contact = Image.new(
        "RGB", (padding * 3 + panel * 2, header + padding * 2 + panel), "#f2f4f8"
    )
    draw = ImageDraw.Draw(contact)
    for x, index in zip((padding, padding * 2 + panel), (0, 2)):
        draw.text((x + 8, 10), f"F{index}  {LABELS[index]}", fill="#18324b", font=font)
        contact.paste(on_white(frames[index], (panel, panel)), (x, header))
    contact.save(OUTPUT_ROOT / "walk_contact_review.png")

    strip_panel = 384
    strip_header = 48
    gap = 14
    strip = Image.new(
        "RGB",
        (gap + 4 * (strip_panel + gap), strip_header + strip_panel + gap),
        "#f2f4f8",
    )
    draw = ImageDraw.Draw(strip)
    for index, (frame, label) in enumerate(zip(frames, LABELS)):
        x = gap + index * (strip_panel + gap)
        draw.text((x + 6, 8), f"F{index}  {label}", fill="#18324b", font=font)
        strip.paste(on_white(frame, (strip_panel, strip_panel)), (x, strip_header))
    strip.save(OUTPUT_ROOT / "walk_right_review_strip.png")

    gif_frames = [on_white(frame, (512, 512)).convert("P", palette=Image.Palette.ADAPTIVE) for frame in frames]
    gif_frames[0].save(
        OUTPUT_ROOT / "walk_right_candidate.gif",
        save_all=True,
        append_images=gif_frames[1:],
        duration=170,
        loop=0,
        disposal=2,
        optimize=False,
    )


def main() -> None:
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    frames: list[Image.Image] = []
    metrics: list[dict[str, object]] = []

    for index, source in enumerate(SOURCES):
        if not source.is_file():
            raise FileNotFoundError(source)
        subject, metadata = remove_magenta_background(source)
        aligned, scale = align_frame(subject)
        target = OUTPUT_ROOT / f"walk_right_f{index}.png"
        aligned.save(target)
        metadata.update(
            {
                "subject_crop_size": list(subject.size),
                "uniform_scale": round(scale, 5),
                "output": str(target.resolve()),
                "output_canvas": list(CANVAS),
                "target_visible_height": TARGET_HEIGHT,
                "baseline_y": BASELINE,
            }
        )
        frames.append(aligned)
        metrics.append(metadata)

    write_reviews(frames)
    (OUTPUT_ROOT / "alignment_metrics.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
