import json, sys
from pathlib import Path
sys.path.insert(0, ".")
import pngtool

ASSETS = Path("pet_assets")
manifest = json.loads((ASSETS / "manifest.json").read_text(encoding="utf-8"))
print("manifest side_r:", manifest["side_r"])
print("manifest side_l:", manifest["side_l"])

def asset_key(role, index):
    return role if index == 0 else f"{role}_{index}"

ok = True
for role in ("side_r", "side_l"):
    files = manifest[role]
    keys = []
    for i, name in enumerate(files):
        path = ASSETS / name
        key = asset_key(role, i)
        keys.append(key)
        if not path.is_file():
            print("MISSING", path)
            ok = False
            continue
        w, h, rgba = pngtool.decode(path.read_bytes())
        c0 = (rgba[0], rgba[1], rgba[2])
        print(f"  {key} <- {name}: {w}x{h} bytes={path.stat().st_size} corner0={c0}")
        if (w, h) != (215, 264):
            print("  BAD SIZE")
            ok = False
        if c0 != (255, 0, 254):
            print("  BAD KEY")
            ok = False
    cycle = " -> ".join(keys) + " -> " + keys[0]
    print(f"cycle {role}: {cycle}")

src = Path("quota_pet.py").read_text(encoding="utf-8", errors="replace")
for needle in ("FOOT_PAD_PX", "_frame_anchor_from_png", "_rebuild_frame_anchors", "_foot_baseline", "center_x"):
    print(f"quota_pet has {needle}:", needle in src)

# simulate walk frame index progression F0..F3
hold = 3
frames_r = [asset_key("side_r", i) for i in range(4)]
seen = [frames_r[(t // hold) % 4] for t in range(12)]
print("walk tick frames sample:", seen)
print("SMOKE", "PASS" if ok else "FAIL")
