# Iteration 6 review

## Result: FAIL

The marked-limb edit request failed twice with an image-service network error. A smaller two-image request using the clean shared F0 and the Contact B diagram did return a frame; the F0/F2 comparison still shows the same lead-foot side.

| Check | Result | Finding |
|---|---|---|
| Leg exchange | FAIL | F2 bends the trailing leg more, but the right foot remains forward as in F0; the lead leg is not unmistakably exchanged. |
| Arm exchange | FAIL | F2 retains the same back-left / forward-right arm endpoints as F0. |
| Passing pose | FAIL | F1 is compact, but F3 remains a spread pose instead of the opposite passing transition. |
| Character consistency | PASS | Uniform crop/scale/baseline alignment keeps the same character size and placement; the design remains consistent. |
| Walk readability | FAIL | The animation still emphasizes a wide stance and a small bend rather than an alternating walk. |
| Loop readability | PASS | F3 returns to F0 at the same scale and baseline without an obvious snap. |

## Target for iteration 7

Use a single annotated F0 target so the generator can identify the actual near and far legs directly. Request only F2 first, with the red-marked leg moved behind and the blue-marked leg brought forward. Preserve F0/F1/F3 from this set while testing that targeted edit.
