# Iteration 3 review

## Result: FAIL

The four frames were generated with the same Runtime side sprite, the Runtime front sprite for identity, and separate limb-pose diagrams. The diagrams improved frame-to-frame variation, especially in F1, but did not establish the required contact exchange.

| Check | Result | Finding |
|---|---|---|
| Leg exchange | FAIL | F0 and F2 still read as the same forward-right / trailing-left stance. The guide's A/B identity did not survive in the visible overlap. |
| Arm exchange | FAIL | The contact frames still use nearly the same arm swing relationship. |
| Passing pose | FAIL | F1 brings the feet closer, but F3 remains too spread and does not make the opposite leg pass clearly. |
| Character consistency | PASS | The four frames retain the same face, hair silhouette, whale ornament, maid costume, and compact body proportions; minor redraw differences are not a visible design change. |
| Walk readability | FAIL | There is some leg movement, but the repeated contact silhouette still reads as a small pose change over translation. |
| Loop readability | PASS | Frame scale and head placement remain steady from F3 back to F0, with no major snap. |

## Target for iteration 4

Make the two contact silhouettes geometrically distinct without relying only on A/B labels: use a heel-strike forward leg and a bent, lifted trailing foot in one contact, then reverse which side owns the foreground overlap in the other. Make the arms reach to clearly different endpoints. Keep a wider, shorter chibi silhouette close to the source. Give F3 an unmistakable close-foot crossover like F1, but with the opposite leg crossing forward.
