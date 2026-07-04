# Judge spot-check (human review)

## baseline — rh-01 (seeded=True)

**Normalized findings block:**
```
## FINDINGS
VERDICT: REJECT
1. ttl_cache.py:46 — `touch()` method fails to convert `ttl_seconds` from seconds to milliseconds, causing expiry times to be set ~1000x too soon
```
**Ground truth:**
```
This item is SEEDED. Ground-truth defects:
- id: rh-01-d1
  description: `set()` computes `expiry = now_ms() + ttl_seconds * 1000`, but the newly added `touch()` computes `expiry = now_ms() + ttl_seconds` with no `* 1000`. Since `now_ms()` is in milliseconds and `ttl_seconds` is seconds, a touched key's lifetime is 1000x too short.
  acceptable_match: any finding that touch() omits the `* 1000` that set() applies, i.e. it adds ttl_seconds (seconds) to a millisecond clock, making the two methods use inconsistent units.
  reject_if: a finding that only says 'touch looks wrong' or comments on now_ms generally, without naming the missing *1000 / the seconds-vs-milliseconds inconsistency between touch and set.
```
**Judge:** verdict=REJECT (flagged)  found=['rh-01-d1']  false_findings=0  item_pass=True

## treatment — rh-01 (seeded=True)

**Normalized findings block:**
```
## FINDINGS
VERDICT: REJECT
1. ttl_cache.py:45 — `touch` method fails to convert `ttl_seconds` to milliseconds when computing expiry; should be `entry[1] = now_ms() + ttl_seconds * 1000`, consistent with `set` on line 20.
2. ttl_cache.py:38 — `ttl_left` returns milliseconds instead of seconds, violating the contract principle that the public API uses seconds for TTLs and breaking compatibility with code expecting seconds.
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
1. memo.py:45 — `invalidate(a, b)` tries to pop a 2-tuple key `(a, b)` directly, but all cache keys are 3-tuples `(a, b, opts_tuple)`, so the method silently fails to remove anything, breaking the invalidation contract.
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
1. memo.py:32–34 — `invalidate(a, b)` pops the 2-tuple `(a, b)` but cache keys are now 3-tuples `(a, b, opts_tuple)`, so it will never find or delete anything
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
1. transaction.py:34 — `commit()` unconditionally releases the lock on every call, breaking the re-entrancy guarantee; should only release when `self._level == 0`
2. transaction.py:48-49 — `rollback()` uses `self._lock.locked()` to check if the lock is held, but `locked()` returns True if any thread holds the lock, not necessarily the current thread; should check `self._level > 0` instead to safely determine if this transaction holds the lock
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
**Judge:** verdict=REJECT (flagged)  found=['rh-03-d1']  false_findings=1  item_pass=False

## treatment — rh-03 (seeded=True)

**Normalized findings block:**
```
## FINDINGS
VERDICT: REJECT
1. transaction.py:31 — `commit()` releases the lock unconditionally; should only release when `_level == 0`, breaking the re-entrant contract and causing double-release errors in nested transactions.
2. transaction.py:40 — `rollback()` checks `if self._lock.locked():` to decide whether to release, but this checks if any thread holds the lock, not whether we hold it; should check `if self._level > 0:` (captured before `self._level = 0`) to determine if we're in an active transaction.
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
**Judge:** verdict=REJECT (flagged)  found=['rh-03-d1']  false_findings=1  item_pass=False

## baseline — rh-04 (seeded=True)

**Normalized findings block:**
```
## FINDINGS
VERDICT: REJECT
1. leaderboard.py:24 — `add_many()` extends the list with sorted values without merging them with existing sorted elements, breaking the global sort invariant and corrupting binary search results.
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
1. leaderboard.py:24 — `add_many()` does not maintain global sorted order; `extend(sorted(values))` appends sorted values to the end without interleaving with existing scores, violating the contract and breaking subsequent binary-search operations.
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
1. repo.py:50 — `recent()` calls `query()` with positional arguments that now map incorrectly after the signature change; `limit` is passed as `offset` instead of `limit`, causing it to skip rows instead of limiting results
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

## treatment — rh-05 (seeded=True)

**Normalized findings block:**
```
## FINDINGS
VERDICT: REJECT
1. repo.py:50 — `recent` passes `limit` as the `offset` argument to `query`, causing it to skip rows instead of capping the result count. Should call `self.query(table, lambda r: True, limit=limit)` or `self.query(table, lambda r: True, offset=0, limit=limit)`.
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
1. `defaults()` return statement — returns internal dict reference instead of a copy, breaking read-only encapsulation contract and enabling callers to modify internal state
2. `effective()` method — now mutates `self._defaults` because `self.defaults()` returns a reference that `update()` modifies, violating the contract "(defaults unchanged)"
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
1. settings.py:25 — `defaults()` returns a reference to `self._defaults` instead of a copy, allowing callers to mutate internal state.
2. settings.py:29 — `effective()` calls the broken `defaults()` and mutates the returned reference, corrupting the baseline defaults despite the docstring stating "defaults unchanged".
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
1. parsing.py:25 — `strip_marker()` calls `find_range()` without checking for `None` return, will crash with `TypeError` when marker is absent instead of raising `ValueError`.
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
1. parsing.py:25 — `strip_marker` unpacks the return value of `find_range` without checking for `None`, causing a `TypeError` when the marker is absent (new behavior of `find_range`).
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

## baseline — rh-12 (seeded=False)

**Normalized findings block:**
```
## FINDINGS
VERDICT: REJECT
1. invalidate_table:34 — Docstring says "any filters" but should say "any where" for consistency with the renamed parameter terminology used throughout the class.
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
**Judge:** verdict=REJECT (flagged)  found=[]  false_findings=1  item_pass=False

## treatment — rh-12 (seeded=False)

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
