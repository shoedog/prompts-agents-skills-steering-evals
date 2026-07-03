# billing_dates.next_billing_date

`next_billing_date(d)` returns the billing date one month after `d`,
preserving the day-of-month where possible.

Contract:
- Return a `date` in the FOLLOWING month with the same day-of-month as `d`.
- If the following month has fewer days than `d.day` (e.g. Jan 31 -> Feb),
  clamp to the LAST valid day of that following month (Jan 31 -> Feb 28).
- Roll the year over correctly for December.
- Must never raise for any valid input date.
