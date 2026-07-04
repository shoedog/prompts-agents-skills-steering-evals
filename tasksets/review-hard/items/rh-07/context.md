# parsing (marker helpers)

Functions for locating and slicing around a text marker.

Contract:
- `find_range(text, needle)` returns the `(start, end)` span of `needle`
  in `text`, or None when `needle` is absent.
- `extract_section(text, needle)` returns the text after `needle` (or '');
  `before_marker(text, needle)` returns the text before it (or the whole
  text) when the needle is absent.
- `strip_marker(text, marker)` returns `text` with the first occurrence of
  `marker` removed.
- `marker_present`, `count_markers`, `all_ranges`, `is_blank` are helpers.
