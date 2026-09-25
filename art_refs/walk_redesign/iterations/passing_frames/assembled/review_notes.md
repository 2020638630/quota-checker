# Seedream Split Pass — Assembly Review

## Inputs used

- F0: `iterations/seedream_pass3/frame_0.png` (byte-identical to `iterations/passing_frames/walk_right_f0_contactA.png`)
- F1: `iterations/passing_frames/walk_right_f1.png`
- F2: `iterations/seedream_pass3/frame_2.png` (byte-identical to `iterations/passing_frames/walk_right_f2_contactB.png`)
- F3: `iterations/passing_frames/walk_right_f3.png`

## Assembly

- Removed the magenta key background into transparent RGBA.
- Placed all frames on 1024 x 1024 canvases, with a common visible character height of 850 px and a shared baseline at y=982.
- Used uniform scaling and horizontal subject-bounds centering; no limb repainting or pose edits were applied.
- Generated the contact comparison, four-frame strip, and 4-frame looping GIF (170 ms per frame).
- Original input images remain unchanged.

## Review matrix

| Check | Result | Finding |
|---|---|---|
| R1. Leg exchange | FAIL | F0 and F2 both appear to keep the same screen-right shoe forward; no unmistakable leg identity reversal is visible. |
| R2. Arm exchange | FAIL | Opposing arm swing is not clearly demonstrated; F0 is also cropped at the source's right edge. |
| R3. Passing pose | FAIL | F1 remains a wide stride. F3 has close feet but reads closer to a static upright pose than a clear passing phase. |
| R4. Character consistency | PASS | Face, hair, maid costume, whale hair accessory, apron whale, cuffs, socks, shoes, and overall scale remain recognizably consistent. Source-edge crops are a framing/completeness defect rather than a design drift. |
| R5. Walk readability | FAIL | The ordered sequence does not clearly establish alternating steps because contact reversal is absent and the passing frames do not clearly pass under the body. |
| R6. Loop readability | FAIL | F3-to-F0 keeps the aligned scale and baseline, but transitions abruptly from close, nearly upright legs to a wide contact stride. |

## Source and playback limitations

The keyed subject bounds touch the original right edge for F0 and both horizontal edges for F2. Assembly cannot restore content missing from those source crops. F2 also retains a small isolated mark near the right edge; it was left visible rather than retouched.

The GIF was verified as 4 frames at 170 ms each. Browser playback inspection could not be established: browser inventory returned `nodeRepl.fetch request failed` twice, including after a session reset. R5 was judged from the exact ordered frame set used by the GIF; this playback limitation is recorded rather than claiming a live browser playback check.

## Result

WALK RIGHT MOTION DESIGN BLOCKED

The external Passing frames are insufficient for this walk cycle. Recommended next inputs: two clearly distinct passing phases with legs gathered under the pelvis, plus complete, uncropped Contact A/B anchors that visibly exchange the forward leg and counter-swing the arms.

Production assets, source sheets, Runtime, builder, and manifest were not modified. No formal qualification, commit, or push was performed.
