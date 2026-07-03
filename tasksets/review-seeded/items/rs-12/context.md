# settings.resolve_retention

`resolve_retention(requested)` resolves the log-retention period in days.

Contract:
- `requested` is an optional int.
- `requested is None` means "no preference": use DEFAULT_RETENTION_DAYS.
- `requested == 0` is a meaningful value meaning "retain nothing" and is
  returned unchanged as 0.
- Any other int is returned as-is.
