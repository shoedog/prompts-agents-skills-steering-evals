# tagging.append_tag

`append_tag(item, tags=None)` appends `item` to a tag list and returns it.

Contract:
- If the caller passes an existing list as `tags`, append to it and return it.
- If `tags` is omitted, start a fresh empty list for THIS call only; two
  separate calls that both omit `tags` must not share state.
