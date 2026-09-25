"""Pose diagrams for iteration 4; A is always the near-side foreground limb."""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


OUT = Path(__file__).parent / "pose_guides"
OUT.mkdir(parents=True, exist_ok=True)
RED, BLUE = "#ed3158", "#168ed2"
BODY, INK = "#d7dce1", "#27384a"


def font(size: int):
    for name in ("arial.ttf", "segoeui.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            pass
    return ImageFont.load_default()


def stroke(d, pts, color, label, width=22):
    d.line(pts, fill=color, width=width, joint="curve")
    for x, y in pts[1:-1]:
        r = width // 2
        d.ellipse((x-r, y-r, x+r, y+r), fill=color)
    x, y = pts[-1]
    # The little horizontal block is a shoe pointing right.
    d.rounded_rectangle((x-5, y-9, x+48, y+9), radius=6, fill=INK)
    d.text((x+8, y-44), label, fill=color, font=font(28), stroke_width=2, stroke_fill="white")


def make(name, legs, arms):
    im = Image.new("RGB", (512, 512), "white")
    d = ImageDraw.Draw(im)
    d.ellipse((145, 43, 344, 238), fill=BODY, outline=INK, width=5)
    d.ellipse((292, 122, 307, 137), fill="#1976d2")
    d.line((226, 216, 235, 282), fill="#9aa5b1", width=48)
    d.polygon([(185, 253), (280, 253), (344, 323), (166, 323)], fill=BODY, outline=INK)
    # Draw the far-side blue arm and leg first. Near-side red A stays in front,
    # so its depth ordering can be seen when its lead position changes.
    for pts, color, label in arms:
        if color == BLUE:
            stroke(d, pts, color, label)
    for pts, color, label in legs:
        if color == BLUE:
            stroke(d, pts, color, label)
    for pts, color, label in arms:
        if color == RED:
            stroke(d, pts, color, label)
    for pts, color, label in legs:
        if color == RED:
            stroke(d, pts, color, label)
    im.save(OUT / f"{name}.png")


make("f0_contact_A", [
    ([(302, 314), (242, 356), (163, 383)], BLUE, "B"),  # back leg, toe-off
    ([(218, 314), (286, 356), (375, 408)], RED, "A"),   # near A planted forward
], [
    ([(284, 224), (330, 204), (374, 210)], BLUE, "B"),
    ([(212, 224), (167, 250), (130, 265)], RED, "A"),
])
make("f1_passing_A", [
    ([(302, 314), (280, 348), (292, 394)], BLUE, "B"),  # B passes forward behind A
    ([(218, 314), (242, 348), (246, 394)], RED, "A"),   # A recovers beneath body
], [
    ([(284, 224), (296, 250), (286, 275)], BLUE, "B"),
    ([(212, 224), (203, 250), (218, 275)], RED, "A"),
])
make("f2_contact_B", [
    ([(302, 314), (348, 353), (392, 408)], BLUE, "B"),  # far B planted forward
    ([(218, 314), (180, 330), (164, 365)], RED, "A"),   # near A trailing, bent/lifted
], [
    ([(284, 224), (244, 250), (204, 265)], BLUE, "B"),
    ([(212, 224), (258, 204), (300, 211)], RED, "A"),
])
make("f3_passing_B", [
    ([(302, 314), (255, 348), (239, 394)], BLUE, "B"),  # B recovers under body
    ([(218, 314), (275, 348), (309, 394)], RED, "A"),   # A passes forward in front
], [
    ([(284, 224), (272, 250), (260, 275)], BLUE, "B"),
    ([(212, 224), (225, 250), (244, 275)], RED, "A"),
])
