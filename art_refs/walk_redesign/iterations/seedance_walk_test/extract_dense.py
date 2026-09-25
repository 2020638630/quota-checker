import cv2, os
out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "frames")
os.makedirs(out, exist_ok=True)
v = cv2.VideoCapture(os.path.join(os.path.dirname(os.path.abspath(__file__)), "walk.mp4"))
fps = v.get(cv2.CAP_PROP_FPS)
n = int(v.get(cv2.CAP_PROP_FRAME_COUNT))
dur = n / fps
print(f"fps={fps} frames={n} dur={dur:.2f}s")
step = 0.2  # seconds
i = 0
t = 0.0
while t < dur:
    v.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
    ok, frame = v.read()
    if ok:
        cv2.imwrite(os.path.join(out, f"walk_{i:03d}_t{t:.1f}s.png"), frame)
        i += 1
    t += step
v.release()
print(f"extracted {i} frames to {out}")
