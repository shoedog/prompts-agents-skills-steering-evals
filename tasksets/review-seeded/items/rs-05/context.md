# io_utils.read_records

`read_records(path)` reads a UTF-8 text file and returns a list of parsed
records, one per non-empty line.

Contract:
- Parse every non-empty line with `parse_line`.
- `parse_line` may raise `ValueError` on a malformed line; that error must
  propagate to the caller.
- The file handle must ALWAYS be released before the function returns or
  raises - no leaked descriptors on any code path.
