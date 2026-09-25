"""Draw deliberately simple limb-pose guides for the isolated redesign experiment."""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


OUT = Path(__file__).parent / "references" / "pose_guides"
OUT.mkdir(parents=True, exist_ok=True)
RED = "#ed3158"  # near-side leg A and its counter-swinging arm
BLUE = "#168ed2"  # far-side leg B and its counter-swinging arm
BODY = "#9aa5b1"
INK = "#27384a"


def font(size: int):
    for name in ("arial.ttf", "segoeui.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            pass
    return ImageFont.load_default()


def limb(draw: ImageDraw.ImageDraw, points: list[tuple[int, int]], color: str, label: str) -> None:
    draw.line(points, fill=color, width=22, joint="curve")
    radius = 13
    for x, y in points[1:-1]:
        draw.ellipse((x-radius, y-radius, x+radius, y+radius), fill=color)
    ankle_x, ankle_y = points[-1]
    draw.line((ankle_x, ankle_y, ankle_x + 31, ankle_y + 3), fill=INK, width=18)
    draw.text((ankle_x + 7, ankle_y - 38), label, fill=color, font=font(26), stroke_width=2, stroke_fill="white")


def make(name: str, a_leg: list[tuple[int, int]], b_leg: list[tuple[int, int]],
         a_arm: list[tuple[int, int]], b_arm: list[tuple[int, int]]) -> None:
    im = Image.new("RGB", (512, 512), "white")
    d = ImageDraw.Draw(im)
    # Compact chibi body and right-facing head; these neutral shapes are only pose landmarks.
    d.ellipse((145, 43, 344, 238), fill="#d7dce1", outline=INK, width=5)
    d.ellipse((292, 122, 307, 137), fill="#1976d2")
    d.line((226, 216, 235, 282), fill=BODY, width=48)
    d.polygon([(185, 253), (280, 253), (344, 323), (166, 323)], fill="#d7dce1", outline=INK)
    # Shoulder/hip joints are placed under the compact torso/skirt landmarks.
    limb(d, a_arm, RED, "A")
    limb(d, b_arm, BLUE, "B")
    limb(d, a_leg, RED, "A")
    limb(d, b_leg, BLUE, "B")
    im.save(OUT / f"{name}.png")


make(
    "walk_right_f0_contact_A",
    [(202, 294), (275, 350), (363, 410)],
    [(302, 294), (242, 345), (164, 386)],
    [(212, 223), (170, 251), (136, 270)],
    [(284, 223), (327, 203), (366, 213)],
)
make(
    "walk_right_f1_passing_A",
    [(202, 294), (239, 349), (246, 398)],
    [(302, 294), (281, 345), (294, 396)],
    [(212, 223), (206, 258), (218, 282)],
    [(284, 223), (291, 258), (278, 282)],
)
make(
    "walk_right_f2_contact_B",
    [(202, 294), (168, 347), (158, 389)],
    [(302, 294), (342, 350), (389, 408)],
    [(212, 223), (247, 202), (285, 211)],
    [(284, 223), (244, 251), (207, 270)],
)
make(
    "walk_right_f3_passing_B",
    [(202, 294), (183, 347), (196, 398)],
    [(302, 294), (268, 349), (260, 399)],
    [(212, 223), (218, 258), (232, 282)],
    [(284, 223), (278, 258), (264, 282)],
)
