# pagination.total_pages

`total_pages(total_items, page_size)` returns how many pages are needed to
display `total_items` records at `page_size` records per page.

Contract:
- `total_items >= 0` and `page_size >= 1`.
- The result is the ceiling of `total_items / page_size`: the number of
  pages required to show every item.
- `total_items == 0` returns 0.
- When `total_items` is an exact multiple of `page_size`, the result is
  exactly `total_items / page_size` (no trailing empty page).
