# replay_spool: external-sort run files (writer, first cut)

Spooling layer for a canonical-data backfill: records are buffered, spilled
to sorted "run" files under a scratch directory, then merged and finally
sealed; an emitter reads the sealed run back one instrument group at a time.

Contract:
- Run files carry a magic header and length-framed records, with an
  integrity digest over the framed stream and a count/digest footer.
- `docs/spool-format.md` is the format's reference documentation and must
  stay accurate: operators size scratch volumes and debug spools from it.
- The diff adds the first cut of the record writer plus the format doc.
