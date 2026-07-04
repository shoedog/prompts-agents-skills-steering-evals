# importer.Importer

Ingests unique, normalized name records.

Contract:
- Names are normalized (trimmed and lower-cased) and each stored record is
  a non-empty, unique normalized key.
- `add(raw)` validates and stores one record, returning False if it is a
  duplicate; a name that is empty (after normalization) or over 64 chars is
  rejected.
- `import_all(names)` imports many and returns how many were stored.
- `retry_import(names)` re-runs an import that may have partially
  completed, without creating duplicate records.
- `has`, `duplicates`, `records`, `count`, `is_empty`, `reset` are helpers.
