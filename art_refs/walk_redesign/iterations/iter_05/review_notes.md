# Iteration 5 review

## Result: FAIL

F0 was retained as the shared character base. F1, F2, and F3 were edited from it using the separate pose diagrams.

| Check | Result | Finding |
|---|---|---|
| Leg exchange | FAIL | F2 repeats F0's left-back / right-forward foot arrangement instead of visibly exchanging the near and far legs. |
| Arm exchange | FAIL | F2 repeats F0's back-left / forward-right arm arrangement. |
| Passing pose | FAIL | F1 has a closer foot pass, but F3 still opens into a contact-like stance instead of the opposite crossing. |
| Character consistency | PASS | Reusing the same base kept face, hair, whale ornament, costume, and scale consistent across the four sprites. |
| Walk readability | FAIL | The unchanged contact silhouette dominates the cycle; the short foot movement does not clearly read as alternating steps. |
| Loop readability | PASS | F3 returns to the reused F0 with stable head placement and scale. |

## Target for iteration 6

The pose diagram alone still does not make the generator switch leg identity. Mark the actual A and B legs on a separate copy of F0 as a tracking reference, then request the reversed contact from that clearly labeled target. Remove all marks in the candidate output. Keep F1 from this set and redraw F2/F3 to make the two passing halves connect to their contacts.
