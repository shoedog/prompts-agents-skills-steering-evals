# validate.collect_warnings

`collect_warnings(record, warnings=...)` appends human-readable warnings for
a single `record` and returns the list.

Contract:
- Check the record and append a message for each problem found.
- When the caller does not pass a `warnings` list, the function returns a
  fresh list describing only THIS record.
- Called once per record while iterating a batch; separate calls that omit
  `warnings` must not share state.
