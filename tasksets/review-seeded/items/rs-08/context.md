# finance.compound_balance

`compound_balance(principal, rate, years)` returns the balance after `years`
of annual compounding at fractional `rate`.

Contract:
- Formula: `principal * (1 + rate) ** years`.
- `rate` is a fraction (0.05 == 5%); `years` is a non-negative int.
- Example: principal=1000, rate=0.05, years=3 -> 1157.625.
