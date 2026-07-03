# cart.add_item

`add_item(item, basket)` appends `item` to a shopping basket and returns it.

Contract:
- Append `item` to `basket` and return the basket.
- If the caller omits `basket`, the function starts a NEW empty basket for
  that call; two separate calls that both omit `basket` must not share items.
