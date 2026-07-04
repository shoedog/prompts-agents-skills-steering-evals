# transaction.Transaction

A re-entrant transaction guard: nested `begin`/`commit` calls share one
lock, and named savepoints can be recorded within a transaction.

Contract:
- `begin()` enters a transaction level (acquiring the lock on the
  outermost level); `commit()` leaves one level (releasing the lock when
  the outermost level closes).
- `rollback()` aborts the whole transaction, releasing the lock and
  discarding the transaction's savepoints.
- `savepoint(name)` records a savepoint; `savepoints()` lists those of the
  current transaction. `depth`, `active`, `run`, `locked` are helpers.
