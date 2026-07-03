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

## treatment — rs-01 (seeded=True)

**Normalized findings block:**
```
## FINDINGS
VERDICT: REJECT
1. pagination.py:16 — Formula `total_items // page_size + 1` is incorrect; it returns 1 instead of 0 when total_items is 0 (fails contract), and returns too many pages when total_items is an exact multiple of page_size (e.g., returns 3 instead of 2 for 10 items with page_size 5).
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

## treatment — rs-02 (seeded=True)

**Normalized findings block:**
```
## FINDINGS
VERDICT: REJECT
1. access.py:23 — Logic operator inverted: `user.id != resource.owner_id` should be `user.id == resource.owner_id`; currently denies access to owners and allows non-owners.
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

## treatment — rs-03 (seeded=True)

**Normalized findings block:**
```
## FINDINGS
VERDICT: REJECT
1. ratelimit.py:13 — parse_rate_limit reads X-RateLimit-Limit (total quota) instead of X-RateLimit-Remaining (remaining calls) and assigns it to the remaining field, violating the contract that remaining must store remaining calls, not total quota.
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

## treatment — rs-04 (seeded=True)

**Normalized findings block:**
```
## FINDINGS
VERDICT: REJECT
1. validate.py:6 — Mutable default argument `warnings=[]` violates the contract that separate calls omitting the argument must not share state; should be `warnings=None` with fresh list initialization inside the function.
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

## treatment — rs-05 (seeded=True)

**Normalized findings block:**
```
## FINDINGS
VERDICT: REJECT
1. io_utils.py:8 — If `parse_line` raises an exception, the file handle is never closed, violating the contract requirement that it must ALWAYS be released on any code path (including exceptions). Use a try-finally block or restore the `with` context manager.
```
**Ground truth:**
```
This item is SEEDED. Ground-truth defects:
- id: rs-05-d1
  description: the file is opened manually without a context manager or try/finally, so if `parse_line` raises the `f.close()` below is skipped and the handle leaks.
  acceptable_match: any finding naming that the file handle is not closed / leaks when parse_line raises (missing with-statement or try/finally).
  reject_if: a finding that only suggests using a list comprehension or comments on style without identifying the unclosed-file-on-exception leak.
```
**Judge:** verdict=REJECT (flagged)  found=['rs-05-d1']  false_findings=0  item_pass=True

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
neutral_findings (true-but-out-of-scope; a finding matching one of these is NEITHER credited as a defect NOR a false finding — count it in neutral_matched):
- the retry branch calls `time.sleep(...)` and the shown diff hunk contains no `import time`, so a finding that `time` is unimported and will raise NameError is UNVERIFIABLE from this hunk alone (the import may already exist above the hunk in http_client.py). It is a true-but-out-of-scope import-visibility observation, not the seeded over-broad-except defect and not a false alarm.
```
**Judge:** verdict=REJECT (flagged)  found=['rs-06-d1']  false_findings=0  item_pass=True

## treatment — rs-06 (seeded=True)

**Normalized findings block:**
```
## FINDINGS
VERDICT: REJECT
1. http_client.py:15 — `except Exception:` catches non-transient failures (HTTP 4xx, JSON decode errors) that the contract requires to propagate to the caller for distinguishability.
2. http_client.py:17 — `return None` instead of re-raising non-transient errors violates the contract requirement that they be "distinguishable from a valid empty response."
3. http_client.py:18 — `time.sleep()` is called but `time` module is not imported, causing `NameError` at runtime when a retry is triggered.
```
**Ground truth:**
```
This item is SEEDED. Ground-truth defects:
- id: rs-06-d1
  description: the bare `except Exception` catches non-transient errors (4xx via raise_for_status, JSON decode errors, and even bugs) and, after exhausting retries, returns None instead of propagating them.
  acceptable_match: any finding naming that the broad `except Exception` swallows non-transient errors (4xx / decode errors) and returns None instead of propagating them.
  reject_if: a finding that only flags the sleep constant or the retry count, not the over-broad except that hides permanent errors.
neutral_findings (true-but-out-of-scope; a finding matching one of these is NEITHER credited as a defect NOR a false finding — count it in neutral_matched):
- the retry branch calls `time.sleep(...)` and the shown diff hunk contains no `import time`, so a finding that `time` is unimported and will raise NameError is UNVERIFIABLE from this hunk alone (the import may already exist above the hunk in http_client.py). It is a true-but-out-of-scope import-visibility observation, not the seeded over-broad-except defect and not a false alarm.
```
**Judge:** verdict=REJECT (flagged)  found=['rs-06-d1']  false_findings=0  item_pass=True

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
neutral_findings (true-but-out-of-scope; a finding matching one of these is NEITHER credited as a defect NOR a false finding — count it in neutral_matched):
- `expiry_label()` / `expiry_year()` dereference `token.expires_at` (via `.isoformat()` / `.year`) and would raise AttributeError if `expires_at` were None, and the sibling `has_expiry()` returning `expires_at is not None` suggests None is a valid state. This is a true secondary observation about the newly added helper functions, but it is out of scope for the `is_expired` UTC-comparison contract under review — neither the seeded timezone defect nor a false alarm.
```
**Judge:** verdict=REJECT (flagged)  found=['rs-07-d1']  false_findings=0  item_pass=True

## treatment — rs-07 (seeded=True)

**Normalized findings block:**
```
## FINDINGS
VERDICT: REJECT
1. tokens.py:5 — `is_expired()` uses `datetime.now()` which returns local time, not UTC; violates the contract requirement to evaluate expiry in UTC regardless of host timezone, causing incorrect expiry on non-UTC hosts.
2. tokens.py:10 — `expiry_label()` will raise `AttributeError` if `token.expires_at` is None; the presence of `has_expiry()` suggests None is valid, so this function should guard against it.
3. tokens.py:19 — `expiry_year()` will raise `AttributeError` if `token.expires_at` is None; same issue as `expiry_label()`.
```
**Ground truth:**
```
This item is SEEDED. Ground-truth defects:
- id: rs-07-d1
  description: `datetime.now()` returns naive LOCAL time, but `token.expires_at` is naive UTC; the two are compared as if both UTC.
  acceptable_match: any finding naming that datetime.now() is naive LOCAL time while expires_at is UTC (should be utcnow()/UTC-aware), skewing expiry by the timezone offset.
  reject_if: a generic 'timezone handling could be improved' without naming now() vs UTC or the local-offset skew.
neutral_findings (true-but-out-of-scope; a finding matching one of these is NEITHER credited as a defect NOR a false finding — count it in neutral_matched):
- `expiry_label()` / `expiry_year()` dereference `token.expires_at` (via `.isoformat()` / `.year`) and would raise AttributeError if `expires_at` were None, and the sibling `has_expiry()` returning `expires_at is not None` suggests None is a valid state. This is a true secondary observation about the newly added helper functions, but it is out of scope for the `is_expired` UTC-comparison contract under review — neither the seeded timezone defect nor a false alarm.
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

## treatment — rs-08 (seeded=True)

**Normalized findings block:**
```
## FINDINGS
VERDICT: REJECT
1. finance.py:15 — compound_balance formula is wrong: `principal * 1 + rate ** years` should be `principal * (1 + rate) ** years`; operator precedence makes this compute as (principal + rate^years) instead of the compound interest formula, producing 1000.0 instead of 1157.625 for the contract example.
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

## treatment — rs-09 (seeded=True)

**Normalized findings block:**
```
## FINDINGS
VERDICT: REJECT
1. profile_cache.py:13 — `save()` method does not update the cache after persisting, violating the contract requirement that "a subsequent `get(uid)` reflects the just-saved data (no stale reads)".
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

## treatment — rs-10 (seeded=True)

**Normalized findings block:**
```
## FINDINGS
VERDICT: REJECT
1. text_utils.py:8 — `truncate_utf8()` raises `UnicodeDecodeError` when truncating in the middle of a multi-byte UTF-8 character, violating the contract to "never raise" and "never split a multi-byte character"
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
