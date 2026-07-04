# ttl_cache.TTLCache

An expiring key/value store. The internal clock (`now_ms`) is integer
milliseconds; the public API takes TTLs in seconds.

Contract:
- `set(key, value, ttl_seconds)` stores `value`, expiring `ttl_seconds`
  after now.
- `get(key)` returns the live value, or None if the key is missing or has
  expired (expired entries are dropped on access).
- `touch(key, ttl_seconds)` resets an existing key's remaining lifetime to
  `ttl_seconds` from now, returning False if the key is absent.
- `ttl_left`, `has`, `get_or`, `live_items`, `keys`, `size` are read-only
  accessors over the same store.
