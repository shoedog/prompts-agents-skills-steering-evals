# Conclusion-match grading — task PLAN-01 (architecture GO/NO-GO)

An engineer wrote the design analysis below in response to the task brief. The
question was later SETTLED empirically. Grade the analysis against the settled
outcome. You do not know who wrote it.

## Settled outcome (ground truth, from later repository history)

- A later design spec reached the conclusion that blind parallelization of
  Step 5b was NOT the right fix; the true Step-5b cost was redundant
  all_functions() reconstruction (measured 10.9x on the hugo corpus), not raw
  CPU parallelism headroom.
- A parallel spike was then measured at a ~0.3 second ceiling and the slice
  was recorded SHELVED: "Slice 2 SHELVED — parallel spike measured ~0.3s
  ceiling".
- i.e. the vindicated answer: NO-GO on parallelizing Step 5b; the win was
  deleting redundant serial work, not adding parallelism.

## Grading fields

- verdict_matches_vindicated: does the analysis's bottom-line GO/NO-GO match
  the vindicated NO-GO on Step-5b parallelization as the primary fix? A GO
  that is conditional/gated still counts as NOT matching if it endorses the
  parallelization as the primary path.
- true_bottleneck_identified: does it identify the redundant
  all_functions()/duplicate-resolve serial work as a (or the) real cost?
- premise_challenged: does it explicitly question the directive's premise
  rather than assuming Step 5b parallelization is the right fix?
- buy_estimate_consistent_with_measured: is its quantitative expected-buy
  consistent with the measured ~0.3s ceiling (a 2-6s estimate is NOT)?
- would_have_prevented_wasted_work: taking the analysis's own recommended
  process (e.g. mandatory instrumentation gates) at face value, would
  following it have avoided implementing the doomed parallelization?
- probe_answer: 2-4 sentences on what the analysis got right and wrong vs the
  settled outcome.

## The task brief the engineer received

You are a Rust performance + static-analysis architect doing an INDEPENDENT analysis + design + architecture
pass for `prism`. session-cwd = the prism repo, on branch `s1.5-call-args-index` (S1.5 just landed:
`call_argument_texts_at` is now backed by a per-file `CallArgsIndex`, not a tree walk). READ-ONLY: read/grep/
`git log`/`git show`. Do NOT edit/build/test. Produce a design, not code.

## The problem
S1.5 removed the serial Step-5b `collect_call_args` quadratic walk — the ~98% dominator of the remaining cold
`assemble_graph` time (cold hugo 86.4→18.4s = 4.68×). But the cold-hugo user/wall ratio is now **1.42**, still
under the s1-followups gate-9 ≥1.5 target. The residual gap is serial work in the cold CPG build. The owner's
directive: **parallelize the rest of Step 5b** (the interprocedural data-flow edge assembly in
`src/cpg/build.rs`). Your job is to analyze whether that is the right target and design how to do it SOUNDLY.

## Deliver THREE things

### A. ANALYSIS — locate the residual serial cost (be skeptical; measure-by-reasoning)
- Read `src/cpg/build.rs` `assemble_graph` (~:245) end to end: enumerate its phases (Step 1..Step 5b and any
  pre/post), and for each say whether it is already parallel (S1 C1/C2 parallelized parse + Phase-1/2/DFG
  extraction) or serial. Read `src/cpg/context.rs` `build_with_scope_graph_inputs` (~:67) for the phases
  BEFORE `assemble_graph` (scope-graph build, `CallGraph::build_with_scope_graph_inputs`, `DataFlowGraph::build`).
- The KEY question: is the residual serial time actually in **Step 5b** (the `for (caller_id, sites) in
  &cg.calls` interprocedural-DFG loop, ~:428–460), or is it dominated by something else on the cold path
  (scope-graph build, call-graph build, DFG build, or the petgraph node/edge assembly in Steps 1–5a)? Reason
  from the code structure + complexity. If Step 5b is NOT the dominant residual serial cost, say so plainly and
  name what is — do not assume the directive's target is correct without evidence. (You cannot run a profiler;
  reason structurally and flag what should be profiled to confirm.)

### B. DESIGN — parallelize Step 5b soundly (if A confirms it's worth it)
- The proven prism pattern for parallelizing serial assembly is **parallel-compute → serial-deterministic-apply**
  (S1 C1/C2; and `CallGraph::rematerialize_rust_receiver_keys` in `src/call_graph.rs` — read it as the template:
  `par_iter` over an immutable read set → collect updates → deterministic sorted serial apply). Design Step 5b
  to fit this: which work is read-only and parallelizable (e.g. `cg.resolve_call_site(site)`, the `CallArgsIndex`
  lookup, callee param-name mapping, computing the `(caller_idx, callee_idx, CpgEdge)` tuples) vs which MUST
  stay serial and ordered (the `graph.add_edge` into the petgraph — NodeIndex assignment + edge insertion order).
- Specify the exact map output type, the deterministic apply order, and where the barrier is.

### C. ARCHITECTURE — the invariants that make it safe
- **Determinism + cache-byte parity (the hard constraint).** s1-followups item 2: "lifting the serial-assembly
  constraint is S2-adjacent NodeIndex-identity work… cache bytes serialize insertion order with no CACHE_VERSION
  bump." Check whether the S2 node-identity work (merged to main — find it via `git log`) changed this: are
  petgraph NodeIndex/edge-insertion order still cache-byte-significant? Does parallelizing the COMPUTE while
  keeping the APPLY in the exact current order preserve byte-identical cache output? What is the parity test
  (mirror S1's exact-order + cache-byte parity tests)?
- **Send/Sync + borrow.** Is `resolve_call_site` (`src/call_graph.rs` / `src/resolution.rs`) `&self` read-only
  and the indices it reads `Sync`? The `CallArgsIndex` is a lazy `OnceLock` on `ParsedFile` — is concurrent
  first-init under `par_iter` sound? Any interior mutability / `&mut` hazard in the parallel map?
- **Option-C safety.** Diff-review output must stay byte-identical (the `cli_nav_compat` invariant).

### D. VERDICT — GO / NO-GO + expected buy
- Given A, is parallelizing Step 5b worth it (does it plausibly move gate-9 1.42→≥1.5, and how much absolute
  cold-time)? Or is the residual serial cost elsewhere (→ redirect the effort)? State a decisive recommendation
  with the reasoning, and the measurements that should confirm it before implementation.

## Read for ground truth (cite file:line)
`src/cpg/build.rs` (`assemble_graph`, Step 5b ~:428), `src/cpg/context.rs` (`build_with_scope_graph_inputs`),
`src/call_graph.rs` (`rematerialize_rust_receiver_keys` = the parallel template; `resolve_call_site`),
`src/ast.rs` (the `CallArgsIndex` / `call_argument_texts_at`), `docs/prism-query-layer/s1-followups.md`
(items 2 + 9), `docs/superpowers/specs/2026-06-11-prism-s1-perf-level4-index-design.md` (the C1/C2 parallel
pattern + cache-byte parity), and the S2 node-identity work (`git log --oneline | grep -i s2/identity` or
search specs). rayon is already a dep.

## Output (plain text, no fence)
- **ANALYSIS:** the phase-by-phase serial/parallel map + where the residual serial cost actually is (decisive).
- **DESIGN:** the parallel-compute→serial-apply for Step 5b (types, apply order, barrier).
- **ARCHITECTURE / INVARIANTS:** determinism + cache-byte parity strategy + parity test; Send/Sync; Option-C.
- **VERDICT:** GO / NO-GO + expected gate-9 + absolute buy + what to profile to confirm. Be decisive.

ADDITIONAL CONTEXT (may be empty): The working tree (branch `s1.5-call-args-index`, PR #111) has S1.5 applied:
`ParsedFile::call_argument_texts_at` is now a `CallArgsIndex` (`BTreeMap<(start_byte,callee_name),Vec<CallArg>>`,
lazy `OnceLock`) lookup, not a tree walk — so the old serial dominator in Step 5b is gone.

Measured AFTER S1.5 (cold `nav --no-cache call-stats`, this branch vs baseline `e72a0c8`):
hugo 86.4→18.4s (4.68×), tokio 8.2→6.5s, prism 27.4→22.7s; cold-hugo user/wall 1.09→1.42.
gate-9 (s1-followups item 9) target is ≥1.5; the 1.42 residual gap is the directive's subject.

Analyze the CURRENT (post-S1.5) cold build. The S1 perf work (FunctionTable, Level-4 index, C1/C2 rayon
parse+extraction with serial assembly) is on main; `rematerialize_rust_receiver_keys` (the Phase-2/3 receiver
post-pass) is the most recent in-repo example of the parallel-compute→serial-deterministic-apply pattern —
read it as the template. S2 node-identity hardening is merged to main (find it in git log).


## The analysis to grade

All evidence is in. Composing the deliverable now.

---

# ANALYSIS — where the residual serial time actually is

## Cold-path phase map (`nav --no-cache call-stats` → `main.rs:491-492` → `NavigationIndex::build`, `src/navigation/mod.rs:34-41`)

`--no-cache` skips both cache load **and** save (`main.rs:491-492` calls `NavigationIndex::build`, never `save_cache`), so cache serialization is *not* in the measured 18.4s window.

| Phase | Where | Parallel? |
|---|---|---|
| Parse all files | `repo_loader.rs:83` (`into_par_iter`) | **Parallel** (S1 C1) |
| Scope inputs + hashes | `repo_loader.rs:144` | Serial, cheap |
| `DataFlowGraph::build` extraction | `data_flow.rs:225-226` (`par_iter` per file) | **Parallel** (C2) |
| DFG flatten/merge of defs/uses/edges | after `data_flow.rs:226` | Serial |
| CG imports extraction | `call_graph.rs:448-453` | Serial |
| CG Phase 1 / Phase 2 extraction | `call_graph.rs:471-517`, `:556-632` | **Parallel** (C2) |
| CG Phase 1/2 flattens | `call_graph.rs:519-548`, `:634-645` | Serial |
| CG Phase 3 (indirect, Levels 1–4) | `call_graph.rs:655-931` | Serial |
| Rust scope graph + receiver rematerialization | `call_graph.rs:995`, `:1096-1192` | Serial (≈no-op on hugo/Go; heavy on Rust corpora) |
| Go embedding + interface dispatch | `call_graph.rs:996-997`, `:1292-1321` | Serial (hugo-relevant) |
| `assemble_graph` Steps 1–9 | `build.rs:245-677` | **Serial end-to-end** (no rayon anywhere in `cpg/build.rs`) |
| `build_registry` + `collect_live_types` | `context.rs:83-84`, `:267-277` | Serial whole-repo scans |

## The arithmetic

user = 1.42 × 18.4 ≈ **26.1s**. With K ≈ 8–10 effective cores, solving `S + P = 26.1`, `S + P/K = 18.4` gives **S ≈ 17.3–17.5s of serial wall time** on cold hugo. That is the residual gap. The gate needs wall ≤ 26.1/1.5 ≈ 17.4s — i.e. a **net ≥1.0s** wall cut. The gate is knife-edge.

## What Step 5b still costs post-S1.5 (`build.rs:428-532`)

Four real per-site costs remain, plus one hidden whole-repo cost:

1. **The `CallArgsIndex` lazy first-init runs serially inside Step 5b.** The plural byte-keyed `call_argument_texts_at` has exactly one production caller — `build.rs:438` (grep-verified; `ast.rs:4393`, index at `ast.rs:76-78,118,178-201`). Nothing warms the `OnceLock` earlier, so on every cold build a full pre-order AST walk + index build of essentially **every caller file** executes inside this serial loop. This is a hidden "index the whole repo" pass, and it is genuinely parallelizable.
2. **`resolve_call_site` runs twice per site** — once in Step 5 (`build.rs:409`) and again in Step 5b (`build.rs:431`), on an unchanged `cg`.
3. **Per resolved site, a per-callee param recompute** via `all_functions()` reconstruct-and-scan (`build.rs:456-476`) — the FunctionTable makes this O(F·log N) per site (`ast.rs:279-316`), not quadratic, but it is repeated identically for every call to the same callee, and `FunctionInfo.param_names` already exists as the fallback (`build.rs:476`).
4. **The param-Def probe** scans `start_line..=end_line` allocating a fresh composite String key per line (`build.rs:514-525`). Param Defs are pinned to the signature line (`data_flow.rs:277-292`), so hits are cheap — but a *miss* (field-only params, common in Go) scans the whole function per site, every time.

## Is Step 5b the dominant residual? **No — say it plainly.**

Three independent lines of evidence:

- **The item-3 bound.** s1-followups item 3 (`docs/prism-query-layer/s1-followups.md:21-24`): `collect_call_args` was "~98% of remaining `assemble_graph` time" (tokio scale). Removing it removed 68s of hugo's 86.4s. If the 98:2 split roughly transfers, the *entire remaining* `assemble_graph` — Steps 1–4, 5, 5b-residual, 6–9 — is a low-single-digit-seconds item on hugo, out of ~17.5s serial. Even generously (hugo files are larger, the split degrades), Step 5+5b residual is plausibly **2–6s**, not 17s.
- **The cross-corpus smoking gun.** Post-S1.5: **prism 22.7s > hugo 18.4s**, though hugo is an order of magnitude more code and call sites. Step 5b cost is site-proportional; if it dominated, hugo would be far slower than prism, not faster. Prism/tokio's residue is the *Rust-only* serial passes — scope-graph populate + `rematerialize_rust_receiver_keys`, which re-runs `function_calls_with_qualifier_and_spans_on_lines` per caller, serially (`call_graph.rs:1146-1147`). The residual serial cost is **language-dependent and spread out**, not concentrated in Step 5b.
- **The tail is enumerable.** On hugo (Go), the rest of the ~17.5s structurally sits in: the serial Phase-1/2/DFG flatten-merges (hundreds of thousands of `CallSite`/`VarLocation` clones into BTreeMaps); Phase 3, including the Level-3 **per-caller whole-tree `find_function_by_name` walk** (`call_graph.rs:853` → recursive from root, `ast.rs:3854-3858`) and the Level-4 whole-repo text scan (`call_graph.rs:761-778`); the Go passes, which build a **second** `GoTypeProvider::from_parsed_files` + live-set scan (`call_graph.rs:1303-1305`) duplicating the one in `build_registry` (`context.rs:272-276`) plus `collect_live_types` (`context.rs:84`); `assemble_graph` Steps 2–4 (millions of composite-String-keyed BTreeMap inserts) and Step 7's per-statement whole-file query in `classify_stmt_kind` (`build.rs:758-767` → `call_names_on_lines` runs a QueryCursor over the entire tree per call/expression statement, `ast.rs:3805-3810`) — the last remaining quadratic-*shaped* term in assemble.

**Conclusion:** Step 5b is the largest single serial item *inside* `assemble_graph` and includes a hidden parallelizable whole-repo index pass, but it is one slice (~2–6s est.) of a ~17.5s broad serial tail. The directive is half-right: worth doing, insufficient alone to make gate-9 robust. This must be confirmed by a 30-minute instrumentation pass before implementation (see VERDICT).

---

# DESIGN — fused Step 5+5b: parallel-compute → serial-deterministic-apply

Template: `rematerialize_rust_receiver_keys` (`call_graph.rs:1123-1192`: immutable-read compute into `updates` at `:1128-1174`, then ordered serial apply at `:1176-1191`) and C1/C2 (parallel extraction, serial in-order flatten — `call_graph.rs:469-470`, spec §2a).

## Pre-passes (all before the compute; deterministic)

- **5a.0 — pre-warm the CallArgsIndex in parallel:** `files.par_iter().for_each(|(_, p)| { p.call_args_index(); })`. Moves the hidden serial whole-repo index build into a parallel phase. Sound: `OnceLock::get_or_init` is exactly-once, racers block, the value is a pure function of the file.
- **5a.1 — per-callee param table (kills cost #3):** one map `BTreeMap<(String, String, usize), Vec<String>>` keyed `(file, name, start_line)`, holding exactly the `normalized_param_names` + Python `self`/`cls` gate result of `build.rs:456-485` — a pure function of `(callee_parsed, callee_id)`, computed **once per function** (parallelizable per file) instead of once per resolved site.
- **5a.2 — per-(callee, param) Def-node memo (kills cost #4):** hoist the probe loop `build.rs:514-525` into `BTreeMap<((String,String,usize), String), Option<NodeIndex>>`, computed once per pair against the (by then frozen) `var_index`. Behavior-identical by construction — same probe, run once.

## Compute (parallel, read-only)

Flatten work items **serially** in today's exact iteration order — `cg.calls` is `BTreeMap<FunctionId, BTreeSet<CallSite>>`, and Steps 5 and 5b iterate it identically (`build.rs:397`, `:429`):

```rust
let work: Vec<(&FunctionId, &CallSite)> = /* nested iteration, serial */;

struct SiteEdges {
    call: Vec<(NodeIndex, NodeIndex, CpgEdge)>, // Step-5 stream: Call+Return pairs, resolved order
    flow: Vec<(NodeIndex, NodeIndex)>,          // Step-5b stream: arg→param, (resolved × param-i) order
}
let results: Vec<SiteEdges> = work.par_iter().map(compute_site).collect();
```

`compute_site` per item: `resolve_call_site` **once**; emit the call stream only if `func_index` has the caller (Step 5's `continue` at `build.rs:403-405` guards *only* the call stream — Step 5b has no such guard, preserve that asymmetry); emit the flow stream replicating `build.rs:431-529` branch-for-branch (including `arg_texts.is_empty() → continue` firing *before* the callee-file lookup, `build.rs:439-444`), using the CallArgsIndex lookup, the 5a.1 param table, and the 5a.2 memo. Everything read is immutable: `&cg`, `&files`, `&func_index`, `&var_index` (Steps 2–3 finished; Step 5b never mutates the indexes today).

## Barrier and apply

The **barrier is the `collect()`** — rayon's indexed collect over a `Vec` preserves item order exactly and completes all compute before apply starts. Apply is serial and is the only phase touching `graph`:

```rust
for se in &results { for &(a, b, ref w) in &se.call { graph.add_edge(a, b, w.clone()); } }  // Step-5 stream
for se in &results { for &(a, b) in &se.flow { graph.add_edge(a, b, CpgEdge::DataFlow); } } // Step-5b stream
```

Two passes reproduce today's global edge sequence exactly: all Step-5 edges in nested-loop order, then all Step-5b edges in nested-loop order. **Steps 5/5b create no nodes** — `NodeIndex` assignment is untouched; only the edge-append sequence matters, and it is bit-for-bit reproduced.

---

# ARCHITECTURE — the invariants

## Determinism + cache-byte parity

- **S2 did not lift the insertion-order constraint.** The S2 node-identity work (spec `docs/superpowers/specs/2026-06-13-prism-s2-node-identity-design.md`; commits `f78a94f`…`dd60ed6`, cache v4→v5) made byte ranges *additive* identity metadata, composite-keyed the indexes, and byte-sorted same-line buckets (`build.rs:646-665`) — but ordering fallbacks are still "then build-order NodeIndex" (spec §, line 108) and the cache still serializes **nodes in `node_indices()` order and edges in `edge_indices()` order** (`cpg_cache.rs:96-106`, `:186-204`, v15 at `:57`), reconstructed in the same order to preserve NodeIndex stability (`:93-95`). s1-followups item 2's constraint stands verbatim.
- **This design preserves cache bytes exactly, no `CACHE_VERSION` bump:** no new nodes, identical edge-append order, all computed values pure functions of immutable inputs. (v7's `git_sha` key means cross-binary cache reuse never happens anyway — but in-run byte determinism is still the enforced contract.)
- **Parity tests (mirror S1 C2 + S1.5):** extend `tests/infra/parallel_equality_test.rs` — `cpg_build_parallel_matches_serial_reference_in_order` (:26) and `cache_blob_bytes_identical_serial_vs_parallel` (:43). (1) Freeze today's Steps 5+5b as a `#[cfg(test)]` reference (the S1.5 oracle pattern, like `call_argument_texts_at_reference`, `ast.rs:4402`) and assert identical in-order `(source, target, weight)` edge streams on the C2 corpus (`src/navigation` + `src/cpg` subsets per item 7). (2) Byte-compare `cpg-cache.bin` from a 1-thread pool build vs an N-thread build, and across 3 repeated runs. (3) Tier-A `--matrix-only` pre-commit, `--quick` pre-review (this touches `src/cpg/`).

## Send/Sync + borrow

- `resolve_call_site` is `&self` → `resolve_call_site_full` (`resolution.rs:1109`, `:673`); it reads only `CallGraph` BTreeMaps/sets and `Option<ScopeGraph>` (`name_resolution/graph.rs:74` — plain `BTreeMap`/`Vec` data). Grep confirms **no `RefCell`/`Mutex`/`RwLock`/`Cell`** anywhere in `call_graph.rs`, `resolution.rs`, `resolution_receiver.rs`, or `name_resolution/` — no interior-mutability hazard; all read types are `Sync`.
- `ParsedFile: Sync` is already **proven in production**: Phase 1/2 and the DFG capture `&ParsedFile` in `par_iter` closures and walk the tree (`call_graph.rs:471-472`, `:556-557`; `data_flow.rs:225-226`). `Node<'_>` handles are created and dropped within each closure, never sent.
- `OnceLock<CallArgsIndex>` (`ast.rs:118`): concurrent first-init is sound — std guarantees the closure runs exactly once, racers block; the value is thread-independent. The 5a.0 pre-warm makes Step-5b reads contention-free anyway.
- Borrow split is clean: compute borrows `cg`/`files`/`func_index`/`var_index` immutably; `graph` is mutated only in the serial apply. No aliasing.

## Option-C safety

The final graph is byte-identical (nodes, indexes, edge sequence), so every downstream traversal — nav queries, slices, diff-review — is input-identical and deterministic. `cli_nav_compat` byte-identity (S1 spec gate row "All", spec line 318) plus goldens are the enforcement; no new output surface is introduced.

---

# VERDICT — GO, scoped, with one pairing

**GO** on the fused Step 5+5b parallel-compute→serial-apply **including the three constant-factor kills** (single resolve, per-callee param table, param-Def memo) and the parallel index pre-warm — but **instrument first**, and **pair it with one adjacent serial kill**, because Step 5b alone is not where most of the residual lives.

- **Expected buy (hugo):** Step 5+5b serial content estimated 2–6s (index first-init + double resolve + per-site param recompute + probes). Parallelizing the compute at ~8 effective cores and deleting the redundant work → wall −2 to −5s → **~13.5–16.5s**, user flat-to-down → ratio **≈1.55–1.9**. Pessimistic case (Step 5+5b residual only ~1s): wall ~17.5s → ratio ≈1.48 — a **miss**. That is why the gate crossing is likely but not guaranteed by the directive alone.
- **The robustness pairing (pick #1, it's the cheapest):** (1) build `GoTypeProvider`/live-sets **once** and share — today they're computed twice per cold build (`call_graph.rs:1303-1305` vs `context.rs:272-276`, `:84`); (2) replace Phase-3 Level-3's per-caller whole-tree `find_function_by_name` (`call_graph.rs:853`) with a FunctionTable lookup; (3) index Step 7's per-statement `call_names_on_lines` whole-file query (`build.rs:758-767`) with a per-file line→names map (S1.5 shape); (4) for Rust corpora (doesn't move the hugo gate, but the biggest absolute buy on prism's 22.7s): parallelize the compute half of `rematerialize_rust_receiver_keys` — it is already compute→apply shaped (`call_graph.rs:1128-1191`).
- **Measure before implementing:** (a) per-phase wall timers (parse / DFG / CG Phases 1-3 / Go passes / assemble Steps 1–9 / registry+live-types) on cold hugo **and** prism — a ~30-minute `eprintln!`-level pass that decisively apportions the 17.5s; (b) `sample` during cold hugo — expect `index_call_args`, `resolve_call_site_full`, `reconstruct_function_node`, and `GoTypeProvider` frames if the analysis above is right; (c) after: `/usr/bin/time` user/wall on hugo (gate-9), edge-stream + cache-byte parity, Tier-A `--matrix-only` + `--quick`.
- **If the profile contradicts this** (Step 5+5b measures <1s on hugo): the design above still ships as hygiene at low risk, but the gate-9 effort redirects to items (1)–(3), which are the same proven patterns with none of the parity risk.

One process note: several claude.ai MCP connectors (Gmail, Drive, Calendar, etc.) require OAuth and are unavailable in this session — irrelevant to this analysis, but flagging since the harness surfaced it.
