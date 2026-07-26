# Blind pairwise code-review judgment — G5F-IMPL-04

Two different engineers (Arm A, Arm B) independently completed the SAME task
from the same starting commit. You see the task brief and both final diffs.
You do NOT know who the engineers are; judge only the work. Answer the JSON
schema exactly; a_materially_better/b_materially_better may not both be true;
both false = parity. Ignore any VERIFICATION.md or process-artifact files in
a diff — judge the code and tests.

## Task brief (both arms received this; process environments may differ — judge the WORK)

You are an expert Rust engineer working as the IMPLEMENTER on `a2a-bridge` (an ACP↔A2A bridge + workflow orchestrator). Your session cwd IS the a2a-bridge repo, on branch `feat/e6-node-retry`. You EDIT the working tree and run `cargo`. The ONE task is below the marker; do EXACTLY it, no more.

## Operating rules
- **Scope discipline:** implement ONLY what the task below the marker specifies. E6 = opt-in PER-NODE retry of TRANSIENT agent failures (crash / `_dyld_start` startup flake / overload / watchdog timeout) in the COLD workflow executor (`run_node`), default OFF (zero behavior change unless a node sets `retry`). The reset between attempts is `release_session` (bridge-side) + a NEW `AgentRegistry::invalidate(agent)` (atomic Slot replace + REUSE the existing detached lease-drained `spawn_retirement` → next `resolve` RESPAWNS a fresh process). DEFERRALS (do NOT build): respawn-only-on-death optimization, resume-re-run of exhausted failures, warm-turn retry, write-node pre-retry reset, rich `NodeRetry` event, global retry default.
- **The plan + spec are GROUND TRUTH and APPROVED (dual-reviewed + RE-reviewed: codex-xhigh + Opus, all folded).** Read `docs/superpowers/plans/2026-06-24-e6-node-retry.md` — its **`## v2` (PR-FIX-1..10) + `## v3` (RR2-FIX-1..6) sections are BINDING and SUPERSEDE the v1 task bodies above them. READ `## v2` + `## v3` FIRST, then the matching v1 task body.** Binding spec: `docs/superpowers/specs/2026-06-24-e6-node-retry.md` (its `## v2` SR-FIX-1..6 + `## v3` RR-FIX-1..4 sections are binding). **VERIFY every signature/anchor against the REAL code before writing** — the plan's `file:line` were verified at authoring but the tree may have shifted a few lines.
- **Key confirmed facts (do NOT relitigate — the dual review + re-review settled these):**
  - Transient set = `AgentCrashed | AgentOverloaded | AgentTimedOut` ONLY (`BridgeError::is_transient()`, COLD-only; do NOT reuse the warm `resilient.rs` classifier).
  - `RetryPolicy { max_attempts: u32, backoff_ms: u64, backoff_cap_ms: Option<u64> }` on `WorkflowNode.retry` (`#[serde(default, skip_serializing_if="Option::is_none")]`, rides `encode_workflow_spec` like `panel`). `backoff_for(attempt)` is OVERFLOW-SAFE (`checked_shl`/saturating, clamp to cap, default cap 30_000). `attempts()=max_attempts.max(1)`.
  - `WorkflowNode.retry` is a REQUIRED struct field → add `retry: None` to ALL **42** workspace `WorkflowNode {` literals (across bridge-workflow/coordinator/a2a-inbound/mcp/bin + their tests); the gate is `cargo build --workspace`.
  - `AgentRegistry::invalidate(&self, agent: &AgentId)` — trait method DEFAULT no-op (`ports.rs:197`), real impl on `Registry`: a SHARED `write_lock: Mutex<()>` across `apply` + `invalidate` (apply's load→build→store is sync → deadlock-free); under the lock, re-load state, NO-OP if the agent vanished, else replace its slot with `Slot::new((*entry).clone())` (`Slot::new` ALREADY returns `Arc<Slot>` — NO double-Arc), `state.store`, then `old_slot.retired.store(true, SeqCst); Self::spawn_retirement(old_slot.clone(), self.grace);` (REUSE the existing helper at `registry.rs:265`; do NOT await `retire()`). `State { slots, default }`.
  - The retry loop is in `run_node` (`executor.rs:158-388`), spanning resolve→configure→prompt→drain. `self.registry: Arc<dyn AgentRegistry>` IS reachable (`executor.rs:119/120`). `tokio::time` IS available (workspace `tokio` full). The resolve-error `backend: None` branch is the `self.registry.resolve` Err arm (`executor.rs:269`).
  - **RR2-FIX-1 (CRITICAL):** the per-attempt carrier must hold `Option<Resolved>` (which owns the retirement LEASE — `ports.rs:190`), NOT just `Arc<dyn AgentBackend>` — dropping the `Resolved` before `release_session` lets a concurrent retire kill the process mid-cleanup. Either carry `Option<Resolved>` OR do `release_session` INSIDE the attempt scope while `resolved` is still live.
  - **RR2-FIX-2:** transient attempts carry `usage: Option<UsageSnapshot>`; an EXHAUSTED transient failure returns the last attempt's usage (SR-FIX-4 last-attempt; do NOT sum — `UsageSnapshot.size` isn't additive).
  - **RR2-FIX-3:** resume-compat tests = (a) drop the executor STREAM/future mid-retry → no `NodeFinished`/checkpoint; (b) seed a `Working` task row + no checkpoint → `resume_working_tasks` re-runs the node. Do NOT use cancellation as a crash proxy (cancel EMITS `NodeFinished` → checkpointed) and do NOT abort `spawn_detached_workflow` (drops `Finalizer` → `Failed`, not a Working crash).
  - **RR2-FIX-4:** add `tracing.workspace = true` to `crates/bridge-workflow/Cargo.toml` BEFORE using `tracing::warn!` in T5.
  - T6/SR-FIX-3: the configure fail-fast (`executor.rs:275`, `ConfigInvalid` non-transient) MUST stay — add a retry-ENABLED test asserting 1 configure attempt / 0 prompts / 0 invalidates.
  - PR-FIX-6 test honesty: the executor's fake `impl AgentRegistry` (bridge-workflow does NOT dep bridge-registry) must COUNT `resolve` + `invalidate` and make SUCCESS depend on a POST-`invalidate` fresh backend (else the test passes with `resolve` outside the loop).
- **TDD:** write the failing test(s) FIRST, run to fail, implement to green. The gate per task is **`cargo test --workspace --all-targets`** (or the task's stated `cargo build --workspace` for the literal-ripple tasks) — `cargo build`/`--bin`/`--no-run` MISS test-only literal breaks + stale cross-crate counts.
- **Conventions:** match surrounding style; `#[serde(default, skip_serializing_if=...)]` for additive snapshot fields; derive what neighbours derive; READ the cited code BEFORE coding.
- **DO NOT COMMIT. DO NOT run any `git` command that mutates state** (no `git add/commit/checkout/restore/stash/clean`). Leave changes UNCOMMITTED — the controller verifies + commits. `git status`/`git diff` (read-only) are fine.
- **NOTE the `_dyld_start`/rustc-stall sandbox flake:** if a test BINARY hangs at startup or a build stalls, report it (the controller re-runs in the clean host env). Use a `timeout` to distinguish a real deadlock from the flake.

## Process
1. Read the cited plan task (the matching `### Task N` body) + ALL `## v2`/`## v3` PR-FIX/RR2-FIX entries that name it + the spec + the real code you'll touch. Confirm every signature against the real tree.
2. Implement (TDD). Then run + report exact commands + counts:
   - the task's `cargo test -p <crate> …` target(s), THEN `cargo test --workspace --all-targets` (MUST compile + pass). If a runtime test stalls on the sandbox flake, report it for the controller.
   - `cargo fmt --all` then `cargo fmt --all --check`; `cargo clippy --workspace --all-targets -- -D warnings`.
3. Self-review: completeness vs the task + the PR-FIX/RR2-FIX amendments; ALL impls/call sites/literals updated (`--all-targets` green); new tests assert REAL behavior (not tautologies).

## Report (plain text — DO NOT commit)
- **STATUS:** DONE | DONE_WITH_CONCERNS | BLOCKED | NEEDS_CONTEXT
- What you implemented; the exact test list + pass/fail counts; files changed (one-line why each). Self-review findings + any concerns for the controller's whole-branch review.

THE TASK:

# TASK T3 — `[[workflows.nodes]].retry` config + map → `WorkflowNode.retry`

Implement the plan's **`### Task 3`** body with **PR-FIX-9** (test the actual graph mapping via `load_workflows`, not just TOML deser). Read those entries first. Touches `bin/a2a-bridge/src/config.rs`.

## 1. `RetryToml` + `WorkflowNodeToml.retry`
```rust
#[derive(Debug, serde::Deserialize)]
pub struct RetryToml {
    pub max_attempts: u32,
    pub backoff_ms: u64,
    #[serde(default)]
    pub backoff_cap_ms: Option<u64>,
}
```
Add `#[serde(default)] pub retry: Option<RetryToml>,` to `WorkflowNodeToml`.

## 2. Map → `WorkflowNode.retry` at the graph-build site
At the `WorkflowNode {` build in the workflows loader (`config.rs:970`, reachable via `RegistryConfig::load_workflows`), map:
```rust
retry: n.retry.as_ref().map(|r| bridge_workflow::graph::RetryPolicy {
    max_attempts: r.max_attempts,
    backoff_ms: r.backoff_ms,
    backoff_cap_ms: r.backoff_cap_ms,
}),
```
(VERIFY the exact field/var names against the real `WorkflowNode { .. }` literal at `:970` + the `RetryPolicy` signature T2 produced.)

## 3. Tests (TDD — write FIRST, run to fail, implement to green)
- `workflow_node_retry_parses`: parse `"{AGENTS_HEADER}\n[[workflows]]\nid=\"wf1\"\n[[workflows.nodes]]\nid=\"only\"\nagent=\"codex\"\nprompt_file=\"p.md\"\ninputs=[]\nretry = {{ max_attempts = 3, backoff_ms = 250 }}\n{SERVER_FOOTER}"` → `cfg.workflows[0].nodes[0].retry` is `Some` with `(3, 250)`.
- **PR-FIX-9 — `workflow_node_retry_maps_into_graph` (MANDATORY):** the deser test alone does NOT prove the mapping reaches `WorkflowNode.retry`. Drive the ACTUAL graph build: create a TEMP prompt file (`prompt_file`), call `RegistryConfig::load_workflows` (or whatever the real graph-build entry is — VERIFY the fn name + signature; the build is at `config.rs:970`), and assert the resulting `WorkflowGraph.nodes[0].retry == Some(RetryPolicy { max_attempts: 3, backoff_ms: 250, backoff_cap_ms: None })`. (Mirror however the existing config tests construct a temp prompt + invoke the loader — e.g. the panel/workflow tests near `config.rs:2364`.)

## Gate
- `cargo test -p a2a-bridge workflow_node_retry` → PASS (both tests).
- `cargo build --workspace` + `cargo test --workspace --all-targets` → MUST pass.
- `cargo fmt --all --check`; `cargo clippy --workspace --all-targets -- -D warnings`.

DO NOT COMMIT. Report STATUS + exact commands + counts + files changed + the real `load_workflows` (or equivalent) entry name for the record.


## Probe question (answer in `probe_answer`, per arm)

Focus on TEST RIGOR: for each arm, would its tests FAIL on the pre-change code, do they cover negative/edge cases per new code path, and do they assert real behavior rather than trivially passing? Name the strongest and weakest test in each arm.

## Arm A diff

```diff
diff --git a/bin/a2a-bridge/src/config.rs b/bin/a2a-bridge/src/config.rs
index d315bcf..e234100 100644
--- a/bin/a2a-bridge/src/config.rs
+++ b/bin/a2a-bridge/src/config.rs
@@ -256,6 +256,14 @@ pub struct PanelTomlSection {
     pub weights: BTreeMap<String, f64>,
 }
 
+#[derive(Debug, serde::Deserialize)]
+pub struct RetryToml {
+    pub max_attempts: u32,
+    pub backoff_ms: u64,
+    #[serde(default)]
+    pub backoff_cap_ms: Option<u64>,
+}
+
 #[derive(Debug, serde::Deserialize)]
 pub struct WorkflowNodeToml {
     pub id: String,
@@ -263,6 +271,8 @@ pub struct WorkflowNodeToml {
     pub prompt_file: String,
     #[serde(default)]
     pub inputs: Vec<String>,
+    #[serde(default)]
+    pub retry: Option<RetryToml>,
 }
 
 /// `[registry]` section — optional; controls which cmds are allowed.
@@ -945,7 +955,7 @@ impl RegistryConfig {
         ConfigError,
     > {
         use bridge_core::ids::{AgentId, NodeId, WorkflowId};
-        use bridge_workflow::graph::{WorkflowGraph, WorkflowNode};
+        use bridge_workflow::graph::{RetryPolicy, WorkflowGraph, WorkflowNode};
 
         let agent_ids: std::collections::HashSet<&str> =
             self.agents.iter().map(|a| a.id.as_str()).collect();
@@ -982,7 +992,11 @@ impl RegistryConfig {
                         .map_err(|e| {
                             ConfigError::Registry(format!("workflow {} input id: {e:?}", w.id))
                         })?,
-                    retry: None,
+                    retry: n.retry.as_ref().map(|r| RetryPolicy {
+                        max_attempts: r.max_attempts,
+                        backoff_ms: r.backoff_ms,
+                        backoff_cap_ms: r.backoff_cap_ms,
+                    }),
                 });
             }
             let g = WorkflowGraph {
@@ -2480,6 +2494,44 @@ addr="127.0.0.1:8080"
         g.validate().unwrap();
     }
 
+    #[test]
+    fn workflow_node_retry_parses() {
+        let toml = format!(
+            "{AGENTS_HEADER}\n[[workflows]]\nid=\"wf1\"\n\
+            [[workflows.nodes]]\nid=\"only\"\nagent=\"codex\"\nprompt_file=\"p.md\"\ninputs=[]\n\
+            retry = {{ max_attempts = 3, backoff_ms = 250 }}\n{SERVER_FOOTER}"
+        );
+        let cfg = RegistryConfig::parse(&toml).unwrap();
+        let retry = cfg.workflows[0].nodes[0].retry.as_ref().unwrap();
+        assert_eq!(retry.max_attempts, 3);
+        assert_eq!(retry.backoff_ms, 250);
+        assert_eq!(retry.backoff_cap_ms, None);
+    }
+
+    #[test]
+    fn workflow_node_retry_maps_into_graph() {
+        let dir = tempfile::tempdir().unwrap();
+        std::fs::write(dir.path().join("p.md"), "retry {{input}}").unwrap();
+        let toml = format!(
+            "{AGENTS_HEADER}\n[[workflows]]\nid=\"wf1\"\n\
+            [[workflows.nodes]]\nid=\"only\"\nagent=\"codex\"\nprompt_file=\"p.md\"\ninputs=[]\n\
+            retry = {{ max_attempts = 3, backoff_ms = 250 }}\n{SERVER_FOOTER}"
+        );
+        let cfg = RegistryConfig::parse(&toml).unwrap();
+        let map = cfg.load_workflows(dir.path()).unwrap();
+        let graph = map
+            .get(&bridge_core::ids::WorkflowId::parse("wf1").unwrap())
+            .unwrap();
+        assert_eq!(
+            graph.nodes[0].retry,
+            Some(bridge_workflow::graph::RetryPolicy {
+                max_attempts: 3,
+                backoff_ms: 250,
+                backoff_cap_ms: None,
+            })
+        );
+    }
+
     #[test]
     fn parses_workflow_panel_weights() {
         let dir = tempfile::tempdir().unwrap();

```

## Arm B diff

```diff
diff --git a/bin/a2a-bridge/src/config.rs b/bin/a2a-bridge/src/config.rs
index d315bcf..7e07d95 100644
--- a/bin/a2a-bridge/src/config.rs
+++ b/bin/a2a-bridge/src/config.rs
@@ -263,6 +263,17 @@ pub struct WorkflowNodeToml {
     pub prompt_file: String,
     #[serde(default)]
     pub inputs: Vec<String>,
+    #[serde(default)]
+    pub retry: Option<RetryToml>,
+}
+
+/// Per-node transient-failure retry (E6); absent = no retry (1 attempt).
+#[derive(Debug, serde::Deserialize)]
+pub struct RetryToml {
+    pub max_attempts: u32,
+    pub backoff_ms: u64,
+    #[serde(default)]
+    pub backoff_cap_ms: Option<u64>,
 }
 
 /// `[registry]` section — optional; controls which cmds are allowed.
@@ -982,7 +993,14 @@ impl RegistryConfig {
                         .map_err(|e| {
                             ConfigError::Registry(format!("workflow {} input id: {e:?}", w.id))
                         })?,
-                    retry: None,
+                    retry: n
+                        .retry
+                        .as_ref()
+                        .map(|r| bridge_workflow::graph::RetryPolicy {
+                            max_attempts: r.max_attempts,
+                            backoff_ms: r.backoff_ms,
+                            backoff_cap_ms: r.backoff_cap_ms,
+                        }),
                 });
             }
             let g = WorkflowGraph {
@@ -2496,6 +2514,43 @@ addr="127.0.0.1:8080"
         assert_eq!(g.panel.as_ref().unwrap().weights["benefit"], 0.4);
     }
 
+    #[test]
+    fn workflow_node_retry_parses() {
+        let toml = format!(
+            "{AGENTS_HEADER}\n[[workflows]]\nid = \"wf1\"\n\
+            [[workflows.nodes]]\nid = \"only\"\nagent = \"codex\"\nprompt_file = \"p.md\"\ninputs = []\n\
+            retry = {{ max_attempts = 3, backoff_ms = 250 }}\n{SERVER_FOOTER}"
+        );
+        let cfg: RegistryConfig = toml::from_str(&toml).unwrap();
+        let r = cfg.workflows[0].nodes[0].retry.as_ref().unwrap();
+        assert_eq!((r.max_attempts, r.backoff_ms), (3, 250));
+        assert_eq!(r.backoff_cap_ms, None);
+    }
+
+    #[test]
+    fn workflow_node_retry_maps_into_graph() {
+        let dir = tempfile::tempdir().unwrap();
+        std::fs::write(dir.path().join("p.md"), "review {{input}}").unwrap();
+        let toml = format!(
+            "{AGENTS_HEADER}\n[[workflows]]\nid = \"wf1\"\n\
+            [[workflows.nodes]]\nid = \"only\"\nagent = \"codex\"\nprompt_file = \"p.md\"\ninputs = []\n\
+            retry = {{ max_attempts = 3, backoff_ms = 250 }}\n{SERVER_FOOTER}"
+        );
+        let cfg = RegistryConfig::parse(&toml).unwrap();
+        let wfs = cfg.load_workflows(dir.path()).unwrap();
+        let g = wfs
+            .get(&bridge_core::ids::WorkflowId::parse("wf1").unwrap())
+            .unwrap();
+        assert_eq!(
+            g.nodes[0].retry,
+            Some(bridge_workflow::graph::RetryPolicy {
+                max_attempts: 3,
+                backoff_ms: 250,
+                backoff_cap_ms: None,
+            })
+        );
+    }
+
     #[test]
     fn shipped_panel_config_loads_and_wires_reserved_vars() {
         let base = std::path::Path::new(env!("CARGO_MANIFEST_DIR")).join("../../examples");
diff --git a/crates/bridge-workflow/src/graph.rs b/crates/bridge-workflow/src/graph.rs
index 389a798..bc4964d 100644
--- a/crates/bridge-workflow/src/graph.rs
+++ b/crates/bridge-workflow/src/graph.rs
@@ -36,13 +36,11 @@ impl RetryPolicy {
         let shift = attempt.saturating_sub(1);
         // `checked_shl` only rejects shift >= bit-width (it WRAPS the value otherwise), so a large
         // `attempt` would silently wrap `backoff_ms << shift` to a small value and defeat the cap.
-        // Multiply by `2^shift` with `checked_mul` (saturating to MAX) to catch VALUE overflow.
+        // Multiply by `2^shift` with `saturating_mul` to catch VALUE overflow.
         let base = if shift >= 64 {
             u64::MAX
         } else {
-            self.backoff_ms
-                .checked_mul(1u64 << shift)
-                .unwrap_or(u64::MAX)
+            self.backoff_ms.saturating_mul(1u64 << shift)
         };
         std::time::Duration::from_millis(base.min(cap))
     }

```
