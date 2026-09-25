#!/usr/bin/env python3
"""Slice and normalize the four 4x2 movement sheets for the desktop pet.

The output images stay on the existing 215x264 runtime canvas.  Pillow is
needed only when rebuilding artwork; the pet runtime itself remains Tk-only.
The existing build_runtime_assets module performs the final alpha-to-color-key
conversion so generated sprites follow the same rules as the other assets.
"""

from pathlib import Path
import sys
import tempfile

try:
    from PIL import Image
except ImportError as exc:  # pragma: no cover - environment-dependent message
    raise SystemExit("Pillow is required only to rebuild sprite sheets: python -m pip install Pillow") from exc


ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = ROOT / "source" / "move_animation_source_sheets"
ASSET_DIR = ROOT / "pet_assets"
SHEET_SIZE = (1536, 1024)
CELL_SIZE = (384, 512)
RUNTIME_SIZE = (215, 264)
RESIZED_CELL = (198, 264)  # uniform 33/64 scale; leaves 8/9 px side margins
CONTENT_BASELINE = 262     # two transparent rows below opaque content

SHEETS = {
    "walk_sheet.png": ("side_l", "side_r"),
    "run_sheet.png": ("run_l", "run_r"),
    "whale_ride_sheet.png": ("ride_l", "ride_r"),
    "duo_run_sheet.png": ("duo_l", "duo_r"),
}


def validate_sources():
    """Validate every sheet before generating or replacing any runtime frame."""
    checked = []
    for filename in SHEETS:
        path = SOURCE_DIR / filename
        if not path.is_file():
            raise SystemExit(f"MOVE ANIMATION SHEET BLOCKED: missing source: {path}")
        with Image.open(path) as opened:
            if opened.size != SHEET_SIZE or opened.mode != "RGBA":
                raise SystemExit(
                    "MOVE ANIMATION SHEET BLOCKED: "
                    f"{filename}: size={opened.size}, mode={opened.mode}; "
                    f"expected {SHEET_SIZE}, RGBA"
                )
            alpha = opened.getchannel("A")
            histogram = alpha.histogram()
            corners = [alpha.getpixel(pos) for pos in (
                (0, 0), (opened.width - 1, 0),
                (0, opened.height - 1), (opened.width - 1, opened.height - 1),
            )]
            if not any(value == 0 for value in corners) or histogram[0] == 0:
                raise SystemExit(
                    f"MOVE ANIMATION SHEET BLOCKED: {filename} has no transparent background"
                )
            checked.append({
                "file": filename,
                "size": list(opened.size),
                "mode": opened.mode,
                "alpha_extrema": list(alpha.getextrema()),
                "transparent_pixels": histogram[0],
                "semi_alpha_pixels": sum(histogram[1:255]),
                "opaque_pixels": histogram[255],
                "grid": "4x2",
                "cell_size": list(CELL_SIZE),
                "background": "transparent",
            })
    return checked


def _opaque_bbox(image):
    mask = image.getchannel("A").point(lambda value: 255 if value >= 128 else 0)
    return mask.getbbox()


def build_frames():
    # Import the project's existing key-safe builder rather than implementing
    # a second alpha policy here.
    sys.path.insert(0, str(ROOT / "tools"))
    from build_runtime_assets import build as build_runtime_assets

    source_report = validate_sources()
    frame_names = []
    with tempfile.TemporaryDirectory(prefix="quota-pet-move-frames-") as temp:
        staging = Path(temp)
        for filename, (left_role, right_role) in SHEETS.items():
            path = SOURCE_DIR / filename
            with Image.open(path) as opened:
                sheet = opened.copy()
            for row, role in ((0, left_role), (1, right_role)):
                for frame_index in range(4):
                    x0 = frame_index * CELL_SIZE[0]
                    y0 = row * CELL_SIZE[1]
                    cell = sheet.crop((x0, y0,
                                       x0 + CELL_SIZE[0], y0 + CELL_SIZE[1]))
                    resized = cell.resize(RESIZED_CELL, Image.Resampling.LANCZOS)
                    bbox = _opaque_bbox(resized)
                    if bbox is None:
                        raise SystemExit(
                            f"MOVE ANIMATION SHEET BLOCKED: empty frame {filename} row={row} col={frame_index}"
                        )
                    dy = CONTENT_BASELINE - bbox[3]
                    if bbox[1] + dy < 0 or bbox[3] + dy > RUNTIME_SIZE[1]:
                        raise SystemExit(
                            f"MOVE ANIMATION SHEET BLOCKED: frame does not fit runtime canvas: {filename} row={row} col={frame_index}"
                        )

                    canvas = Image.new("RGBA", RUNTIME_SIZE, (0, 0, 0, 0))
                    # Preserve the source cell's horizontal anchor.  Align all
                    # frames to the same opaque foot/ride baseline.
                    source_top = max(0, -dy)
                    source_bottom = min(
                        RESIZED_CELL[1], RUNTIME_SIZE[1] - dy
                    )
                    visible_part = resized.crop(
                        (0, source_top, RESIZED_CELL[0], source_bottom)
                    )
                    canvas.alpha_composite(
                        visible_part, (8, max(0, dy))
                    )
                    name = role if frame_index == 0 else f"{role}_{frame_index}"
                    canvas.save(staging / f"{name}.png", format="PNG")
                    frame_names.append(f"{name}.png")

        reports = build_runtime_assets(
            staging, ASSET_DIR, threshold=128, names=frame_names
        )

    print("SOURCE SHEETS")
    for report in source_report:
        print(report)
    print("RUNTIME FRAMES")
    for report in reports:
        print(report)
    return reports


if __name__ == "__main__":
    build_frames()
