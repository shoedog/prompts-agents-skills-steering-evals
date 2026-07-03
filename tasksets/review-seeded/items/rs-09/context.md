# ProfileCache

In-memory read-through cache over a slow `load_profile` / `save_profile`
storage layer.

Contract:
- `get(uid)` returns the profile, loading and caching it on first access.
- `save(uid, profile)` persists the profile AND keeps the cache consistent,
  so a subsequent `get(uid)` reflects the just-saved data (no stale reads).
- `clear()` empties the cache.
