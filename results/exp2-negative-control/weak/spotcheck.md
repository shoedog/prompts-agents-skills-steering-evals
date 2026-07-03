# Judge spot-check (human review)

## baseline — rs-01 (seeded=True)

**Normalized findings block:**
```
## FINDINGS
VERDICT: REJECT
1. pagination.py:13 — `total_pages()` uses incorrect ceiling division formula; `total_items // page_size + 1` returns 1 when total_items is 0 (should return 0) and adds spurious pages when total_items is an exact multiple of page_size
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
1. pagination.py:14 — `total_pages()` formula `total_items // page_size + 1` violates contract: returns 1 (not 0) when total_items==0, and returns too many pages for exact multiples (e.g., 5 items at page_size 5 should return 1 page, not 2)
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
1. access.py:23 — Logic error: `user.id != resource.owner_id` should be `user.id == resource.owner_id`; current code denies access to owners and grants it to non-owners, inverting the access control.
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
1. access.py:23 — `can_access` grants access to non-owners and denies it to owners; the ownership check uses `!=` instead of `==`, inverting the entire access control policy for non-admin users
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
1. ratelimit.py:13 — `parse_rate_limit` reads `X-RateLimit-Limit` (total quota) into `remaining` instead of `X-RateLimit-Remaining` (remaining calls), violating the contract requirement that remaining must be the remaining calls, not the total quota.
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
1. ratelimit.py:15 — `parse_rate_limit` reads from `X-RateLimit-Limit` (total quota) instead of `X-RateLimit-Remaining` for the remaining field, violating the contract requirement that remaining must be "the REMAINING calls, not the total quota"
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
1. validate.py:6 — Mutable default argument `warnings=[]` causes state sharing between separate calls that omit the parameter, violating the contract that requires independent list instances per call.
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
1. validate.py:6 — Mutable default argument `warnings=[]` causes state sharing between calls; separate calls omitting the parameter will accumulate warnings from prior calls, violating the contract that each call returns warnings for only that record.
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
1. io_utils.py:6 — File handle leak: file is opened without context manager protection, so if `parse_line()` raises an exception, the file is never closed, leaking the file descriptor and violating the contract requirement.
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

## treatment — rs-05 (seeded=True)

**Normalized findings block:**
```
## FINDINGS
VERDICT: REJECT
1. io_utils.py:7 — File handle leaks if `parse_line(line)` raises an exception; `f.close()` is unreachable on exception paths, violating the contract that requires the handle to be released on all code paths. Use a try/finally or context manager to guarantee closure.
2. io_utils.py:13-20 — Unused helper functions `is_blank()` and `non_empty_lines()` should not be in this diff; they add code with no current purpose or call site.
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
1. http_client.py:11 — Catches all exceptions with `except Exception:`, retrying non-transient failures (HTTP 4xx, JSON decode errors) that should propagate immediately per contract
2. http_client.py:12–13 — Returns `None` instead of raising on non-transient failures, making them indistinguishable from valid empty responses and violating contract requirement
3. http_client.py:11 — Missing failure-type differentiation; does not distinguish transient (5xx, timeouts, connection errors) from non-transient (4xx, JSON decode) failures for selective retry logic
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
1. http_client.py:14 — Exception handler violates the contract by catching non-transient failures (HTTP 4xx and JSON decode errors) that must propagate immediately; instead it retries them and returns None, making them indistinguishable from valid empty responses.
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
1. tokens.py:5 — `datetime.now()` returns local time, not UTC; must use a UTC-aware call to evaluate expiry correctly regardless of host timezone
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
1. tokens.py:6 — `datetime.now()` returns local time, not UTC; comparison will be incorrect on hosts not in UTC timezone, violating the contract that "expiry must be evaluated in UTC regardless of the host's local timezone"
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
1. finance.py:15 — Formula is missing parentheses: `principal * 1 + rate ** years` should be `principal * (1 + rate) ** years`. Current formula produces 1000.000125 instead of 1157.625 for the contract example.
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
1. finance.py:15 — `compound_balance` uses `principal * 1 + rate ** years` instead of `principal * (1 + rate) ** years`; due to operator precedence, this computes the wrong result (off by orders of magnitude).
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
1. profile_cache.py:13 — `save()` persists to storage but does not update the cache, leaving stale data in the cache; the next `get(uid)` will return the old cached profile instead of the newly saved one, violating the "no stale reads" contract. Fix: add `self._cache[uid] = profile` after the `save_profile()` call.
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
1. profile_cache.py:13 — `save()` does not update the cache after persisting, violating the contract that "a subsequent `get(uid)` reflects the just-saved data (no stale reads)"
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
1. text_utils.py:10 — `.decode("utf-8")` raises UnicodeDecodeError when max_bytes cuts mid-multibyte-character, violating the "never raise" contract (e.g., `truncate_utf8("a😀", 2)` fails).
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
1. text_utils.py:7 — `truncate_utf8` can raise `UnicodeDecodeError` when truncation splits a multi-byte UTF-8 character; should use `decode("utf-8", errors="ignore")` to safely return the longest valid prefix.
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
