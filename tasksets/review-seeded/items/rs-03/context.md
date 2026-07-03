# ratelimit.parse_rate_limit

`parse_rate_limit(headers)` reads GitHub-style rate-limit response headers.

Header contract (all present, all decimal strings):
- `X-RateLimit-Limit`    - the total quota for the window.
- `X-RateLimit-Remaining`- calls still available in the current window.
- `X-RateLimit-Reset`    - unix epoch seconds when the window resets.

Return a RateLimit(remaining=<remaining calls>, reset_at=<reset epoch>).
`remaining` must be the REMAINING calls, not the total quota.
