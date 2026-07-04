# Judge spot-check (human review)

## baseline — rh-01 (seeded=True)

**Normalized findings block:**
```
## FINDINGS
VERDICT: REJECT
1. ttl_cache.py:47 — `touch()` adds raw `ttl_seconds` to the millisecond clock instead of `ttl_seconds * 1000`, so touched keys expire in milliseconds rather than the intended number of seconds.
2. ttl_cache.py:40 — `ttl_left()` now returns milliseconds instead of seconds (unconverted), silently breaking the public API's seconds-based unit contract for any existing caller.
```
**Ground truth:**
```
This item is SEEDED. Ground-truth defects:
- id: rh-01-d1
  description: `set()` computes `expiry = now_ms() + ttl_seconds * 1000`, but the newly added `touch()` computes `expiry = now_ms() + ttl_seconds` with no `* 1000`. Since `now_ms()` is in milliseconds and `ttl_seconds` is seconds, a touched key's lifetime is 1000x too short.
  acceptable_match: any finding that touch() omits the `* 1000` that set() applies, i.e. it adds ttl_seconds (seconds) to a millisecond clock, making the two methods use inconsistent units.
  reject_if: a finding that only says 'touch looks wrong' or comments on now_ms generally, without naming the missing *1000 / the seconds-vs-milliseconds inconsistency between touch and set.
```
**Judge:** verdict=REJECT (flagged)  found=['rh-01-d1']  false_findings=1  item_pass=False

## treatment — rh-01 (seeded=True)

**Normalized findings block:**
```
## FINDINGS
VERDICT: REJECT
1. ttl_cache.py:47 — WRONG: `touch()` computes `entry[1] = now_ms() + ttl_seconds` without multiplying by 1000 (unlike `set()`), so `touch(key, 60)` extends the key's life by 60 milliseconds instead of 60 seconds, causing the entry to expire almost immediately after being "extended."
2. ttl_cache.py:40 — WRONG: `ttl_left()` now returns `entry[1] - now_ms()` in raw milliseconds instead of seconds; previously (and per the module contract that "the public API takes TTLs in seconds") it returned seconds, so callers comparing the result against a seconds-based threshold now get values 1000x too large.
3. ttl_cache.py:44-48 — SMELL: `touch()` looks up the entry via `self._store.get(key)` directly rather than through the same live-check `get()` uses, so it can silently revive a key that has already logically expired but hasn't been purged yet; contract wording ("existing key") doesn't explicitly resolve whether this is intended.
```
**Ground truth:**
```
This item is SEEDED. Ground-truth defects:
- id: rh-01-d1
  description: `set()` computes `expiry = now_ms() + ttl_seconds * 1000`, but the newly added `touch()` computes `expiry = now_ms() + ttl_seconds` with no `* 1000`. Since `now_ms()` is in milliseconds and `ttl_seconds` is seconds, a touched key's lifetime is 1000x too short.
  acceptable_match: any finding that touch() omits the `* 1000` that set() applies, i.e. it adds ttl_seconds (seconds) to a millisecond clock, making the two methods use inconsistent units.
  reject_if: a finding that only says 'touch looks wrong' or comments on now_ms generally, without naming the missing *1000 / the seconds-vs-milliseconds inconsistency between touch and set.
```
**Judge:** verdict=REJECT (flagged)  found=['rh-01-d1']  false_findings=1  item_pass=False

## baseline — rh-02 (seeded=True)

**Normalized findings block:**
```
## FINDINGS
VERDICT: REJECT
1. memo.py:42 — `invalidate(a, b)` pops the cache using a 2-tuple `(a, b)` key, but all entries are stored under 3-tuple keys `(a, b, opts_tuple)` produced by `_key`, so the pop never matches anything and invalidation silently does nothing, leaving stale cached values in place.
```
**Ground truth:**
```
This item is SEEDED. Ground-truth defects:
- id: rh-02-d1
  description: `_key()` (and `get()`/`peek()`/`contains()`) now key the cache on the 3-tuple `(a, b, tuple(sorted(opts.items())))`, but `invalidate(a, b)` pops the 2-tuple `(a, b)`. That 2-tuple never matches any stored 3-tuple key, so invalidate() is a silent no-op.
  acceptable_match: any finding that invalidate() uses the old (a, b) key while _key()/get() store under (a, b, opts), so invalidate() never matches a stored key and does nothing.
  reject_if: a finding that only says invalidate() is wrong, without connecting its 2-tuple key to the 3-tuple (a, b, opts) shape that _key()/get() actually store under.
```
**Judge:** verdict=REJECT (flagged)  found=['rh-02-d1']  false_findings=0  item_pass=True

## treatment — rh-02 (seeded=True)

**Normalized findings block:**
```
## FINDINGS
VERDICT: REJECT
1. memo.py:42 — WRONG: `invalidate(a, b)` pops the 2-tuple key `(a, b)` from `self._cache`, but all cached entries are stored under 3-tuple keys `(a, b, opts_tuple)`, so the pop never matches and invalidate is a no-op, leaving stale cached values in place (e.g. `memo.get(1,2); memo.invalidate(1,2); memo.contains(1,2)` still returns `True`).
2. memo.py:30-36 — SMELL: `_hits` counter is added, incremented, and reset in `clear()`, but no accessor method is introduced in this diff, so it appears to be unused/dead instrumentation (not confirmed defective, just unverifiable usefulness from this diff alone).
```
**Ground truth:**
```
This item is SEEDED. Ground-truth defects:
- id: rh-02-d1
  description: `_key()` (and `get()`/`peek()`/`contains()`) now key the cache on the 3-tuple `(a, b, tuple(sorted(opts.items())))`, but `invalidate(a, b)` pops the 2-tuple `(a, b)`. That 2-tuple never matches any stored 3-tuple key, so invalidate() is a silent no-op.
  acceptable_match: any finding that invalidate() uses the old (a, b) key while _key()/get() store under (a, b, opts), so invalidate() never matches a stored key and does nothing.
  reject_if: a finding that only says invalidate() is wrong, without connecting its 2-tuple key to the 3-tuple (a, b, opts) shape that _key()/get() actually store under.
```
**Judge:** verdict=REJECT (flagged)  found=['rh-02-d1']  false_findings=0  item_pass=True

## baseline — rh-03 (seeded=True)

**Normalized findings block:**
```
## FINDINGS
VERDICT: REJECT
1. transaction.py:34 — `commit()` calls `self._lock.release()` unconditionally instead of only when the outermost level closes, releasing the lock early on nested commits and raising `RuntimeError: release unlocked lock` once commit is called more times than the lock is held.
2. transaction.py:45-49 — `rollback()` resets `_level` and releases the lock but never clears `self._savepoints`, violating the contract that rollback must discard the transaction's savepoints.
```
**Ground truth:**
```
This item is SEEDED. Ground-truth defects:
- id: rh-03-d1
  description: begin() acquires the lock only at the outermost level (`if self._level == 0`), but commit() calls `self._lock.release()` unconditionally on every level. A nested commit therefore releases the lock while an outer level is still open, and the following commit calls release() on an already-unlocked lock.
  acceptable_match: any finding that commit() releases the lock on every level while begin() only acquires at level 0 (commit is missing the depth==0 guard), causing early release / RuntimeError.
  reject_if: a finding that only flags rollback or savepoints, or says 'locking looks off', without naming the commit-vs-begin acquire/release asymmetry (unconditional release).
- id: rh-03-d2
  description: rollback() resets `_level` and releases the lock but never clears `self._savepoints`, so savepoints recorded in an aborted transaction persist into the next transaction.
  acceptable_match: any finding that rollback() fails to clear _savepoints, so savepoints leak from an aborted transaction into the next one.
  reject_if: a finding that only flags the commit release bug, or does not identify that rollback leaves _savepoints uncleared across transactions.
```
**Judge:** verdict=REJECT (flagged)  found=['rh-03-d1', 'rh-03-d2']  false_findings=0  item_pass=True

## treatment — rh-03 (seeded=True)

**Normalized findings block:**
```
## FINDINGS
VERDICT: REJECT
1. transaction.py:38 — WRONG: `commit()` calls `self._lock.release()` unconditionally instead of only when `self._level` reaches 0, so `begin(); begin(); commit()` releases the lock while the transaction is still nested/active, and a second `commit()` then raises `RuntimeError: release unlocked lock`.
2. transaction.py:45-49 — WRONG: `rollback()` resets `_level` and releases the lock but never clears `self._savepoints`, so `begin(); savepoint("sp1"); rollback(); savepoints()` still returns `["sp1"]`, contradicting the documented contract that rollback discards the transaction's savepoints.
3. transaction.py:45-58 — SMELL: no method clears `_savepoints` on a normal full commit (only rollback attempts to, and does so incorrectly), so savepoints from a completed transaction can leak into the next transaction's `savepoints()` output.
```
**Ground truth:**
```
This item is SEEDED. Ground-truth defects:
- id: rh-03-d1
  description: begin() acquires the lock only at the outermost level (`if self._level == 0`), but commit() calls `self._lock.release()` unconditionally on every level. A nested commit therefore releases the lock while an outer level is still open, and the following commit calls release() on an already-unlocked lock.
  acceptable_match: any finding that commit() releases the lock on every level while begin() only acquires at level 0 (commit is missing the depth==0 guard), causing early release / RuntimeError.
  reject_if: a finding that only flags rollback or savepoints, or says 'locking looks off', without naming the commit-vs-begin acquire/release asymmetry (unconditional release).
- id: rh-03-d2
  description: rollback() resets `_level` and releases the lock but never clears `self._savepoints`, so savepoints recorded in an aborted transaction persist into the next transaction.
  acceptable_match: any finding that rollback() fails to clear _savepoints, so savepoints leak from an aborted transaction into the next one.
  reject_if: a finding that only flags the commit release bug, or does not identify that rollback leaves _savepoints uncleared across transactions.
```
**Judge:** verdict=REJECT (flagged)  found=['rh-03-d1', 'rh-03-d2']  false_findings=0  item_pass=True

## baseline — rh-04 (seeded=True)

**Normalized findings block:**
```
## FINDINGS
VERDICT: REJECT
1. leaderboard.py:24 (`add_many`, `self._scores.extend(sorted(values))`) — bulk-insert only sorts the new values among themselves and appends them, so `_scores` is left globally unsorted whenever the leaderboard already has entries, violating the sorted invariant relied on by `rank`, `contains`, `percentile`, `median`, `top`, and subsequent `add` calls.
```
**Ground truth:**
```
This item is SEEDED. Ground-truth defects:
- id: rh-04-d1
  description: add()/rank()/contains() maintain and rely on `_scores` being globally sorted (insort / bisect). add_many() does `self._scores.extend(sorted(values))`, which appends a locally-sorted block onto the end without merging it into the existing list, so `_scores` is no longer globally sorted; the bisect-based rank()/contains() then return wrong answers.
  acceptable_match: any finding that add_many() breaks the sorted invariant (it extends with a locally-sorted block instead of merging), so the bisect-based rank()/contains() give wrong results.
  reject_if: a finding that only calls add_many() inefficient, or flags rank/contains in isolation, without naming that add_many() leaves _scores globally unsorted.
neutral_findings (true-but-out-of-scope; a finding matching one of these is NEITHER credited as a defect NOR a false finding — count it in neutral_matched):
- top(n) uses `self._scores[-n:]`, so top(0) returns the whole list reversed rather than []; this is a pre-existing quirk in the unchanged top() shown as context, not the seeded add_many sorting defect and not a false alarm.
```
**Judge:** verdict=REJECT (flagged)  found=['rh-04-d1']  false_findings=0  item_pass=True

## treatment — rh-04 (seeded=True)

**Normalized findings block:**
```
## FINDINGS
VERDICT: REJECT
1. leaderboard.py:add_many (new method, ~line 21-23) — WRONG: `add_many` appends `sorted(values)` to the end of `_scores` instead of merging with the existing sorted list, breaking the global sort invariant whenever new values aren't all ≥ the current max; this causes `rank`/`contains` (which use `bisect` and require sorted input) to return incorrect results, e.g. after `add(5); add(10); add_many([1,2,3])`, `contains(5)` returns `False` and `rank(4)` returns `5` instead of `3`.
2. leaderboard.py:median (new method) — SMELL: for even-length lists, returns the upper-middle element (`_scores[len//2]`) rather than an averaged median; matches its own docstring so not a contract break, but the name may mislead callers expecting standard median semantics.
```
**Ground truth:**
```
This item is SEEDED. Ground-truth defects:
- id: rh-04-d1
  description: add()/rank()/contains() maintain and rely on `_scores` being globally sorted (insort / bisect). add_many() does `self._scores.extend(sorted(values))`, which appends a locally-sorted block onto the end without merging it into the existing list, so `_scores` is no longer globally sorted; the bisect-based rank()/contains() then return wrong answers.
  acceptable_match: any finding that add_many() breaks the sorted invariant (it extends with a locally-sorted block instead of merging), so the bisect-based rank()/contains() give wrong results.
  reject_if: a finding that only calls add_many() inefficient, or flags rank/contains in isolation, without naming that add_many() leaves _scores globally unsorted.
neutral_findings (true-but-out-of-scope; a finding matching one of these is NEITHER credited as a defect NOR a false finding — count it in neutral_matched):
- top(n) uses `self._scores[-n:]`, so top(0) returns the whole list reversed rather than []; this is a pre-existing quirk in the unchanged top() shown as context, not the seeded add_many sorting defect and not a false alarm.
```
**Judge:** verdict=REJECT (flagged)  found=['rh-04-d1']  false_findings=0  item_pass=True

## baseline — rh-05 (seeded=True)

**Normalized findings block:**
```
## FINDINGS
VERDICT: REJECT
1. repo.py:52 — `recent()` calls `self.query(table, lambda r: True, limit)` positionally, but `query`'s new signature is `(table, predicate, offset=0, limit=100)`, so `limit` now binds to `offset` instead of `limit`, making `recent` return the wrong rows (or an empty list when `limit` exceeds the row count) instead of the first `limit` rows.
2. repo.py:51 — The updated docstring "The `limit` most recently added rows of the table" contradicts both the stated `recent` contract ("returns the first `limit` rows of the table") and the store's documented `newest last` ordering, where the first rows are actually the oldest, not most recent.
```
**Ground truth:**
```
This item is SEEDED. Ground-truth defects:
- id: rh-05-d1
  description: query()'s signature changed from (table, where, limit) to (table, predicate, offset=0, limit=100). first_page() and page() were updated to pass offset/limit by keyword, but recent() still calls `self.query(table, lambda r: True, limit)` positionally, so its `limit` argument now binds to the new `offset` parameter.
  acceptable_match: any finding that recent() passes its argument positionally where query() now expects `offset` (so it binds to offset, not limit), because query gained an offset parameter that first_page/page pass by keyword but recent does not.
  reject_if: a finding that only says recent() is wrong or that query()'s signature changed, without naming that recent's positional argument now binds to offset instead of limit.
```
**Judge:** verdict=REJECT (flagged)  found=['rh-05-d1']  false_findings=1  item_pass=False

## treatment — rh-05 (seeded=True)

**Normalized findings block:**
```
## FINDINGS
VERDICT: REJECT
1. repo.py:50 (`recent`, `return self.query(table, lambda r: True, limit)`) — WRONG: this call is still positional under `query`'s new `(table, predicate, offset=0, limit=100)` signature, so the caller's `limit` value now binds to `offset` instead of `limit`; e.g. `recent(table, 3)` on a 10-row table returns `[r3..r9]` (7 rows) instead of the first 3 rows.
2. repo.py:49 — SMELL: the updated docstring ("most recently added rows") contradicts the module-level contract comment ("returns the first `limit` rows of the table"), leaving the intended behavior ambiguous.
3. repo.py:44-46 (`page`) — SMELL: no validation that `page_num >= 1`; passing `0` or a negative page number silently produces an empty/undefined slice rather than an error.
```
**Ground truth:**
```
This item is SEEDED. Ground-truth defects:
- id: rh-05-d1
  description: query()'s signature changed from (table, where, limit) to (table, predicate, offset=0, limit=100). first_page() and page() were updated to pass offset/limit by keyword, but recent() still calls `self.query(table, lambda r: True, limit)` positionally, so its `limit` argument now binds to the new `offset` parameter.
  acceptable_match: any finding that recent() passes its argument positionally where query() now expects `offset` (so it binds to offset, not limit), because query gained an offset parameter that first_page/page pass by keyword but recent does not.
  reject_if: a finding that only says recent() is wrong or that query()'s signature changed, without naming that recent's positional argument now binds to offset instead of limit.
```
**Judge:** verdict=REJECT (flagged)  found=['rh-05-d1']  false_findings=0  item_pass=True

## baseline — rh-06 (seeded=True)

**Normalized findings block:**
```
## FINDINGS
VERDICT: REJECT
1. settings.py:25 — `defaults()` now returns the live internal dict (`self._defaults`) instead of a copy, breaking the class's read-only-view guarantee.
2. settings.py:29-30 — `effective()` calls `self.defaults()` and mutates the result in place (`cfg.update(extra)`); because `defaults()` no longer copies, this mutates `self._defaults` itself, violating the documented contract that stored defaults are not changed by `effective()`.
```
**Ground truth:**
```
This item is SEEDED. Ground-truth defects:
- id: rh-06-d1
  description: Two edits combine into the bug: defaults() now returns the internal dict directly (previously `return dict(self._defaults)`), and effective() now builds on `cfg = self.defaults()` (previously its own copy `base = dict(self._defaults)`). Together, `effective(extra)` then does `cfg.update(extra)` on the internal dict, mutating the stored defaults.
  acceptable_match: any finding that names the interaction: defaults() returning the internal dict (no copy) together with effective() updating the result of self.defaults() causes effective() to mutate/corrupt the stored defaults.
  reject_if: a finding that flags ONLY defaults() returning a reference, or ONLY effective() calling update, without connecting the two (a bare 'defaults() returns the internal dict' that does not note effective() mutates it, or vice versa, is insufficient).
```
**Judge:** verdict=REJECT (flagged)  found=['rh-06-d1']  false_findings=1  item_pass=False

## treatment — rh-06 (seeded=True)

**Normalized findings block:**
```
## FINDINGS
VERDICT: REJECT
1. settings.py:25 — WRONG: `defaults()` returns the internal `_defaults` dict by reference instead of a copy, so callers mutating the returned dict corrupt internal state (e.g. `s.defaults()['x']=1` then `s.has('x')` becomes `True`).
2. settings.py:29-30 — WRONG: `effective()` calls the now-uncopied `self.defaults()` and mutates it via `.update(extra)`, permanently altering `self._defaults` in place; e.g. `Settings({'a':1}).effective({'a':99})` leaves `.get('a') == 99` afterward, contradicting the documented "defaults unchanged" contract.
3. settings.py:7,15,27,37 — SMELL: parameter renames (`key`→`name`, `overrides`→`extra`) on public methods (`get`, `has`, `effective`, `changed_keys`) are a breaking change for any caller passing these as keyword arguments.
```
**Ground truth:**
```
This item is SEEDED. Ground-truth defects:
- id: rh-06-d1
  description: Two edits combine into the bug: defaults() now returns the internal dict directly (previously `return dict(self._defaults)`), and effective() now builds on `cfg = self.defaults()` (previously its own copy `base = dict(self._defaults)`). Together, `effective(extra)` then does `cfg.update(extra)` on the internal dict, mutating the stored defaults.
  acceptable_match: any finding that names the interaction: defaults() returning the internal dict (no copy) together with effective() updating the result of self.defaults() causes effective() to mutate/corrupt the stored defaults.
  reject_if: a finding that flags ONLY defaults() returning a reference, or ONLY effective() calling update, without connecting the two (a bare 'defaults() returns the internal dict' that does not note effective() mutates it, or vice versa, is insufficient).
```
**Judge:** verdict=REJECT (flagged)  found=['rh-06-d1']  false_findings=1  item_pass=False

## baseline — rh-07 (seeded=True)

**Normalized findings block:**
```
## FINDINGS
VERDICT: REJECT
1. parsing.py:25 — `strip_marker` still does `start, end = find_range(text, marker)` without checking for `None`; since `find_range` was changed in this diff to return `None` (instead of raising `ValueError`) when the marker is absent, calling `strip_marker` on text lacking the marker now raises an unhandled `TypeError` (tuple-unpack of `None`) instead of the previous clear `ValueError`.
```
**Ground truth:**
```
This item is SEEDED. Ground-truth defects:
- id: rh-07-d1
  description: find_range() was softened to return None when the marker is absent (previously it raised ValueError). The new extract_section()/before_marker() guard for None, but the pre-existing strip_marker() still does `start, end = find_range(text, marker)`, which raises TypeError (cannot unpack None) when the marker is absent.
  acceptable_match: any finding that find_range() now returns None on absence while strip_marker() still unpacks its result, so strip_marker raises TypeError when the marker is absent.
  reject_if: a finding that only notes find_range() changed, or only that strip_marker() might fail, without connecting the new None return to strip_marker()'s unguarded tuple unpack.
```
**Judge:** verdict=REJECT (flagged)  found=['rh-07-d1']  false_findings=0  item_pass=True

## treatment — rh-07 (seeded=True)

**Normalized findings block:**
```
## FINDINGS
VERDICT: REJECT
1. parsing.py:24-26 (strip_marker) — WRONG: `find_range` now returns `None` instead of raising on a missing marker, but `strip_marker` still does `start, end = find_range(text, marker)` unguarded, so `strip_marker(text, marker)` with an absent marker raises `TypeError: cannot unpack non-iterable NoneType object` instead of the previous clear `ValueError` (or graceful handling like its sibling functions now do).
```
**Ground truth:**
```
This item is SEEDED. Ground-truth defects:
- id: rh-07-d1
  description: find_range() was softened to return None when the marker is absent (previously it raised ValueError). The new extract_section()/before_marker() guard for None, but the pre-existing strip_marker() still does `start, end = find_range(text, marker)`, which raises TypeError (cannot unpack None) when the marker is absent.
  acceptable_match: any finding that find_range() now returns None on absence while strip_marker() still unpacks its result, so strip_marker raises TypeError when the marker is absent.
  reject_if: a finding that only notes find_range() changed, or only that strip_marker() might fail, without connecting the new None return to strip_marker()'s unguarded tuple unpack.
```
**Judge:** verdict=REJECT (flagged)  found=['rh-07-d1']  false_findings=0  item_pass=True

## baseline — rh-11 (seeded=False)

**Normalized findings block:**
```
## FINDINGS
VERDICT: APPROVE
No findings.
```
**Ground truth:**
```
This item is CLEAN. There are NO ground-truth defects.
clean_rationale: Every timestamp entering or bounding the store is converted to milliseconds via to_ms: record(), count_since(), prune() and in_window() all apply to_ms to their seconds inputs, and _span_ms is compared against millisecond timestamps. Units are consistent at every site; no site mixes seconds and milliseconds.
tempting_non_defects (a finding matching one of these is a false finding):
- record() converts at_seconds with to_ms before storing, so stored timestamps and the _span_ms window are both in milliseconds (unlike a bug where one site forgets the conversion).
- count_since() and prune() compute the identical cutoff `to_ms(now_seconds) - _span_ms`, so they agree exactly on the window boundary.
- the field rename _window_ms -> _span_ms is purely mechanical and every reference was updated.
```
**Judge:** verdict=APPROVE  found=[]  false_findings=0  item_pass=True

## treatment — rh-11 (seeded=False)

**Normalized findings block:**
```
## FINDINGS
VERDICT: APPROVE
1. rate_window.py:49-63 — SMELL: `span_ms()` and `window_ms()` are exact-duplicate implementations (both `return self._span_ms`); likely an intentional compatibility alias per the stated contract, but could be simplified to have one delegate to the other.
2. rate_window.py:25-47 — SMELL: the cutoff calculation `to_ms(now_seconds) - self._span_ms` is duplicated identically in `count_since`, `prune`, and `in_window`; no behavioral defect, but could be factored into a private helper.
```
**Ground truth:**
```
This item is CLEAN. There are NO ground-truth defects.
clean_rationale: Every timestamp entering or bounding the store is converted to milliseconds via to_ms: record(), count_since(), prune() and in_window() all apply to_ms to their seconds inputs, and _span_ms is compared against millisecond timestamps. Units are consistent at every site; no site mixes seconds and milliseconds.
tempting_non_defects (a finding matching one of these is a false finding):
- record() converts at_seconds with to_ms before storing, so stored timestamps and the _span_ms window are both in milliseconds (unlike a bug where one site forgets the conversion).
- count_since() and prune() compute the identical cutoff `to_ms(now_seconds) - _span_ms`, so they agree exactly on the window boundary.
- the field rename _window_ms -> _span_ms is purely mechanical and every reference was updated.
```
**Judge:** verdict=APPROVE  found=[]  false_findings=0  item_pass=True

## baseline — rh-12 (seeded=False)

**Normalized findings block:**
```
## FINDINGS
VERDICT: APPROVE
No findings.
```
**Ground truth:**
```
This item is CLEAN. There are NO ground-truth defects.
clean_rationale: invalidate() and invalidate_table() are consistent with fetch()'s key shape: invalidate() pops `self._key(table, where)` (the same tuple fetch stores under), and invalidate_table() matches on `key[0]`. Invalidation actually removes the intended entries, so no stale value survives.
tempting_non_defects (a finding matching one of these is a false finding):
- invalidate() builds its key via the same _key(table, where) helper fetch() uses, so the key shapes match (unlike a stale hard-coded key that would never match).
- invalidate_table() iterates a snapshot list comprehension before deleting, so it does not mutate the dict while iterating it.
- the param rename filters -> where is mechanical and applied consistently across _key/fetch/invalidate/cached.
```
**Judge:** verdict=APPROVE  found=[]  false_findings=0  item_pass=True

## treatment — rh-12 (seeded=False)

**Normalized findings block:**
```
## FINDINGS
VERDICT: APPROVE
1. query_cache.py — SMELL: the diff adds four new public methods (`invalidate`, `invalidate_table`, `is_empty`, `has_table`) with no test file included in the diff to confirm coverage; not a demonstrated defect, just an untested-surface risk.
```
**Ground truth:**
```
This item is CLEAN. There are NO ground-truth defects.
clean_rationale: invalidate() and invalidate_table() are consistent with fetch()'s key shape: invalidate() pops `self._key(table, where)` (the same tuple fetch stores under), and invalidate_table() matches on `key[0]`. Invalidation actually removes the intended entries, so no stale value survives.
tempting_non_defects (a finding matching one of these is a false finding):
- invalidate() builds its key via the same _key(table, where) helper fetch() uses, so the key shapes match (unlike a stale hard-coded key that would never match).
- invalidate_table() iterates a snapshot list comprehension before deleting, so it does not mutate the dict while iterating it.
- the param rename filters -> where is mechanical and applied consistently across _key/fetch/invalidate/cached.
```
**Judge:** verdict=APPROVE  found=[]  false_findings=0  item_pass=True

## baseline — rh-13 (seeded=False)

**Normalized findings block:**
```
## FINDINGS
VERDICT: APPROVE
No findings.
```
**Ground truth:**
```
This item is CLEAN. There are NO ground-truth defects.
clean_rationale: find() gained an offset parameter and both call sites pass offset and limit by keyword: first() calls find(pred, offset=0, limit=n) and page() calls find(pred, offset=(page_num-1)*size, limit=size). No call site relies on positional binding, so no argument transposes, and page() uses the correct 1-indexed offset.
tempting_non_defects (a finding matching one of these is a false finding):
- first() and page() both pass offset/limit as keywords, so inserting offset into find()'s signature transposes nothing (unlike a positional call that would bind to offset).
- page()'s offset is (page_num - 1) * size (correct 1-indexed), not page_num * size, so page 1 starts at index 0.
- the param rename predicate -> pred is mechanical and consistent across matching/count/find/batches/page/first.
```
**Judge:** verdict=APPROVE  found=[]  false_findings=0  item_pass=True

## treatment — rh-13 (seeded=False)

**Normalized findings block:**
```
## FINDINGS
VERDICT: REJECT
1. search.py:39-41 — WRONG: `page()` doesn't validate `page_num >= 1` (or `size > 0`); for negative `page_num` (e.g. `page(pred, -1, 3)` over 10 matches), Python's negative-slice wraparound makes `find()` silently return a plausible non-empty slice (`[14,15,16]`) instead of an empty result or error.
2. search.py:23-25 — SMELL: `find()`'s new signature inserts `offset` before the pre-existing `limit` parameter, so any positional caller relying on the old `find(pred, limit)` shape now silently gets a different (offset, limit) meaning with no error; unconfirmed whether such callers exist outside this diff.
3. search.py:19-54 — SMELL: every helper recomputes `matching(pred)` from scratch rather than sharing/caching results, which is correct but inefficient for repeated pagination calls.
```
**Ground truth:**
```
This item is CLEAN. There are NO ground-truth defects.
clean_rationale: find() gained an offset parameter and both call sites pass offset and limit by keyword: first() calls find(pred, offset=0, limit=n) and page() calls find(pred, offset=(page_num-1)*size, limit=size). No call site relies on positional binding, so no argument transposes, and page() uses the correct 1-indexed offset.
tempting_non_defects (a finding matching one of these is a false finding):
- first() and page() both pass offset/limit as keywords, so inserting offset into find()'s signature transposes nothing (unlike a positional call that would bind to offset).
- page()'s offset is (page_num - 1) * size (correct 1-indexed), not page_num * size, so page 1 starts at index 0.
- the param rename predicate -> pred is mechanical and consistent across matching/count/find/batches/page/first.
```
**Judge:** verdict=REJECT (flagged)  found=[]  false_findings=1  item_pass=False
