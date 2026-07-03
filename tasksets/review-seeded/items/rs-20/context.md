# ConfigCache

Read-through / write-through in-memory cache over a config store.

Contract:
- `get(key)` returns the value, loading and caching it on first access.
- `set(key, value)` writes THROUGH to the store and updates the cache so a
  subsequent `get(key)` returns the new value (no stale read).
- `reload()` drops all cached entries so the next get reloads from the store.
