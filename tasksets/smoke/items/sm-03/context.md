# eligibility.is_eligible

`is_eligible(age, has_consent)` gates access to a feature.

Contract:
- A user is eligible if they are an adult (`age >= 18`) OR a guardian has
  provided consent (`has_consent` is True).
- Otherwise they are not eligible.
