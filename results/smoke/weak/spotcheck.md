# Judge spot-check (human review)

## baseline — sm-01 (seeded=True)

**Normalized findings block:**
```
## FINDINGS
VERDICT: REJECT
1. recent.py:2 — Formula `items[-n - 1:]` is off-by-one: returns n+1 elements instead of n for normal cases (e.g., `last_n([1,2,3,4,5], 2)` returns `[3,4,5]` not `[4,5]`)
2. recent.py:2 — Incorrect result for n=0: returns the last element instead of empty list (e.g., `last_n([1,2,3], 0)` returns `[3]` not `[]`)
```
**Ground truth:**
```
This item is SEEDED. Ground-truth defects:
- id: sm-01-d1
  description: `items[-n - 1:]` returns the last n+1 elements instead of the last n.
  acceptable_match: any finding naming that the slice `[-n-1:]` returns n+1 items / one extra element (should be `[-n:]`).
  reject_if: a generic 'slicing looks wrong' without noting the extra element or the -n-1.
```
**Judge:** verdict=REJECT (flagged)  found=['sm-01-d1']  false_findings=0  item_pass=True

## baseline — sm-02 (seeded=True)

**Normalized findings block:**
```
## FINDINGS
VERDICT: REJECT
1. cart.py:1 — Mutable default argument `basket=[]` causes separate calls to share the same basket list, violating the contract that each omitted call should get a fresh basket.
```
**Ground truth:**
```
This item is SEEDED. Ground-truth defects:
- id: sm-02-d1
  description: `basket=[]` is a mutable default evaluated once and shared across all calls that omit it.
  acceptable_match: any finding naming the mutable default argument `basket=[]` shared/accumulating across calls.
  reject_if: a generic 'default looks odd' without identifying the shared mutable default / accumulation.
```
**Judge:** verdict=REJECT (flagged)  found=['sm-02-d1']  false_findings=0  item_pass=True

## baseline — sm-03 (seeded=True)

**Normalized findings block:**
```
## FINDINGS
VERDICT: REJECT
1. eligibility.py:3 — Logic operator is `and` but contract specifies `or`; rejects both adults without consent and minors with consent
```
**Ground truth:**
```
This item is SEEDED. Ground-truth defects:
- id: sm-03-d1
  description: the contract requires OR (adult OR consent) but the code uses `and`, requiring both.
  acceptable_match: any finding naming that the condition uses `and` instead of `or`, so both are required and adults-without-consent / consenting-minors are wrongly rejected.
  reject_if: a generic 'eligibility check is wrong' without naming and-vs-or.
```
**Judge:** verdict=REJECT (flagged)  found=['sm-03-d1']  false_findings=0  item_pass=True

## baseline — sm-04 (seeded=False)

**Normalized findings block:**
```
## FINDINGS
VERDICT: APPROVE
No findings.
```
**Ground truth:**
```
This item is CLEAN. There are NO ground-truth defects.
clean_rationale: None sentinel avoids a shared default, and dict(base) copies before update, so neither input is mutated and defaulted calls do not share state.
tempting_non_defects (a finding matching one of these is a false finding):
- `extra=None` with `if extra is None: extra = {}` avoids the shared mutable-default trap.
- `dict(base)` makes a copy, so `base` is never mutated by `.update()`; extra is only read.
```
**Judge:** verdict=APPROVE  found=[]  false_findings=0  item_pass=True

## baseline — sm-05 (seeded=False)

**Normalized findings block:**
```
## FINDINGS
VERDICT: APPROVE
No findings.
```
**Ground truth:**
```
This item is CLEAN. There are NO ground-truth defects.
clean_rationale: range step and slice width both equal size, so every element is covered exactly once with no overlap or gap; the final short batch is handled by slice clamping.
tempting_non_defects (a finding matching one of these is a false finding):
- step and slice width are both `size`, so chunks neither overlap nor skip - contrast the buggy `range(..., size-1)` variant.
- the final short batch is produced correctly by Python slice clamping.
```
**Judge:** verdict=APPROVE  found=[]  false_findings=0  item_pass=True

## treatment — sm-01 (seeded=True)

**Normalized findings block:**
```
## FINDINGS
VERDICT: REJECT
1. recent.py:2 — The slice `items[-n-1:]` is off by one and returns `n+1` elements instead of `n` elements, violating the contract; should be `items[-n:]` when n > 0, else `[]`.
```
**Ground truth:**
```
This item is SEEDED. Ground-truth defects:
- id: sm-01-d1
  description: `items[-n - 1:]` returns the last n+1 elements instead of the last n.
  acceptable_match: any finding naming that the slice `[-n-1:]` returns n+1 items / one extra element (should be `[-n:]`).
  reject_if: a generic 'slicing looks wrong' without noting the extra element or the -n-1.
```
**Judge:** verdict=REJECT (flagged)  found=['sm-01-d1']  false_findings=0  item_pass=True

## treatment — sm-02 (seeded=True)

**Normalized findings block:**
```
## FINDINGS
VERDICT: REJECT
1. cart.py:1 — Mutable default argument `basket=[]` causes all calls without an explicit basket to share the same list, violating the contract that each call without a basket must get an independent empty basket.
```
**Ground truth:**
```
This item is SEEDED. Ground-truth defects:
- id: sm-02-d1
  description: `basket=[]` is a mutable default evaluated once and shared across all calls that omit it.
  acceptable_match: any finding naming the mutable default argument `basket=[]` shared/accumulating across calls.
  reject_if: a generic 'default looks odd' without identifying the shared mutable default / accumulation.
```
**Judge:** verdict=REJECT (flagged)  found=['sm-02-d1']  false_findings=0  item_pass=True

## treatment — sm-03 (seeded=True)

**Normalized findings block:**
```
## FINDINGS
VERDICT: REJECT
1. eligibility.py:3 — Logical operator AND should be OR; code requires both age >= 18 AND has_consent=True, but contract specifies either condition suffices. An adult without consent is incorrectly denied access.
```
**Ground truth:**
```
This item is SEEDED. Ground-truth defects:
- id: sm-03-d1
  description: the contract requires OR (adult OR consent) but the code uses `and`, requiring both.
  acceptable_match: any finding naming that the condition uses `and` instead of `or`, so both are required and adults-without-consent / consenting-minors are wrongly rejected.
  reject_if: a generic 'eligibility check is wrong' without naming and-vs-or.
```
**Judge:** verdict=REJECT (flagged)  found=['sm-03-d1']  false_findings=0  item_pass=True

## treatment — sm-04 (seeded=False)

**Normalized findings block:**
```
## FINDINGS
VERDICT: APPROVE
No findings.
```
**Ground truth:**
```
This item is CLEAN. There are NO ground-truth defects.
clean_rationale: None sentinel avoids a shared default, and dict(base) copies before update, so neither input is mutated and defaulted calls do not share state.
tempting_non_defects (a finding matching one of these is a false finding):
- `extra=None` with `if extra is None: extra = {}` avoids the shared mutable-default trap.
- `dict(base)` makes a copy, so `base` is never mutated by `.update()`; extra is only read.
```
**Judge:** verdict=APPROVE  found=[]  false_findings=0  item_pass=True

## treatment — sm-05 (seeded=False)

**Normalized findings block:**
```
## FINDINGS
VERDICT: APPROVE
No findings.
```
**Ground truth:**
```
This item is CLEAN. There are NO ground-truth defects.
clean_rationale: range step and slice width both equal size, so every element is covered exactly once with no overlap or gap; the final short batch is handled by slice clamping.
tempting_non_defects (a finding matching one of these is a false finding):
- step and slice width are both `size`, so chunks neither overlap nor skip - contrast the buggy `range(..., size-1)` variant.
- the final short batch is produced correctly by Python slice clamping.
```
**Judge:** verdict=APPROVE  found=[]  false_findings=0  item_pass=True
