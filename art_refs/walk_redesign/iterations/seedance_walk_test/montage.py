import cv2, os, glob
fd = os.path.join(os.path.dirname(os.path.abspath(__file__)), "frames")
files = sorted(glob.glob(os.path.join(fd, "walk_*.png")))
imgs = [cv2.imread(f) for f in files]
# tile 5 columns
cols = 5
rows = (len(imgs) + cols - 1) // cols
h, w = imgs[0].shape[:2]
# scale down each to width 300
tw = 300
th = int(h * tw / w)
canvas = 255 * __import__("numpy").ones((rows * th, cols * tw, 3), dtype="uint8")
for idx, im in enumerate(imgs):
    r, c = divmod(idx, cols)
    small = cv2.resize(im, (tw, th))
    canvas[r*th:(r+1)*th, c*tw:(c+1)*tw] = small
out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "contact_sheet.png")
cv2.imwrite(out, canvas)
print(f"saved {out}: {cols}x{rows} grid, {len(imgs)} frames")
