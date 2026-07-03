Review procedure — follow in order:
1. Walk this checklist against the diff, one item at a time: correctness of boundary conditions; error/exception paths; resource lifecycle (open/close, acquire/release); state mutation and aliasing; API-contract conformance with the surrounding code.
2. Disconfirm first: for each candidate finding, actively look for evidence it is NOT a bug before accepting it.
3. Default-REJECT: approve only if you completed the checklist and found no defect.
4. Verify separately: after drafting findings, re-derive each one from the diff alone; drop any you cannot re-derive.
Label these workspace sections literally: CHECKLIST, DISCONFIRM, VERIFY.
