# Conclusion-match grading — task DES-06 (design/architecture)

An engineer wrote the design analysis below in response to the task brief. The
question was later SETTLED empirically by the project's subsequent history.
Grade the analysis against the settled outcome. You do not know who wrote it.
Judge conclusions by SHAPE and substance, not by labels or wording.

## Settled outcome (ground truth, from later repository history)

- The vindicated answer was **GO**: Step 7 statement-node collection was
  parallelized exactly as the reference designed, landing on main (fd81e49
  extract + serial-reference parity oracle; ec84e21 ordered par_iter collect
  -> serial create; 3cb0182 non-vacuity guards).
- Load-bearing correctness point: the proof harness must compare **cache
  BYTES, not semantic graph equality**, because CpgNode::PartialEq ignores
  statement byte-spans — a reorder is invisible to semantic equality but
  changes serialized edge-endpoint integers. NodeIndex creation order must be
  preserved via serial apply in materialized file order.

## Grading fields

- verdict_matches_vindicated: is the bottom line GO on parallelizing Step 7?
- ordered_collect_serial_apply: does the design use parallel per-file
  collection with a serial, deterministically-ordered apply that preserves
  node-creation order?
- cache_byte_parity_point: does the analysis identify that parity must be
  proven at the CACHE-BYTE level (or equivalent: that semantic/PartialEq
  equality is insufficient because it ignores spans / NodeIndex order)?
- would_have_prevented_wasted_work: following the analysis as written, would
  the team have shipped the safe version (no reorder bug reaching cache)?
- probe_answer: 2-4 sentences on what the analysis got right and wrong vs the
  settled outcome.

## The task brief the engineer received

You are a Rust performance + static-analysis architect doing an INDEPENDENT design + architecture pass for
`prism`. session-cwd = the prism repo (branch `step5b-assemble-profile`, off main — S1.5 + the Step-5b memo are
merged). READ-ONLY: read/grep/`git`. Do NOT edit/build/test. Produce a design, not code.

## The opportunity (measured)
After S1.5 (call-args index) and the Step-5b memo, a per-step profile of `assemble_graph` shows the residual
serial cost is concentrated in **ONE step — Step 7 (statement nodes for CFG, `collect_function_statements`,
`src/cpg/build.rs:706`)**: hugo **5.71s = 80%** of the 7.18s assemble, tokio **2.76s = 73%** of 3.80s; every
other step is now small. A throwaway `par_iter`-over-files spike (collect statements in parallel → serial
node-create) measured **hugo 14.7→10.7s (−4.0s), tokio 6.4→4.2s (−2.2s)**, user/wall 1.53→2.22 → clear GO.

## The owner's directive: BE MINDFUL AND GUARD AGAINST RISK
This is a node-CREATING step, so unlike the edge-only Step 5b, the **load-bearing risk is node-insertion-order
parity**: petgraph `NodeIndex` is assigned in insertion order, and `cpg_cache.rs` serializes nodes/edges in
that order — so a single reordered node ⇒ different `NodeIndex` ⇒ different cache bytes ⇒ wrong incremental
builds / Tier-A flips, AND every downstream index keyed by `NodeIndex` (`stmt_index`, `location_index`, Step 8
CFG edges) shifts. **The design's central job is to PROVE the parallel build produces a byte-identical graph.**

## Deliver

### A. ANALYSIS — confirm the target + the parallel/serial split
Read `collect_function_statements` (`:706`) + its callees (`parsed.statement_spans_in_function` `src/ast.rs:3112`,
`Self::classify_stmt_kind` `:750`). Confirm: the per-file work (tree walk + `statement_spans_in_function` +
`classify_stmt_kind`) is READ-ONLY and per-file independent; only `graph.add_node` + `stmt_index.insert` +
`location_index.entry().push()` mutate shared state. Confirm the profile attribution (Step 7 dominant). Is the
expensive part the walk/classify (parallelizable) or `add_node` (serial, cheap)?

### B. DESIGN — parallel collect → serial node-create
`par_iter` over `files` (a `BTreeMap` — order-preserving) → per file, walk + dedup + classify → a `Vec` of
statement records (line, kind, start_byte, end_byte) in walk order; then a SERIAL pass creates the nodes +
`stmt_index` + `location_index` in `files`-order × walk-order. Specify the map output type, the dedup handling,
and the serial apply.

### C. ARCHITECTURE / RISK — the byte-identical proof (the core, per the owner)
- **Node order.** Does `files`-BTreeMap-order × per-file-walk-order reproduce the EXACT current serial node
  order? The current dedup is `if stmt_index.contains_key(&(file,line)) { continue }` — a GLOBAL incremental
  check. Is a per-file dedup equivalent (the key includes `file`, so per-file ⊆ global — but verify no
  cross-file (file,line) interaction, and that "first occurrence in walk order wins" is preserved exactly)?
- **`location_index` interaction.** Step 7 does `location_index.entry((file,line)).or_default().push(idx)` into
  an index that ALREADY holds nodes from earlier steps (var nodes, etc.). The APPEND ORDER of the statement
  nodes matters. What consumes `location_index` (grep), and is its post-Step-7 contents/order preserved
  byte-for-byte by the parallel-then-serial approach?
- **`stmt_index` → Step 8.** Step 8 (`build_cfg_edges` + `stmt_index.get`) depends on `stmt_index` being
  identical. Confirm.
- **The proof harness.** Specify a **serial-reference node-order oracle** (the S1.5 frozen-oracle pattern):
  capture the pre-refactor sequence of created `Statement` nodes (+ `stmt_index`/`location_index` state) and
  assert the parallel build reproduces it exactly; PLUS extend `tests/infra/parallel_equality_test.rs`
  (thread-count determinism + cache-blob byte parity). Read `cpg_cache.rs` to confirm node-order is
  byte-significant and name the exact serialized fields.
- **Determinism + Send/Sync.** rayon `collect` order-preserving; `ParsedFile` `Send+Sync` (existing `par_iter`
  proves it); `statement_spans_in_function`/`classify_stmt_kind` read-only (any interior mutability /
  `OnceLock` / caching that could race or non-determine?). The map captures no `&mut`.
- **FAILURE MODES — enumerate.** List every way the parallel output could diverge from serial (dedup order,
  location_index append order, walk order, classify non-determinism, float/hash, …) and the guard for each.

### D. VERDICT
GO / NO-GO + the risk-mitigation plan + EXACTLY what must be proven byte-identical before this can ship, and
whether the ~4s reward justifies the parity-test cost (the owner's instinct: yes, but pressure-test it).

## Read for ground truth (cite file:line)
`src/cpg/build.rs` (`collect_function_statements` :706, Step 7 :565, Step 8 :581, `assemble_graph` :290),
`src/ast.rs` (`statement_spans_in_function` :3112), `src/cpg/build.rs` (`classify_stmt_kind` :750), `cpg_cache.rs`
(node/edge serialization), `tests/infra/parallel_equality_test.rs`, `src/cpg/types.rs` (`CpgNode::Statement`,
`StmtKind`). rayon is a dep; C1/C2 (the S1 perf parallel-extract→serial-assemble pattern) is the precedent.

## Output (plain text, no fence)
- **ANALYSIS:** target confirmation + parallel/serial split.
- **DESIGN:** parallel-collect → serial-create (types, dedup, apply order).
- **ARCHITECTURE / RISK:** the byte-identical proof — node order, location_index, stmt_index, the oracle,
  determinism, Send/Sync, the enumerated failure modes + guards.
- **VERDICT:** GO/NO-GO + risk-mitigation + what must be proven. Be decisive.

ADDITIONAL CONTEXT (may be empty): Branch step5b-assemble-profile (off main: S1.5 call-args index + the Step-5b per-callee param memo are merged).
Per-step assemble_graph profile (env-gated Instant timers, reverted), cold nav --no-cache call-stats:
  HUGO assemble 7.18s: Step7 stmtNodes 5.71s (80%), Step8 cfgEdges 0.59s, Step5b interpDFG(memo) 0.41s, Steps2-3 varNodes 0.31s, rest <0.15s. Step9 ~0 (no type_db).
  TOKIO assemble 3.80s: Step7 2.76s (73%), Step5/5b ~0.4s each, Step8 0.17s, rest small.
Throwaway par_iter-over-files spike (parallel collect statements -> serial node-create, per-file line dedup):
  hugo 14.7->10.7s (-4.0s, ratio 1.53->2.22), tokio 6.4->4.2s (-2.2s). The spike happened to preserve node order
  (files BTreeMap order x walk order) and produced a working build, but it had NO parity proof — that is the
  production design's job. cpg_cache.rs serializes node/edge insertion order (cache-byte significant).


## The analysis to grade

All ground truth is read. Writing up the design pass now.

---

**ANALYSIS — target confirmed; the split is clean**

Step 7 (`src/cpg/build.rs:565-579`) iterates `files` (a `BTreeMap<String, ParsedFile>`, build.rs:293) and calls `collect_function_statements` (build.rs:706), a pre-order recursion over the whole parse tree. At each function-typed node it calls `parsed.statement_spans_in_function` (src/ast.rs:3112 — linear walk of the function body, then sort+dedup by line), and for each surviving statement calls `classify_stmt_kind` (build.rs:750).

The cost structure explains the 80%/73% attribution. `classify_stmt_kind` is not O(1): for every `expression_statement` or call-kind statement it invokes `call_names_on_lines(&[line])` (build.rs:781 → ast.rs:3799), which runs a fresh `QueryCursor` over the **entire file tree** per statement (ast.rs:3809-3810) — an O(statements × tree-size) quadratic term per file; goto/label statements additionally do full-root re-walks (`extract_goto_target`/`extract_label_name`, build.rs:793-839, C/C++ only). So the expensive part is the walk+classify, which is **read-only over `&ParsedFile`**; the shared-state mutations — `graph.add_node` (build.rs:724), `stmt_index.insert` (:731), `location_index.entry().push()` (:732) — are O(1) map/vec operations, trivially cheap. The spike's −4.0s/−2.2s with a serial node-create pass confirms empirically that the serial residue is small.

Per-file independence holds: the parallel work reads only `parsed` (tree, source, language tables, static `QUERY_CACHE`) and the file's own path. The dedup is against `stmt_index` (statements only), **not** `location_index` — so the map needs no access to any earlier-step state. One important detail: `collect_function_statements` recurses into children *even after* matching a function node (build.rs:735-746), so nested functions are visited and can re-yield lines already claimed by the enclosing function — the global `(file, line)` dedup is what arbitrates, and it must be preserved exactly.

---

**DESIGN — parallel collect → serial create**

*Record type* (mirrors `CpgNode::Statement` field-for-field, src/cpg/types.rs:25-31):

    struct StmtRecord { line: usize, kind: StmtKind, start_byte: usize, end_byte: usize }

*Parallel map.* Materialize the file list first so the parallel iterator is indexed (rayon only guarantees order-preserving `collect` for `IndexedParallelIterator`; `&BTreeMap::par_iter` is not indexed):

    let file_list: Vec<(&String, &ParsedFile)> = files.iter().collect();   // BTreeMap = sorted order
    let per_file: Vec<Vec<StmtRecord>> =
        file_list.par_iter().map(|(_, parsed)| collect_file_statement_records(parsed)).collect();

`collect_file_statement_records` is the **same recursion body** as today's `collect_function_statements`, with the three shared-state mutations replaced by a local `seen: BTreeSet<usize>` + `out: Vec<StmtRecord>`: at each func-type node, `statement_spans_in_function`; per stmt, `if !seen.insert(stmt.line) { continue; }` **before** classify (preserving today's skip-before-classify shape, build.rs:720-722), then classify and push. Classification runs in the parallel map — that is where the win is.

*Dedup.* Per-file `seen` on `line` alone is exactly equivalent to the global `stmt_index.contains_key(&(file, line))` check: every key in `stmt_index` carries the file name, each path occurs exactly once in the `files` iteration, so when file F is processed the global map can only contain (F, line) entries added while processing F itself. Cross-file interaction is impossible by key construction. First-occurrence-in-walk-order wins is preserved because `seen` is consulted incrementally in the identical walk order (including the nested-function re-visits).

*Serial apply* (files-order × walk-order, identical fold to today's code):

    for ((path, _), records) in file_list.iter().zip(per_file) {
        for r in records {
            let key = (path.to_string(), r.line);
            if stmt_index.contains_key(&key) { continue; }   // retained: provably never fires; keeps the
            let idx = graph.add_node(CpgNode::Statement {    // fold bit-identical to the old loop
                file: key.0.clone(), line: r.line, kind: r.kind,
                start_byte: r.start_byte, end_byte: r.end_byte });
            stmt_index.insert(key.clone(), idx);
            location_index.entry(key).or_default().push(idx);
        }
    }

Retaining the global `contains_key` costs one lookup per record and makes the apply *literally* the current algorithm run over the current candidate stream — any hypothetical per-file-dedup bug degrades to the serial behavior (skip) rather than a divergent graph.

*Equivalence argument in one paragraph:* current Step 7 is a fold over the candidate stream S = concat over files-in-BTreeMap-order of each file's walk-order candidates. The design computes each file's segment with the same pure code, concatenates in the same order (indexed rayon collect), and runs the identical fold. Identical stream + identical fold ⇒ identical `add_node` sequence ⇒ identical `NodeIndex` assignment. The only behavioral delta is thread scheduling of pure computation.

*Compatible follow-up (optional, composes):* batch `call_names_on_lines` once per file — collect all candidate lines in the map, run one query pass, classify from the returned `BTreeMap<line, Vec<name>>`. Per-line results are identical whether queried singly or batched (the cursor scans the whole tree either way and filters captures by line-set membership, ast.rs:3812-3825; classify uses only `names.first()`, build.rs:783). This kills the quadratic term outright and would shrink even the single-thread cost; it is output-equivalent and covered by the same oracle. Worth doing inside the parallel map, but it is severable if the review wants minimal deltas.

---

**ARCHITECTURE / RISK — the byte-identical proof**

*Node order.* Yes — files-BTreeMap-order × per-file-walk-order is exactly the current serial order, by the fold argument above. `cpg_cache.rs` makes this byte-significant: `SerializedCpg.nodes: Vec<CpgNode>` is "all graph nodes in insertion order" (cpg_cache.rs:98-99), reconstructed by re-adding in order to preserve `NodeIndex` (cpg_cache.rs:401-404); edges are serialized as raw `(u32, u32, CpgEdge)` index triples (cpg_cache.rs:100-101), so a single node reorder corrupts every subsequent edge record. Serialized `Statement` fields: `file`, `line`, `kind: StmtKind` (including `Call{callee}`, `Goto{target}`, `Label{name}` payloads, types.rs:117-136), `start_byte`, `end_byte` — all must match, and note the trap: **`CpgNode::PartialEq` ignores the byte fields** (types.rs:46-110), so any parity assertion must compare Debug dumps or full field tuples, never `==`. The existing test's `format!("{:?}", …)` dump (parallel_equality_test.rs:34) does this correctly.

*`location_index`.* Consumers: `cpg/query.rs:52,683`, `cpg/trace.rs:261,363,400`, `cpg/cfg_queries.rs:67,176` — several take `.first()`-style picks, so Vec order is semantically load-bearing. Two facts make this a non-issue beyond node-order parity: (1) `assemble_graph` applies a **total-order sort** to every bucket after Step 9 (build.rs:667-686; key ends in `i.index()`, which is unique), and nothing reads `location_index` between Step 7 and that sort (Step 8 reads only `stmt_index`, Step 9 only `func_index`/graph edges); (2) the cache does not serialize `location_index` at all — `reconstruct_cpg` rebuilds it from node iteration order and applies the identical sort (cpg_cache.rs:466-471, 480-499). So post-sort `location_index` is a pure function of node indices; node-order parity subsumes it. The design preserves the pre-sort append order anyway (same appends, same order), as defense against a future mid-assemble reader.

*`stmt_index` → Step 8.* `stmt_index` is Step-7-local (not a `CodePropertyGraph` field — `from_parts` carries graph, func/name/var/location indexes, CG, DFG; cpg_cache.rs:501-509). Step 8 (build.rs:581-591) reads it by key; identical (file,line)→NodeIndex content ⇒ identical `ControlFlow` edges in identical insertion order (the files/cfg_edges iteration is untouched and serial). Also confirmed: Step 7 adds no edges, and all edge insertions before Step 9 are order-unchanged, so Step 9's order-sensitive `graph.edges(caller_idx)` iteration (build.rs:630-636) is unaffected.

*The proof harness.* Three layers:

1. **Frozen serial-reference oracle (the S1.5 pattern** — precedent: `collect_call_args_at_reference`, ast.rs:73-74). Freeze today's `collect_function_statements` verbatim as `collect_function_statements_reference`; factor Step 7 into a callable seam (`step7_statement_nodes(files, &mut graph, &mut stmt_index, &mut location_index)` with a `_reference` twin). A test runs both variants from empty state over the existing corpora (`src/navigation`, `src/cpg` — parallel_equality_test.rs:17-23) **plus a C fixture with gotos/labels/duplicate-line and nested-function cases** (the goto/label classify paths are C-only), asserting: node Debug-dump sequence equality (all fields, incl. bytes), `stmt_index` equality, and post-sort `location_index` equality.
2. **Thread-count determinism + cache-byte parity — already exists and needs zero changes to exercise the new code.** `tests/infra/parallel_equality_test.rs:26-40` builds under a 1-thread pool vs. the default pool and compares full node+edge dumps; `:42-67` byte-compares `cpg-cache.bin` blobs. These prove scheduling-independence of the *new* code; the frozen oracle proves *old-vs-new* equivalence — both are needed, since a 1-thread run of new code is not the old code. Cheap addition: an oversubscribed pool (threads ≫ files) case.
3. **Real-corpus one-shot before merge:** build hugo and tokio cache blobs with the pre-refactor and post-refactor binaries and `cmp` the bytes; plus the CLAUDE.md Tier-A gate for `src/cpg/` changes (`uv run tier-a --matrix-only --allow-stale-sut` pre-commit, `--quick` pre-review) with any flips pasted into the PR.

*Determinism + Send/Sync.* `&ParsedFile` sharing across rayon threads is already proven in production: `call_graph.rs:472,557` par_iter over files, `data_flow.rs:226`, and `repo_loader.rs:83` (`ParsedFile: Send`). `ParsedFile` has two `OnceLock` fields — `framework` (ast.rs:113) and `call_args` (ast.rs:118) — neither is touched on the Step 7 path (audited: `statement_spans_in_function`, `classify_stmt_kind`, the goto/label walks, and `call_names_on_lines` read only `tree`/`source`/`language`); even if hit, `OnceLock` is single-winner with a deterministic init. `call_names_on_lines` uses the global `QUERY_CACHE: OnceLock<HashMap<…>>` (queries.rs:31) — keyed lookup only (no iteration order exposure), compiled from static pattern strings, race-safe. Capture iteration is tree-sitter document order — deterministic for a fixed tree. No floats anywhere in the path; all output containers are BTree or order-preserved Vecs. The map closure captures only `&` references — the compiler enforces no `&mut` capture (rayon requires `Sync` captures).

*Failure modes, enumerated, with guards:*

1. **Concatenation order ≠ files order** (unindexed rayon collect). Guard: materialize `Vec` from the BTreeMap, use indexed `par_iter().collect()`; oracle test catches any regression.
2. **Per-file dedup ≠ global dedup** (future key change, or first-wins violated). Guard: the key-construction proof as a code comment; per-file `seen` consulted in identical walk order; retained global `contains_key` in the apply makes any residual divergence degrade to exact serial behavior; oracle fixture includes duplicate-line nested-function cases.
3. **Walk-order divergence** from re-implementing the recursion. Guard: don't re-implement — extract the existing recursion body so old and new share code; the frozen `_reference` copy pins the original.
4. **Classify non-determinism** (query cache, capture order, OnceLock). Guard: audit above; determinism additionally witnessed by the 1-thread-vs-N dump test and cache-byte test.
5. **`location_index` append-order drift.** Guard: append in the serial apply only; normalized anyway by the total-order sort at build.rs:667 and rebuilt-from-nodes on cache load.
6. **Byte-field divergence invisible to `PartialEq`.** Guard: all assertions via Debug dump / bincode bytes, never `CpgNode ==`.
7. **Edge-order perturbation downstream** (Step 8/9 order sensitivity). Guard: Step 7 adds no edges; Step 8/9 code untouched; cache blob byte-compare covers the full edge list.
8. **Incremental-build path divergence.** `assemble_graph` is shared by full and incremental builds (build.rs:286-289), so the same code runs in both; the cache-blob test plus a PartialHit-path Tier-A run covers it.

---

**VERDICT — GO**

The reward is real and the risk is unusually well-contained for a node-creating step. Step 7 is the last big serial term (hugo 5.71s of 7.18s assemble; tokio 2.76s of 3.80s), the spike measured hugo 14.7→10.7s and tokio 6.4→4.2s end-to-end, and — decisively — the parity obligation collapses to a **single invariant**: the `add_node` call sequence. Everything the owner flagged (`stmt_index`, `location_index`, Step 8 CFG edges, cache bytes) is a derived function of node insertion order, because the cache serializes nodes-in-insertion-order and *rebuilds* the indexes on load, and `assemble_graph` totally-orders `location_index` buckets after Step 9. The equivalence argument is three short lemmas (pure per-file segments, order-preserving indexed collect, identical serial fold), each independently machine-checked.

Pressure-testing the owner's instinct on parity-test cost: the marginal cost is low because two-thirds of the harness already exists — `parallel_equality_test.rs` covers thread-count determinism and cache-byte parity with no changes, and the S1.5 frozen-reference pattern (`collect_call_args_at_reference`) is established practice in this codebase. The new cost is one frozen function, one oracle test with a C goto/label fixture, and a one-shot hugo/tokio `cmp` + Tier-A matrix before merge. That is roughly a day of work for a ~28% cold-build wall-clock reduction on hugo that also compounds into every future cold nav/CPG build. Yes — justified.

Must be proven byte-identical before ship, exactly: (1) the full `CpgNode` sequence in insertion order, all fields including `start_byte`/`end_byte` and `StmtKind` payloads, old-vs-new via the frozen oracle; (2) the `cpg-cache.bin` blob, serial-pool vs. parallel and old-binary vs. new-binary on at least one real corpus (hugo or tokio); (3) `stmt_index` content and post-sort `location_index` content on the oracle corpora; (4) a clean Tier-A matrix (no unexplained flips). Ship gate: all four green; any single byte of divergence is a stop-ship, not a re-baseline.

One scope note: the per-file batching of `call_names_on_lines` (kills the quadratic classify term) is output-equivalent and covered by the same oracle — recommend it as a fast-follow inside the parallel map, kept as a separate commit so the parity bisection stays clean.
