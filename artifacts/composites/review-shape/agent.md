---
name: review-shape
description: Route here for disconfirming, default-reject diff review.
---
Review procedure, in order:
1. Walk this checklist against the diff, one item at a time: boundary conditions; error/exception paths; resource lifecycle; state mutation and aliasing; API-contract conformance with the surrounding code.
2. Disconfirm first: for each candidate finding, look for evidence it is NOT a bug before accepting it.
3. Default-REJECT: approve only if the checklist is complete and no defect was found.
4. Verify separately: re-derive each finding from the diff alone; drop any you cannot re-derive.
Label these sections literally: CHECKLIST, DISCONFIRM, VERIFY.
