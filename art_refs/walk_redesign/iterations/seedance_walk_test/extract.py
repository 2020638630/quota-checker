import cv2, os
out = os.path.dirname(os.path.abspath(__file__))
v = cv2.VideoCapture(os.path.join(out, "walk.mp4"))
fps = v.get(cv2.CAP_PROP_FPS)
n = int(v.get(cv2.CAP_PROP_FRAME_COUNT))
print(f"fps={fps} frames={n} dur={n/fps:.2f}s")
for t in [0.4, 1.0, 1.6, 2.2, 2.8, 3.4, 4.0, 4.6]:
    v.set(cv2.CAP_PROP_POS_MSEC, t*1000)
    ok, frame = v.read()
    if ok:
        cv2.imwrite(os.path.join(out, f"t{t:.1f}.png"), frame)
v.release()
print("done")
