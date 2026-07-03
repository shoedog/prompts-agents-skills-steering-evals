# list_view.page_bounds

`page_bounds(page, page_size, total)` computes slice indices for a 1-indexed
page over a 0-indexed list of `total` items.

Contract:
- `page` is 1-indexed (page 1 is first); `page_size >= 1`.
- Return `(start, end)` such that `items[start:end]` is the page's slice.
- `end` is exclusive and clamped to `total`, so the final (possibly partial)
  page is handled and never reads past the end.
