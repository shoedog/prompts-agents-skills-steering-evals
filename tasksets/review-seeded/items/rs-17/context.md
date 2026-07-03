# txn.run_in_transaction

`run_in_transaction(conn, fn)` runs `fn(conn)` inside a transaction.

Contract:
- On success, return `fn`'s result.
- If `fn` raises, roll the transaction back and RE-RAISE the original
  exception (callers must still see the error).
- Always close the connection afterwards, on success and failure.
- `conn.close()` is idempotent.
