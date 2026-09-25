# Iteration 4 review

## Result: FAIL

The diagrams explicitly assigned A as the near-side foreground limb and B as the far-side limb. The generated contact frames still do not preserve a visible lead-leg exchange.

| Check | Result | Finding |
|---|---|---|
| Leg exchange | FAIL | F0 and F2 both read as a left-back / right-forward stance; the raised rear heel is too small a distinction to prove the lead changed. |
| Arm exchange | FAIL | Both contacts keep arms spread in the same left-back / right-forward arrangement. |
| Passing pose | FAIL | F1 is closer to passing, but F3 is still a separated stance and the shin crossover is not clear in both directions. |
| Character consistency | PASS | The character identity and short-body proportions stay consistent across the set; the measured silhouette ratios are close to the source and pose spread accounts for most width changes. |
| Walk readability | FAIL | The cycle still reads as repeated wide poses with arm motion, not a clear alternating walk. |
| Loop readability | PASS | F3 and F0 share the same head placement and overall scale; the loop transition has no visible size or anchor jump. |

## Target for iteration 5

Use the same generated F0 as the shared character base for all four frames so head, face, hair, torso, and costume stay identical. Regenerate each limb pose from its guide, with F2 visibly putting the near-side A leg behind and far-side B leg ahead, and both passing frames showing close, opposite shin crossings. Keep generous transparent margin so the character remains compact rather than filling the tall canvas.
