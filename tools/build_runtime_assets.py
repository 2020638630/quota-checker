#!/usr/bin/env python3
"""Build Tk color-key-safe runtime sprites from existing RGBA PNG assets.

The current ``source/`` references in this project are JPEG files with a
``.png`` suffix, so this small tool intentionally defaults to the existing
RGBA files in ``pet_assets/``.  It does not alter the high-resolution source
references.  Pixels below the alpha threshold become the runtime color key;
all remaining pixels become opaque while retaining their foreground RGB.
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pngtool import alpha_stats, decode, encode


KEY_RGB = (255, 0, 254)
DEFAULT_ASSETS = Path(__file__).resolve().parents[1] / "pet_assets"
DEFAULT_THRESHOLD = 128


def _manifest_names(asset_dir):
    manifest_path = asset_dir / "manifest.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        manifest = {}

    names = []
    for value in manifest.values():
        values = [value] if isinstance(value, str) else value
        if not isinstance(values, list):
            continue
        for name in values:
            if isinstance(name, str) and name.strip() and name not in names:
                names.append(name)
    return names or [
        "front.png", "front_typing.png", "side_l.png", "side_l_1.png",
        "side_r.png", "side_r_1.png", "back.png",
        "blink_1.png", "blink_2.png", "sleep_1.png", "sleep_2.png",
    ]


def normalize_rgba(rgba, threshold):
    """Return opaque foreground plus opaque key-color background."""
    out = bytearray(len(rgba))
    for i in range(0, len(rgba), 4):
        if rgba[i + 3] < threshold:
            out[i:i + 4] = bytes((*KEY_RGB, 255))
        else:
            out[i:i + 4] = bytes((rgba[i], rgba[i + 1], rgba[i + 2], 255))
    return out


def build(input_dir, output_dir, threshold, names):
    if not 1 <= threshold <= 254:
        raise ValueError("threshold must be between 1 and 254")
    output_dir.mkdir(parents=True, exist_ok=True)
    reports = []
    for name in names:
        source = input_dir / name
        if not source.exists():
            raise FileNotFoundError(source)
        width, height, rgba = decode(source.read_bytes())
        before = alpha_stats(rgba)
        normalized = normalize_rgba(rgba, threshold)
        destination = output_dir / name
        destination.write_bytes(encode(width, height, normalized))
        after = alpha_stats(normalized)
        reports.append({
            "name": name,
            "size": [width, height],
            "before": before,
            "after": after,
            "threshold": threshold,
            "key_rgb": KEY_RGB,
        })
    return reports


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_ASSETS)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_ASSETS)
    parser.add_argument("--threshold", type=int, default=DEFAULT_THRESHOLD)
    parser.add_argument("--files", nargs="*", default=None,
                        help="specific PNG names; default is manifest assets")
    args = parser.parse_args()
    names = args.files or _manifest_names(args.input_dir)
    for report in build(args.input_dir, args.output_dir, args.threshold, names):
        print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
