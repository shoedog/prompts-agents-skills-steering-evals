# Judge spot-check (human review)

## baseline — rs-01 (seeded=True)

**Normalized findings block:**
```
## FINDINGS
VERDICT: REJECT
1. pagination.py:13 — `total_pages` returns 1 when `total_items == 0`, but contract specifies it should return 0
2. pagination.py:13 — `total_pages` adds 1 unconditionally, causing it to return extra pages for exact multiples (e.g., 3 pages instead of 2 for 10 items at 5 per page)
```
**Ground truth:**
```
This item is SEEDED. Ground-truth defects:
- id: rs-01-d1
  description: `total_items // page_size + 1` is not a correct ceiling; it over-counts by one whenever total_items is an exact multiple of page_size, and returns 1 for 0 items.
  acceptable_match: any finding stating that total_pages over-counts by one for exact multiples (or returns 1 for 0 items), or that `// + 1` is wrong ceiling division.
  reject_if: a vague 'pagination math looks off' that does not identify the exact-multiple/zero over-count or the `// + 1` idiom.
```
**Judge:** verdict=REJECT (flagged)  found=['rs-01-d1']  false_findings=0  item_pass=True

## baseline — rs-02 (seeded=True)

**Normalized findings block:**
```
## FINDINGS
VERDICT: REJECT
1. access.py:23 — Logic inverted: uses `!=` instead of `==`, causing owners to be denied access and non-owners to be granted access, the opposite of specification.
```
**Ground truth:**
```
This item is SEEDED. Ground-truth defects:
- id: rs-02-d1
  description: the ownership check uses `!=` where it should use `==`, so a non-admin is allowed precisely when they are NOT the owner.
  acceptable_match: any finding naming that the ownership comparison uses `!=` instead of `==`, letting non-owners access resources / granting access to the wrong users.
  reject_if: a generic 'access control looks risky/insecure' without identifying the `!=` vs `==` inversion or that non-owners are wrongly granted access.
```
**Judge:** verdict=REJECT (flagged)  found=['rs-02-d1']  false_findings=0  item_pass=True

## baseline — rs-03 (seeded=True)

**Normalized findings block:**
```
## FINDINGS
VERDICT: REJECT
1. ratelimit.py:15 — parse_rate_limit reads X-RateLimit-Limit (total quota) instead of X-RateLimit-Remaining (remaining calls), violating the contract that remaining must be the remaining calls, not the total quota.
```
**Ground truth:**
```
This item is SEEDED. Ground-truth defects:
- id: rs-03-d1
  description: reads `X-RateLimit-Limit` (the total quota) into `remaining` instead of `X-RateLimit-Remaining`.
  acceptable_match: any finding naming that `remaining` reads the Limit header instead of the Remaining header (wrong key), reporting total quota instead of remaining.
  reject_if: a generic 'header parsing may be wrong' without naming the Limit-vs-Remaining key mix-up.
```
**Judge:** verdict=REJECT (flagged)  found=['rs-03-d1']  false_findings=0  item_pass=True

## baseline — rs-04 (seeded=True)

**Normalized findings block:**
```
## FINDINGS
VERDICT: REJECT
1. validate.py:6 — Mutable default argument `warnings=[]` causes state to be shared across separate calls, violating the contract that "separate calls that omit `warnings` must not share state"; warnings accumulate across invocations.
```
**Ground truth:**
```
This item is SEEDED. Ground-truth defects:
- id: rs-04-d1
  description: `warnings=[]` is a mutable default evaluated once and shared across all calls that omit the argument.
  acceptable_match: any finding naming the mutable default argument `warnings=[]` being shared/accumulating across calls.
  reject_if: a generic 'default argument looks unusual' without identifying the shared-mutable-default accumulation bug.
```
**Judge:** verdict=REJECT (flagged)  found=['rs-04-d1']  false_findings=0  item_pass=True

## baseline — rs-05 (seeded=True)

**Normalized findings block:**
```
## FINDINGS
VERDICT: REJECT
1. io_utils.py:5-11 — File descriptor leak: if `parse_line(line)` on line 10 raises an exception, `f.close()` on line 11 is never executed, violating the contract requirement that the handle must ALWAYS be released on all code paths including exception paths.
2. io_utils.py:5 — Misleading comment: references a "checksum pass below" that does not exist, indicating incomplete or abandoned logic.
```
**Ground truth:**
```
This item is SEEDED. Ground-truth defects:
- id: rs-05-d1
  description: the file is opened manually without a context manager or try/finally, so if `parse_line` raises the `f.close()` below is skipped and the handle leaks.
  acceptable_match: any finding naming that the file handle is not closed / leaks when parse_line raises (missing with-statement or try/finally).
  reject_if: a finding that only suggests using a list comprehension or comments on style without identifying the unclosed-file-on-exception leak.
```
**Judge:** verdict=REJECT (flagged)  found=['rs-05-d1']  false_findings=1  item_pass=False

## baseline — rs-06 (seeded=True)

**Normalized findings block:**
```
## FINDINGS
VERDICT: REJECT
1. http_client.py:14 — `except Exception:` catches non-transient failures (HTTP 4xx, JSON decode errors) that must propagate per contract; should only catch transient errors.
2. http_client.py:16, 18 — Returning `None` instead of re-raising exceptions violates the contract requirement that non-transient failures be distinguishable from valid empty responses.
3. http_client.py:17 — `time.sleep()` is called but the `time` module is not imported, causing NameError at runtime.
```
**Ground truth:**
```
This item is SEEDED. Ground-truth defects:
- id: rs-06-d1
  description: the bare `except Exception` catches non-transient errors (4xx via raise_for_status, JSON decode errors, and even bugs) and, after exhausting retries, returns None instead of propagating them.
  acceptable_match: any finding naming that the broad `except Exception` swallows non-transient errors (4xx / decode errors) and returns None instead of propagating them.
  reject_if: a finding that only flags the sleep constant or the retry count, not the over-broad except that hides permanent errors.
```
**Judge:** verdict=REJECT (flagged)  found=['rs-06-d1']  false_findings=1  item_pass=False

## baseline — rs-07 (seeded=True)

**Normalized findings block:**
```
## FINDINGS
VERDICT: REJECT
1. tokens.py:5 — `datetime.now()` returns local time, not UTC; breaks contract requiring UTC comparison on hosts in any timezone. Must use `_utcnow()` or equivalent UTC time source.
```
**Ground truth:**
```
This item is SEEDED. Ground-truth defects:
- id: rs-07-d1
  description: `datetime.now()` returns naive LOCAL time, but `token.expires_at` is naive UTC; the two are compared as if both UTC.
  acceptable_match: any finding naming that datetime.now() is naive LOCAL time while expires_at is UTC (should be utcnow()/UTC-aware), skewing expiry by the timezone offset.
  reject_if: a generic 'timezone handling could be improved' without naming now() vs UTC or the local-offset skew.
```
**Judge:** verdict=REJECT (flagged)  found=['rs-07-d1']  false_findings=0  item_pass=True

## baseline — rs-08 (seeded=True)

**Normalized findings block:**
```
## FINDINGS
VERDICT: REJECT
1. finance.py:13 — `compound_balance` computes `principal * 1 + rate ** years` instead of `principal * (1 + rate) ** years`; missing parentheses causes operator precedence error and produces wrong results (1000.000125 instead of 1157.625 for the spec example).
```
**Ground truth:**
```
This item is SEEDED. Ground-truth defects:
- id: rs-08-d1
  description: `principal * 1 + rate ** years` evaluates as `principal + (rate ** years)` because `**` binds tighter than `*`/`+`; the intended `principal * (1 + rate) ** years` is missing its parentheses.
  acceptable_match: any finding naming the missing parentheses / operator precedence so it computes principal + rate**years rather than principal*(1+rate)**years.
  reject_if: a generic 'interest formula is wrong' without pointing at the precedence / missing-parentheses issue.
```
**Judge:** verdict=REJECT (flagged)  found=['rs-08-d1']  false_findings=0  item_pass=True

## baseline — rs-09 (seeded=True)

**Normalized findings block:**
```
## FINDINGS
VERDICT: REJECT
1. profile_cache.py:14 — `save()` does not update the cache with the persisted profile, violating the contract's guarantee that subsequent `get()` returns the just-saved data (causes stale reads if uid is already cached).
```
**Ground truth:**
```
This item is SEEDED. Ground-truth defects:
- id: rs-09-d1
  description: `save` writes to storage but never updates or invalidates `self._cache[uid]`, so a previously cached value stays after a save.
  acceptable_match: any finding naming that save() does not update or invalidate the cache entry, so get() returns stale data after a save.
  reject_if: a generic 'caching looks fragile' without identifying the missing cache update/invalidation in save.
```
**Judge:** verdict=REJECT (flagged)  found=['rs-09-d1']  false_findings=0  item_pass=True

## baseline — rs-10 (seeded=True)

**Normalized findings block:**
```
## FINDINGS
VERDICT: REJECT
1. text_utils.py:12 — `decode("utf-8")` raises UnicodeDecodeError when the byte slice ends mid-character, violating the contract's "never raise" guarantee
```
**Ground truth:**
```
This item is SEEDED. Ground-truth defects:
- id: rs-10-d1
  description: `encoded[:max_bytes]` can cut a multi-byte UTF-8 character in the middle; `.decode('utf-8')` on the truncated bytes then raises UnicodeDecodeError.
  acceptable_match: any finding naming that slicing the encoded bytes at max_bytes can split a multi-byte character and .decode() then raises (UnicodeDecodeError).
  reject_if: a generic 'unicode handling is risky' without identifying the byte-slice splitting a character or the decode raising.
```
**Judge:** verdict=REJECT (flagged)  found=['rs-10-d1']  false_findings=0  item_pass=True

## baseline — rs-11 (seeded=True)

**Normalized findings block:**
```
## FINDINGS
VERDICT: REJECT
1. batching.py:6 — `range(0, len(seq), size - 1)` should be `range(0, len(seq), size)` to produce non-overlapping chunks; the current implementation creates overlapping chunks where elements repeat across multiple outputs.
```
**Ground truth:**
```
This item is SEEDED. Ground-truth defects:
- id: rs-11-d1
  description: the range step is `size - 1` while each slice is `size` wide, so consecutive chunks overlap by one element instead of being disjoint.
  acceptable_match: any finding that identifies the loop step `size - 1` as wrong (should be `size`), evidenced either by overlapping/duplicated chunks or by the step becoming 0 when size == 1 (range ValueError); do not credit a report of either symptom that does not attribute it to the size-1 step.
  reject_if: a generic 'chunking looks wrong' without naming the step of size-1 / the overlap or duplication.
```
**Judge:** verdict=REJECT (flagged)  found=['rs-11-d1']  false_findings=0  item_pass=True

## baseline — rs-12 (seeded=True)

**Normalized findings block:**
```
## FINDINGS
VERDICT: REJECT
1. settings.py:4 — `resolve_retention()` uses `or` operator which treats 0 as falsy, but contract requires 0 to be returned unchanged; should use `if requested is None` check instead
```
**Ground truth:**
```
This item is SEEDED. Ground-truth defects:
- id: rs-12-d1
  description: `requested or DEFAULT_RETENTION_DAYS` treats `requested == 0` as falsy and replaces it with the default; only `None` should trigger the default.
  acceptable_match: any finding naming that `requested or DEFAULT` treats 0 as falsy so an explicit 0 is replaced by the default (should check `is None`).
  reject_if: a generic 'default handling is wrong' without identifying that 0 is swallowed by the truthiness/`or` check.
```
**Judge:** verdict=REJECT (flagged)  found=['rs-12-d1']  false_findings=0  item_pass=True

## baseline — rs-13 (seeded=True)

**Normalized findings block:**
```
## FINDINGS
VERDICT: REJECT
1. ledger.py:8 — `kind == "credit"` should be `kind == "CREDIT"` to match the contract's requirement for upper-case type strings; current code silently fails to accumulate any CREDIT totals.
2. ledger.py:6 — `int(float(amount) * 100)` truncates instead of rounding; should use `round(float(amount) * 100)` per the contract's "correctly rounded" requirement to avoid losing precision on fractional cents.
```
**Ground truth:**
```
This item is SEEDED. Ground-truth defects:
- id: rs-13-d1
  description: `int(float(amount) * 100)` truncates rather than rounds; binary float representation makes some exact decimals land just below the integer, losing a cent.
  acceptable_match: any finding naming that int(float(amount)*100) truncates due to float representation and under-counts cents (off by one cent), e.g. 2.30 -> 229.
  reject_if: a bare 'don't use floats for money' style note that does not identify an actual off-by-a-cent truncation/rounding error.
- id: rs-13-d2
  description: the type column holds upper-case 'CREDIT'/'DEBIT', but the code compares to lower-case 'credit', which never matches.
  acceptable_match: any finding naming the case mismatch: comparing to lower-case 'credit' when data is upper-case 'CREDIT', so credits are never summed (total always 0).
  reject_if: a generic 'the type check may be wrong' without identifying the upper/lower case mismatch or that credits are never counted.
```
**Judge:** verdict=REJECT (flagged)  found=['rs-13-d1', 'rs-13-d2']  false_findings=0  item_pass=True

## baseline — rs-14 (seeded=True)

**Normalized findings block:**
```
## FINDINGS
VERDICT: REJECT
1. billing_dates.py:12 — `calendar.monthrange(year, d.month)` should be `calendar.monthrange(year, month)` to clamp to the target month's days, not the original month's days; causes ValueError when original month has more days than target month (e.g., Jan 31 → Feb).
```
**Ground truth:**
```
This item is SEEDED. Ground-truth defects:
- id: rs-14-d1
  description: the clamp calls `calendar.monthrange(year, d.month)` using the SOURCE month `d.month` instead of the target `month`, so it clamps to the wrong month's length.
  acceptable_match: any finding naming that monthrange is called with the source month (d.month) instead of the target month, clamping to the wrong month's length (crash on Jan 31 / month-end dates).
  reject_if: a generic 'date math may be off' without identifying the wrong month passed to monthrange or the crash on 31-day source months.
```
**Judge:** verdict=REJECT (flagged)  found=['rs-14-d1']  false_findings=0  item_pass=True

## baseline — rs-15 (seeded=False)

**Normalized findings block:**
```
## FINDINGS
VERDICT: APPROVE
No findings.
```
**Ground truth:**
```
This item is CLEAN. There are NO ground-truth defects.
clean_rationale: Indices are correct for 1-indexed pages: start = (page-1)*page_size and end clamped to total; slicing never over-reads and the last partial page is returned.
tempting_non_defects (a finding matching one of these is a false finding):
- `(page - 1) * page_size` is the correct 1-indexed-to-offset conversion, not an off-by-one.
- `min(start + page_size, total)` correctly clamps the exclusive end so the final partial page is returned without reading past the end.
- page_count uses math.ceil, which correctly counts pages (unlike the `// + 1` anti-pattern).
```
**Judge:** verdict=APPROVE  found=[]  false_findings=0  item_pass=True

## baseline — rs-16 (seeded=False)

**Normalized findings block:**
```
## FINDINGS
VERDICT: APPROVE
No findings.
```
**Ground truth:**
```
This item is CLEAN. There are NO ground-truth defects.
clean_rationale: The mutable default trap is avoided: the default is None, and a fresh list is created inside the call when tags is None, so defaulted calls do not share state.
tempting_non_defects (a finding matching one of these is a false finding):
- `tags=None` plus `if tags is None: tags = []` is the correct idiom that AVOIDS the shared mutable-default-argument bug; each defaulted call gets its own list.
- appending to a caller-provided list and returning it is intended behaviour, not accidental mutation.
```
**Judge:** verdict=APPROVE  found=[]  false_findings=0  item_pass=True

## baseline — rs-17 (seeded=False)

**Normalized findings block:**
```
## FINDINGS
VERDICT: REJECT
1. txn.py:7 — If `conn.rollback()` raises an exception, it will mask the original exception, causing the caller to see the wrong error instead of the original failure from `fn` or `commit`, violating the contract requirement to re-raise the original exception.
```
**Ground truth:**
```
This item is CLEAN. There are NO ground-truth defects.
clean_rationale: On the success path the code commits before returning (the result is captured in a local, then `conn.commit()` runs, then the local is returned), so successful writes are persisted, not discarded; if `fn` raises, it rolls back and re-raises the original exception (no swallow); `finally` closes exactly once on every path.
tempting_non_defects (a finding matching one of these is a false finding):
- `conn.commit()` IS called on the success path (after `fn` returns, before `return result`), so successful writes are committed - they are NOT silently discarded.
- the `except Exception` does NOT swallow the error: it calls `rollback()` and then `raise`, which re-raises the original exception.
- the result is stored in a local before commit and returned afterwards; `finally: conn.close()` has no return statement, so it does not override the returned value.
- close() runs once (in finally) and is idempotent per the contract, so there is no double-close problem.
```
**Judge:** verdict=REJECT (flagged)  found=[]  false_findings=1  item_pass=False

## baseline — rs-18 (seeded=False)

**Normalized findings block:**
```
## FINDINGS
VERDICT: APPROVE
No findings.
```
**Ground truth:**
```
This item is CLEAN. There are NO ground-truth defects.
clean_rationale: Both operands are timezone-aware UTC, so the comparison is valid and correct; the >= boundary matches the contract that the exact expiry instant is expired.
tempting_non_defects (a finding matching one of these is a false finding):
- `datetime.now(timezone.utc)` returns an AWARE UTC datetime (unlike the buggy naive `datetime.now()`), so comparing to the aware `expires_at` is correct and does not raise.
- `>=` correctly treats the exact expiry instant as expired per the contract; it is not an off-by-one.
```
**Judge:** verdict=APPROVE  found=[]  false_findings=0  item_pass=True

## baseline — rs-19 (seeded=False)

**Normalized findings block:**
```
## FINDINGS
VERDICT: APPROVE
No findings.
```
**Ground truth:**
```
This item is CLEAN. There are NO ground-truth defects.
clean_rationale: startswith guard plus a slice at len(prefix) removes exactly the prefix and nothing else, and correctly handles the no-match and empty-prefix cases.
tempting_non_defects (a finding matching one of these is a false finding):
- `s[len(prefix):]` slices from exactly the character after the prefix - not an off-by-one (no +1/-1 needed).
- using startswith + slice deliberately avoids `str.lstrip(prefix)`, which would wrongly strip any leading character that appears in prefix.
- empty prefix: startswith('') is True and s[0:] returns s unchanged - correct.
```
**Judge:** verdict=APPROVE  found=[]  false_findings=0  item_pass=True

## baseline — rs-20 (seeded=False)

**Normalized findings block:**
```
## FINDINGS
VERDICT: APPROVE
No findings.
```
**Ground truth:**
```
This item is CLEAN. There are NO ground-truth defects.
clean_rationale: set() is write-through: it updates both the store and the cache entry, so a following get() is not stale; reload() clears the cache for a full refresh.
tempting_non_defects (a finding matching one of these is a false finding):
- unlike a stale-cache bug, `set()` updates `self._cache[key]` right after `save_config`, so the following `get()` returns the new value.
- `reload()` clears the whole cache so subsequent gets reload from the store.
```
**Judge:** verdict=APPROVE  found=[]  false_findings=0  item_pass=True
