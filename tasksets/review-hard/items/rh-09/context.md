# bank.Bank

In-memory account balances with transfers.

Contract:
- `deposit(account, amount)` adds to a balance.
- `transfer(src, dst, amount)` moves `amount` from `src` to `dst`
  atomically: either both balances change or neither does.
- `safe_transfer(src, dst, amount)` performs a transfer and returns True
  on success or False on failure.
- `balance`, `accounts`, `history`, `net_worth`, `has_account`,
  `entry_count` are read-only accessors.
