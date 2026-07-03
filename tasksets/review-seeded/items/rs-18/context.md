# sessions.is_expired

`is_expired(expires_at)` reports whether a session has expired.

Contract:
- `expires_at` is a timezone-AWARE `datetime` in UTC.
- Compare against the current time in UTC.
- The exact expiry instant counts as expired (return True when now == expiry).
