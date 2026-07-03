# tokens.is_expired

`is_expired(token)` reports whether an access token has passed its expiry.

Contract:
- `token.expires_at` is a NAIVE `datetime` expressed in UTC (all timestamps
  are stored as naive UTC).
- The service runs on hosts in various local timezones; expiry must be
  evaluated in UTC regardless of the host's local timezone.
- Return True iff the current UTC time is at or past `token.expires_at`.
