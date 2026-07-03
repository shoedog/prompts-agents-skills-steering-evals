# ledger.parse_ledger

`parse_ledger(lines)` parses a CSV ledger and returns
`(entries, total_credit_cents)`.

Format & contract:
- `lines[0]` is a header row and is skipped.
- Each data row is `date,amount,type`.
- `amount` is a decimal dollar string like "12.10"; store it as an integer
  number of CENTS, correctly rounded (12.10 -> 1210).
- `type` is the literal upper-case string "CREDIT" or "DEBIT".
- `total_credit_cents` is the sum of the cent amounts of all CREDIT rows.
