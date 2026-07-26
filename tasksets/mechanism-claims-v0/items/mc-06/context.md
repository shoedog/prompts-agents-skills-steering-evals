# target_spool: run-file writer for the target-only adjudicator

Spooling layer for the SMALL target-only population (~5.5k instruments,
~8.8M records) — a separate, deliberately simpler sibling of the
full-population canonical spool. Records spill to "run" files under a
scratch directory and are merged and sealed by machinery outside this diff.

Contract:
- Run files carry a magic header and length-framed records, with an
  integrity digest over the framed stream and a count/digest footer.
- `docs/target-spool-format.md` is the format's reference documentation
  and must stay accurate: operators size scratch volumes and debug spools
  from it.
- The diff adds the record writer plus the format doc.
