# Seedance walk motion-source candidate review

## Motion review

The 26-frame sequence contains genuine motion and is suitable for experimental pose extraction: the arm phase reverses, the legs lift and pass beneath the body, and the character stays in a right-facing side view.

The selected stills are **candidates only**. F0/F2 have different arm positions, but the leading-leg exchange is not unmistakable in their side-by-side silhouette; the right-side shoe still reads as leading in both. Do not call the final four-frame walk qualified until that hard gate is clear.

## Event-frame selection

- F0: `walk_010_t2.0s.png` (2.0 s), Contact A candidate
- F1: `walk_012_t2.4s.png` (2.4 s), Passing A candidate
- F2: `walk_013_t2.6s.png` (2.6 s), Contact B candidate
- F3: `walk_015_t3.0s.png` (3.0 s), Passing B candidate

## Cleanup applied to these experimental candidates

- Sampled 20x20 pixels at each of the four corners per source frame to estimate the hot-pink background. Per-frame means are in `alignment_metrics.json`.
- Mapped pixels within RGB distance 90 of the sampled corner mean to pure magenta, then used 4-connected flood fill from the corners for pixels within RGB distance 160 of pure magenta.
- Cropped at source y=1082 (exclusive) to remove the bottom dashed floor marker while preserving the shoes.
- Used one shared character bbox across all four selected frames, NEAREST scaling, preserved aspect ratio, and placed the result on a 215x264 pure-magenta canvas. The character content is 180x256 with centered horizontal padding.
- Created a 4-frame preview GIF at 170 ms per frame for review only.

These files are experimental candidates, not production assets. No production files were changed.
