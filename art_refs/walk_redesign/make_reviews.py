"""Create isolated candidate frames and review artifacts for a walk iteration.

This helper only crops generated sprite sheets and assembles comparison images/GIFs.
It does not edit the source art or any production asset.
"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


LABELS = ["Contact A", "Passing A", "Contact B", "Passing B"]


def load_font(size: int) -> ImageFont.ImageFont:
    for name in ("arial.ttf", "segoeui.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            pass
    return ImageFont.load_default()


def render_iteration(iteration: Path) -> None:
    sheet_path = iteration / "generated_sheet.png"
    if sheet_path.exists():
        sheet = Image.open(sheet_path).convert("RGBA")
        width, height = sheet.size
        if width % 2 or height % 2:
            raise ValueError(f"Expected even 2x2 sprite sheet dimensions, got {sheet.size}")
        cell_w, cell_h = width // 2, height // 2
        boxes = [
            (0, 0, cell_w, cell_h),
            (cell_w, 0, width, cell_h),
            (0, cell_h, cell_w, height),
            (cell_w, cell_h, width, height),
        ]
        frames = [sheet.crop(box) for box in boxes]
    else:
        frames = [
            Image.open(iteration / f"generated_f{index}.png").convert("RGBA")
            for index in range(4)
        ]
        cell_w, cell_h = frames[0].size
        if any(frame.size != (cell_w, cell_h) for frame in frames):
            raise ValueError("The four generated frame canvases must have matching dimensions")

    # ImageGen sometimes leaves different transparent margins around each pose.
    # Crop only that transparency, then uniformly scale and place every subject
    # to a shared height, horizontal center, and shoe baseline. No limb pixels
    # are painted or reshaped by this alignment step.
    crops = []
    for frame in frames:
        alpha = frame.getchannel("A").point(lambda value: 255 if value > 8 else 0)
        box = alpha.getbbox()
        if not box:
            raise ValueError("A generated frame contains no visible subject")
        crops.append(frame.crop(box))

    target_h = max(crop.height for crop in crops)
    widest_ratio = max(crop.width / crop.height for crop in crops)
    target_h = min(target_h, round((cell_w - 48) / widest_ratio))
    baseline = cell_h - (40 if cell_h > 700 else 10)
    target_h = min(target_h, baseline - 4)
    aligned: list[Image.Image] = []
    for index, crop in enumerate(crops):
        target_w = round(crop.width * target_h / crop.height)
        subject = crop.resize((target_w, target_h), Image.Resampling.LANCZOS)
        canvas = Image.new("RGBA", (cell_w, cell_h), (0, 0, 0, 0))
        canvas.alpha_composite(subject, ((cell_w - target_w) // 2, baseline - target_h))
        canvas.save(iteration / f"walk_right_f{index}.png")
        aligned.append(canvas)
    frames = aligned

    scale = min(1, 440 / cell_w)
    label_h = 56
    padding = 18
    display_w, display_h = round(cell_w * scale), round(cell_h * scale)
    font = load_font(30)
    strip = Image.new("RGB", (padding + 4 * (display_w + padding), display_h + label_h + padding), "#f2f4f8")
    draw = ImageDraw.Draw(strip)
    for index, (frame, label) in enumerate(zip(frames, LABELS)):
        x = padding + index * (display_w + padding)
        draw.text((x + 8, 10), f"F{index}  {label}", fill="#18324b", font=font)
        card = Image.new("RGBA", frame.size, "white")
        card.alpha_composite(frame)
        strip.paste(card.convert("RGB").resize((display_w, display_h)), (x, label_h))
    strip.save(iteration / "walk_right_review_strip.png")

    contact_w, contact_h = display_w * 2, display_h
    contact = Image.new("RGB", (contact_w + padding * 3, contact_h + label_h + padding * 2), "#f2f4f8")
    draw = ImageDraw.Draw(contact)
    for pos, index in enumerate((0, 2)):
        x = padding + pos * (display_w + padding)
        draw.text((x + 8, 10), f"F{index}  {LABELS[index]}", fill="#18324b", font=font)
        card = Image.new("RGBA", frames[index].size, "white")
        card.alpha_composite(frames[index])
        contact.paste(card.convert("RGB").resize((display_w, display_h)), (x, label_h))
    contact.save(iteration / "walk_contact_review.png")

    gif_frames = [frame.resize((display_w, display_h), Image.Resampling.LANCZOS) for frame in frames]
    gif_frames[0].save(
        iteration / "walk_right_candidate.gif",
        save_all=True,
        append_images=gif_frames[1:],
        duration=170,
        loop=0,
        disposal=2,
        transparency=0,
    )


if __name__ == "__main__":
    folder = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).parent / "iterations" / "iter_01"
    render_iteration(folder)
