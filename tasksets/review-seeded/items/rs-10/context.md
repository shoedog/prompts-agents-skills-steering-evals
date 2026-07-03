# text_utils.truncate_utf8

`truncate_utf8(text, max_bytes)` shortens `text` so its UTF-8 encoding is at
most `max_bytes` bytes.

Contract:
- If `text` already fits in `max_bytes` bytes, return it unchanged.
- Otherwise return the longest prefix of `text` whose UTF-8 encoding is
  `<= max_bytes` bytes.
- The result must always be valid text: never split a multi-byte character
  and never raise, for any input.
