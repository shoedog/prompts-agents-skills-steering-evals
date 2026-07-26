# Blind pairwise code-review judgment — HKW-IMPL-06

Two different engineers (Arm A, Arm B) independently completed the SAME task
from the same starting commit. You see the task brief and both final diffs.
You do NOT know who the engineers are; judge only the work. Answer the JSON
schema exactly; a_materially_better/b_materially_better may not both be true;
both false = parity. Ignore any VERIFICATION.md or process-artifact files in
a diff — judge the code and tests.

## Task brief (both arms received this; process environments may differ — judge the WORK)

You are an expert Rust engineer working as the IMPLEMENTER on `a2a-bridge` (an ACP↔A2A bridge + workflow
orchestrator). Your session cwd IS the a2a-bridge repo, on feature branch `feat/slice-7a-rich-acp`. You EDIT the
working tree and run `cargo`. The specific ONE task is below the marker; do EXACTLY it, no more.

## Operating rules
- **Scope discipline:** implement ONLY what the task specifies. Do NOT touch files outside the task's stated set.
  Honor INERT / byte-identical / back-compat requirements (UPDATE-MINIMAL: NO new `Update` variant; the ACP handler
  stays NON-BLOCKING — no `.await`/store-write on the event loop; the S6 node-frame byte-identity for no-rich runs;
  W3b resume reads typed checkpoints only).
- **The plan is GROUND TRUTH and APPROVED (dual plan-reviewed → fix-then-implement, all fixes folded).** Read
  `docs/superpowers/plans/2026-06-20-slice-7a-rich-acp.md` — its **`## v2 … (BINDING; PFIX-A..K)` section SUPERSEDES
  any contradicting task body text. READ THE PFIX SECTION FIRST.** The binding spec is
  `docs/superpowers/specs/2026-06-20-slice-7a-rich-acp.md` (FIX-1..13). VERIFY each signature/method against the
  REAL code before using it (the PFIX list corrects several SDK shapes + the test sketches).
- **Key real APIs (PFIX-confirmed):** the rich-sink factory is `make(&NodeId)` (NO op param — it CLOSES OVER op,
  built in `spawn_detached_workflow`). `ToolCallUpdate` fields are NESTED: `u.fields.{kind,status,title,content,
  locations}`. The SDK types (`SessionUpdate`/`Plan`/`ToolCall`/`ToolKind`/`ToolCallStatus`/`ToolCallContent`/
  `ContentBlock`/…) are `#[non_exhaustive]` → match arms need `_ =>` wildcards; TEST fixtures BUILD SDK values via
  constructors (`Plan::new`, `ToolCall::new(id,title)`+builders, `ContentChunk::new`, `TextContent::new`) — mirror
  `acp_backend.rs:2994-3022`. SDK enums have NO `Display` → hand-write `match → &'static str` (+ `_ => "other"`).
  `AgentMessageChunk(ContentChunk)` → `chunk.content` is a `ContentBlock`. `DetachedRichSink.queue` is
  `std::sync::Mutex<VecDeque<_>>` (NOT tokio — `record` is sync). `record_event_sequenced` is a DEFAULTED trait
  method returning `Err(StoreFailure)` (SQLite+Memory override; the 2 custom impls `LegacyFallbackStore`
  `server.rs:8653` + `tests/workflow_producer.rs:2373` keep the default). `PlanEntry`/`ContentSummary` derive
  `Clone, Debug, PartialEq, Eq, Serialize, Deserialize`.
- **TDD:** write the failing test(s) named in the task FIRST, run them to fail, then implement to green. Tests
  assert REAL behavior.
- **Conventions:** match surrounding code style; `tokio::sync::Mutex` for ASYNC-held locks but `std::sync::Mutex`
  where a sync method locks; derive what neighbours derive; keep files focused. Read the cited code BEFORE coding.
- **DO NOT COMMIT. DO NOT run any `git` command that mutates state.** Leave changes UNCOMMITTED — the controller
  verifies + commits. `git status`/`git diff` (read-only) are fine.

## Process
1. Read the cited plan task + the PFIX section + the spec sections + the existing code you'll touch.
2. Implement TDD. Then run, in order (report exact commands + counts):
   - the specific `cargo test -p <crate> …` target(s), THEN `cargo test --workspace --no-run`
   - `cargo fmt --all` then `cargo fmt --all --check`
   - `cargo clippy -p <crate> --all-targets -- -D warnings` (no new warnings in files you touched)
   - NOTE the `_dyld_start` PTY flake: if a test BINARY hangs at startup, report it (the controller re-runs in a
     clean env). Use a `timeout` to distinguish a real deadlock.
3. Self-review: completeness vs the task; back-compat (UPDATE-MINIMAL / non-blocking handler / S6 byte-identity /
   W3b); ALL call sites of any changed signature/enum updated (`cargo test --workspace --no-run` MUST pass).

## Report (plain text — DO NOT commit)
- **STATUS:** DONE | DONE_WITH_CONCERNS | BLOCKED | NEEDS_CONTEXT
- What you implemented; the test list + results; files changed. Self-review findings + concerns.

THE TASK:

# Slice 7a — TASK 8 (S7a.2): The merged seq-ordered snapshot projection + both reattach sites + goldens

Implement **Task 8** from `docs/superpowers/plans/2026-06-20-slice-7a-rich-acp.md` in
`crates/bridge-a2a-inbound/src/server.rs`. The final S7a task — wire the rich transcript into the reattach snapshot.

## Binding (PFIX-H — SUPERSEDE the v1 sketch)
- The snapshot must come from ONE consistent read returning `{ snap: TaskProgressSnapshot, events: Vec<OrchEvent> }`
  — `fold_or_typed_snapshot` (`server.rs:1102`) today returns ONLY `snap` and DISCARDS `journal_fold_inputs().events`.
  Change it (or add a sibling) to return BOTH.
- Add `rich_snapshot_frames(snap: &TaskProgressSnapshot, events: &[OrchEvent], cursor: Option<i64>) ->
  Vec<WorkflowProgressFrame>` = the EXISTING node frames `snapshot_frames(snap, None)` MERGED seq-sorted with the
  folded rich frames, then cursor-filtered ONCE.
- Replace `snapshot_frames(&snap, cursor)` at BOTH reattach call sites (`server.rs:1054` terminal/subscribe + `:1194`
  working_sse) with `rich_snapshot_frames(&snap, &events, cursor)`; PRESERVE the `SnapshotComplete` sentinel seq
  (re-derived from the MERGED last frame) + the working-SSE `dedup_floor`/`cut_seq` (`:1205`).
- **NODE byte-identity:** for a no-rich task, `events` has no rich kinds → rich frames empty → the merged list ==
  the node frames → the S6 golden (`golden_two_node_run_wire_tuples`) STILL passes.

## The rich fold (over `events`, seq order)
- **Plan:** keep ONLY the LATEST `Plan` event → one `FrameKind::Plan` frame at that event's seq.
- **ToolCall / ToolCallUpdate (by `tool_call_id`):** walk in seq order; maintain `id -> (merged state, last_seq,
  had_base: bool)`. `ToolCall` → set/replace the base (had_base=true). `ToolCallUpdate` → PATCH the base's present
  fields (sparse; `Some` replaces, incl. `Some(empty)`), update last_seq. At the end, per id: if `had_base`, emit
  ONE `FrameKind::ToolCall` (merged current state) at `last_seq`; else (orphan update) emit a `FrameKind::ToolCall
  Update` at its seq.
- (Mode/config/commands are deferred — not in `events`.) Use `reattach::frame_from_orch` where it fits, or build the
  folded `ToolCall` frame directly from the merged state.

## Steps
1. Read `server.rs` `fold_or_typed_snapshot` (`:1102`), `snapshot_frames` (`:1277`), the two reattach sites
   (`:1049-1095` terminal + `:1160-1210` working_sse incl. the `SnapshotComplete` sentinel `:1057/1195` + dedup
   `:1205`); `journal_fold_inputs`; the S6 golden test (`:8975`).
2. TDD — failing tests FIRST: (a) the S6 `golden_two_node_run_wire_tuples` STILL passes (no-rich); (b) a new rich
   golden:
```rust
#[tokio::test]
async fn rich_snapshot_folds_toolcall_interleaved() {
    // journal: node_started(1), tool_call(2,t1,in_progress), tool_call_update(3,t1->completed), node_finished(4)
    // expect (seq, tag) ordered: (3,"tool_call" folded current=completed), (4,"node_finished") [start collapsed]
    let frames = rich_snapshot_frames(&snap, &events, None);
    assert_eq!(tags(&frames), vec![(3, "tool_call"), (4, "node_finished")]);
}
```
3. Implement `rich_snapshot_frames` (the merge + the fold) + change `fold_or_typed_snapshot`→`{snap, events}` (a
   small struct or tuple) + swap both call sites + re-derive the sentinel from the merged last frame. (Reuse
   `frame_from_orch` for the folded ToolCall if the merged state maps cleanly to an `OrchEventKind::ToolCall`.)
4. Run → PASS (the S6 golden + the new rich golden + the existing reattach/Last-Event-ID/working-sse tests).
   `cargo test -p bridge-a2a-inbound`; `cargo test --workspace --no-run`; fmt; `cargo clippy -p bridge-a2a-inbound
   --all-targets -- -D warnings`. Remove the Task-7 scoped `dead_code` allow if `frame_from_orch` is now used.
5. Self-review: no-rich → identical node frames (S6 golden)? the ToolCall fold by id (latest, orphan-tolerant)?
   Plan latest-only? both sites swapped? sentinel re-derived? cursor applied once on the merged list?

Report STATUS + test names + results + files changed. DO NOT commit.


## Probe question (answer in `probe_answer`, per arm)

Focus on TEST RIGOR: for each arm, would its tests FAIL on the pre-change code, do they cover negative/edge cases per new code path, and do they assert real behavior rather than trivially passing? Name the strongest and weakest test in each arm.

## Arm A diff

```diff
diff --git a/crates/bridge-a2a-inbound/src/reattach.rs b/crates/bridge-a2a-inbound/src/reattach.rs
index 3cf20ef..35b614e 100644
--- a/crates/bridge-a2a-inbound/src/reattach.rs
+++ b/crates/bridge-a2a-inbound/src/reattach.rs
@@ -38,11 +38,9 @@ impl TerminalOutcome {
 #[derive(Clone, Debug, Serialize)]
 #[serde(tag = "kind", rename_all = "snake_case")]
 pub(crate) enum FrameKind {
-    #[allow(dead_code)] // Task 7 lands before the rich sink/projection callers.
     Plan {
         entries: Vec<PlanEntry>,
     },
-    #[allow(dead_code)] // Task 7 lands before the rich sink/projection callers.
     ToolCall {
         tool_call_id: String,
         title: String,
@@ -52,7 +50,6 @@ pub(crate) enum FrameKind {
         locations: Vec<String>,
         content_preview: Option<String>,
     },
-    #[allow(dead_code)] // Task 7 lands before the rich sink/projection callers.
     ToolCallUpdate {
         tool_call_id: String,
         #[serde(skip_serializing_if = "Option::is_none")]
@@ -96,7 +93,6 @@ pub(crate) struct WorkflowProgressFrame {
     pub kind: FrameKind,
 }
 
-#[allow(dead_code)] // Task 7 lands before the rich sink/projection callers.
 pub(crate) fn frame_from_orch(
     kind: &OrchEventKind,
     phase: Phase,
diff --git a/crates/bridge-a2a-inbound/src/server.rs b/crates/bridge-a2a-inbound/src/server.rs
index 429de03..a761011 100644
--- a/crates/bridge-a2a-inbound/src/server.rs
+++ b/crates/bridge-a2a-inbound/src/server.rs
@@ -1021,11 +1021,11 @@ async fn subscribe_to_task(
             if rec.status.is_terminal() {
                 // --- Terminal-task flow (Task 8) --- read the snapshot and replay it
                 // as a FINITE SSE stream (snapshot → SnapshotComplete → Terminal → close).
-                let snap = match fold_or_typed_snapshot(&srv.task_store, &task_id).await {
-                    Ok(s) => s,
+                let folded = match fold_or_typed_snapshot(&srv.task_store, &task_id).await {
+                    Ok(f) => f,
                     Err(_) => return bridge_err_to_jsonrpc(id, &BridgeError::StoreFailure),
                 };
-                terminal_sse_response(&snap, cursor)
+                terminal_sse_response(&folded.snap, &folded.events, cursor)
             } else {
                 // --- Working-task flow (Task 9) --- subscribe-first, then snapshot,
                 // then live-tail the hub until the Terminal frame.
@@ -1048,10 +1048,11 @@ async fn subscribe_to_task(
 /// reader-trap suggesting more may come).
 fn terminal_sse_response(
     snap: &bridge_core::task_store::TaskProgressSnapshot,
+    events: &[bridge_core::orch::OrchEvent],
     cursor: Option<i64>,
 ) -> Response {
-    // Build snapshot frames (cursor-filtered, seq-ordered).
-    let mut frames = snapshot_frames(snap, cursor);
+    // Build the merged (node + folded rich) snapshot frames, cursor-filtered once.
+    let mut frames = rich_snapshot_frames(snap, events, cursor);
 
     // Append SnapshotComplete sentinel (seq = max snapshot frame seq or cut_seq).
     let sentinel_seq = frames.last().map(|f| f.seq).unwrap_or(snap.cut_seq);
@@ -1099,10 +1100,19 @@ fn terminal_sse_response(
     Sse::new(sse_stream).into_response()
 }
 
+/// The result of the ONE consistent `journal_fold_inputs` read: the node-resume
+/// snapshot (folded or typed-fallback) PLUS the raw journal events used to derive
+/// it, so callers can also fold the rich (Plan/ToolCall/ToolCallUpdate) transcript
+/// from the SAME read (PFIX-H — no second store read for the rich projection).
+struct FoldedSnapshot {
+    snap: bridge_core::task_store::TaskProgressSnapshot,
+    events: Vec<bridge_core::orch::OrchEvent>,
+}
+
 async fn fold_or_typed_snapshot(
     store: &Arc<dyn bridge_core::task_store::TaskStore>,
     task: &TaskId,
-) -> Result<bridge_core::task_store::TaskProgressSnapshot, BridgeError> {
+) -> Result<FoldedSnapshot, BridgeError> {
     let fi = store.journal_fold_inputs(task).await?;
     let is_terminal = matches!(
         fi.scalars.status,
@@ -1112,11 +1122,15 @@ async fn fold_or_typed_snapshot(
             | bridge_core::task_store::TaskRecordStatus::Interrupted
     );
     let eligible = fi.complete_from_birth && (!is_terminal || fi.scalars.terminal_seq.is_some());
-    if eligible {
-        bridge_core::task_store::fold_journal_to_snapshot(&fi.events, &fi.scalars)
+    let snap = if eligible {
+        bridge_core::task_store::fold_journal_to_snapshot(&fi.events, &fi.scalars)?
     } else {
-        store.progress_snapshot(task).await
-    }
+        store.progress_snapshot(task).await?
+    };
+    Ok(FoldedSnapshot {
+        snap,
+        events: fi.events,
+    })
 }
 
 /// Build the streaming working SSE response: subscribe to the task's live progress
@@ -1157,7 +1171,7 @@ async fn working_sse_response(
             return match srv.task_store.get(task_id).await {
                 Ok(Some(rec)) if rec.status.is_terminal() => {
                     match fold_or_typed_snapshot(&srv.task_store, task_id).await {
-                        Ok(snap) => terminal_sse_response(&snap, cursor),
+                        Ok(folded) => terminal_sse_response(&folded.snap, &folded.events, cursor),
                         Err(_) => bridge_err_to_jsonrpc(id, &BridgeError::StoreFailure),
                     }
                 }
@@ -1176,22 +1190,24 @@ async fn working_sse_response(
     // window between the snapshot cut and the start of the live tail.
     let rx = hub.subscribe();
 
-    // Read the durable snapshot.
-    let snap = match fold_or_typed_snapshot(&srv.task_store, task_id).await {
-        Ok(s) => s,
+    // Read the durable snapshot (+ the SAME journal events for the rich fold).
+    let folded = match fold_or_typed_snapshot(&srv.task_store, task_id).await {
+        Ok(f) => f,
         Err(_) => return bridge_err_to_jsonrpc(id, &BridgeError::StoreFailure),
     };
+    let snap = &folded.snap;
 
     // I5: the task finished during/just-before the snapshot read → replay the
     // terminal snapshot (do NOT rely on `rx` Closed; the runner may have published
     // its Terminal frame before we subscribed).
     if snap.status.is_terminal() {
-        return terminal_sse_response(&snap, cursor);
+        return terminal_sse_response(snap, &folded.events, cursor);
     }
 
-    // Snapshot phase: cursor-filtered, seq-ordered frames + a SnapshotComplete
-    // sentinel (seq = max snapshot frame seq, else cut_seq).
-    let mut snapshot_vec = snapshot_frames(&snap, cursor);
+    // Snapshot phase: cursor-filtered, seq-ordered frames (node + folded rich,
+    // merged by seq) + a SnapshotComplete sentinel (seq = max merged frame seq,
+    // else cut_seq).
+    let mut snapshot_vec = rich_snapshot_frames(snap, &folded.events, cursor);
     let sentinel_seq = snapshot_vec.last().map(|f| f.seq).unwrap_or(snap.cut_seq);
     snapshot_vec.push(crate::reattach::WorkflowProgressFrame {
         v: 1,
@@ -1319,6 +1335,153 @@ fn snapshot_frames(
     frames
 }
 
+/// Build the merged, seq-ordered, cursor-filtered snapshot projection: the node
+/// frames (`snapshot_frames`, byte-identical for a no-rich task) MERGED with the
+/// folded rich transcript (`fold_rich_frames`), cursor-filtered ONCE on the
+/// combined list (PFIX-H). For a no-rich task `events` carries no rich kinds, so
+/// `fold_rich_frames` returns empty and this is exactly `snapshot_frames(snap,
+/// cursor)` — the S6 node-frame byte-identity holds.
+fn rich_snapshot_frames(
+    snap: &bridge_core::task_store::TaskProgressSnapshot,
+    events: &[bridge_core::orch::OrchEvent],
+    cursor: Option<i64>,
+) -> Vec<crate::reattach::WorkflowProgressFrame> {
+    let mut frames = snapshot_frames(snap, None);
+    frames.extend(fold_rich_frames(events));
+    frames.sort_by_key(|f| f.seq);
+
+    let pass = |seq: i64| cursor.is_none_or(|k| seq > k);
+    frames.retain(|f| pass(f.seq));
+    frames
+}
+
+/// Fold the rich (Plan/ToolCall/ToolCallUpdate) events into their current-state
+/// snapshot frames, in seq order (unfiltered by cursor — the caller filters once
+/// on the merged list):
+/// - `Plan`: keep only the LATEST entry → one `FrameKind::Plan` frame at that
+///   event's seq.
+/// - `ToolCall`/`ToolCallUpdate`: fold per `tool_call_id` into a current merged
+///   state (a full `ToolCall` sets/replaces the base; an update sparsely patches
+///   whichever fields are `Some`). At the end, per id: if a base `ToolCall` was
+///   ever seen, emit ONE `FrameKind::ToolCall` (the merged current state) at the
+///   LAST-applied seq; otherwise (an orphan update with no prior base) emit a
+///   `FrameKind::ToolCallUpdate` at the last-applied seq.
+fn fold_rich_frames(
+    events: &[bridge_core::orch::OrchEvent],
+) -> Vec<crate::reattach::WorkflowProgressFrame> {
+    use bridge_core::orch::OrchEventKind;
+
+    #[derive(Default)]
+    struct ToolFold {
+        had_base: bool,
+        title: Option<String>,
+        kind: Option<String>,
+        status: Option<String>,
+        locations: Option<Vec<String>>,
+        content: Option<bridge_core::orch::ContentSummary>,
+        last_seq: i64,
+    }
+
+    let mut latest_plan: Option<(i64, Vec<bridge_core::orch::PlanEntry>)> = None;
+    let mut tool_calls: HashMap<String, ToolFold> = HashMap::new();
+
+    for event in events {
+        match &event.kind {
+            OrchEventKind::Plan { entries } => {
+                latest_plan = Some((event.seq, entries.clone()));
+            }
+            OrchEventKind::ToolCall {
+                tool_call_id,
+                title,
+                kind,
+                status,
+                locations,
+                content,
+            } => {
+                let fold = tool_calls.entry(tool_call_id.clone()).or_default();
+                fold.had_base = true;
+                fold.title = Some(title.clone());
+                fold.kind = Some(kind.clone());
+                fold.status = Some(status.clone());
+                fold.locations = Some(locations.clone());
+                fold.content = content.clone();
+                fold.last_seq = event.seq;
+            }
+            OrchEventKind::ToolCallUpdate {
+                tool_call_id,
+                title,
+                kind,
+                status,
+                locations,
+                content,
+            } => {
+                let fold = tool_calls.entry(tool_call_id.clone()).or_default();
+                if title.is_some() {
+                    fold.title = title.clone();
+                }
+                if kind.is_some() {
+                    fold.kind = kind.clone();
+                }
+                if status.is_some() {
+                    fold.status = status.clone();
+                }
+                if locations.is_some() {
+                    fold.locations = locations.clone();
+                }
+                if content.is_some() {
+                    fold.content = content.clone();
+                }
+                fold.last_seq = event.seq;
+            }
+            OrchEventKind::NodeStarted { .. }
+            | OrchEventKind::NodeFinished { .. }
+            | OrchEventKind::Terminal { .. }
+            | OrchEventKind::Progress { .. }
+            | OrchEventKind::Usage { .. } => {}
+        }
+    }
+
+    let mut frames = Vec::new();
+
+    if let Some((seq, entries)) = latest_plan {
+        let kind = OrchEventKind::Plan { entries };
+        frames.push(crate::reattach::frame_from_orch(
+            &kind,
+            crate::reattach::Phase::Snapshot,
+            seq,
+        ));
+    }
+
+    for (tool_call_id, fold) in tool_calls {
+        let kind = if fold.had_base {
+            OrchEventKind::ToolCall {
+                tool_call_id,
+                title: fold.title.unwrap_or_default(),
+                kind: fold.kind.unwrap_or_default(),
+                status: fold.status.unwrap_or_default(),
+                locations: fold.locations.unwrap_or_default(),
+                content: fold.content,
+            }
+        } else {
+            OrchEventKind::ToolCallUpdate {
+                tool_call_id,
+                title: fold.title,
+                kind: fold.kind,
+                status: fold.status,
+                locations: fold.locations,
+                content: fold.content,
+            }
+        };
+        frames.push(crate::reattach::frame_from_orch(
+            &kind,
+            crate::reattach::Phase::Snapshot,
+            fold.last_seq,
+        ));
+    }
+
+    frames
+}
+
 /// Spawn the local-backend producer for an already-resolved [`LocalDispatch`]: drive
 /// the translator on the bound backend and forward each translated event into the
 /// mpsc channel. Stops if the receiver is dropped (client disconnect).
@@ -8865,7 +9028,7 @@ mod tests {
         let typed_frames = snapshot_frames(&typed, None);
         let store_dyn: std::sync::Arc<dyn bridge_core::task_store::TaskStore> = store.clone();
         let folded = fold_or_typed_snapshot(&store_dyn, &task_id).await.unwrap();
-        let folded_frames = snapshot_frames(&folded, None);
+        let folded_frames = snapshot_frames(&folded.snap, None);
         assert_eq!(
             serialize_frames(&typed_frames),
             serialize_frames(&folded_frames)
@@ -8901,7 +9064,7 @@ mod tests {
         let typed_frames = snapshot_frames(&typed, None);
         let store_dyn: std::sync::Arc<dyn bridge_core::task_store::TaskStore> = store.clone();
         let folded = fold_or_typed_snapshot(&store_dyn, &task_id).await.unwrap();
-        let folded_frames = snapshot_frames(&folded, None);
+        let folded_frames = snapshot_frames(&folded.snap, None);
         assert_eq!(
             serialize_frames(&typed_frames),
             serialize_frames(&folded_frames)
@@ -8942,7 +9105,7 @@ mod tests {
         assert_eq!(typed_frames.len(), 1, "legacy typed checkpoint is required");
         let store_dyn: std::sync::Arc<dyn bridge_core::task_store::TaskStore> = store;
         let folded = fold_or_typed_snapshot(&store_dyn, &task_id).await.unwrap();
-        let folded_frames = snapshot_frames(&folded, None);
+        let folded_frames = snapshot_frames(&folded.snap, None);
         assert_eq!(
             serialize_frames(&typed_frames),
             serialize_frames(&folded_frames)
@@ -9032,6 +9195,87 @@ mod tests {
         );
     }
 
+    /// `(seq, kind)` tags for a merged snapshot frame list, read off the serialized
+    /// JSON's top-level `kind` discriminator (mirrors `collect_sse_wire_tuples`'s
+    /// approach, but over in-process `WorkflowProgressFrame`s rather than SSE bytes).
+    fn tags(frames: &[crate::reattach::WorkflowProgressFrame]) -> Vec<(i64, String)> {
+        frames
+            .iter()
+            .map(|f| {
+                let v = serde_json::to_value(f).unwrap();
+                (f.seq, v["kind"].as_str().unwrap().to_string())
+            })
+            .collect()
+    }
+
+    /// (S7a.2 rich golden) journal: node_started(1), tool_call(2,t1,in_progress),
+    /// tool_call_update(3,t1->completed), node_finished(4). The node start collapses
+    /// into its finish (S6 fold); the tool call folds to ONE current-state frame at
+    /// its LAST-applied seq (3, from the update) — seq-ordered ahead of the
+    /// node_finished at seq 4.
+    #[tokio::test]
+    async fn rich_snapshot_folds_toolcall_interleaved() {
+        let store = std::sync::Arc::new(bridge_core::task_store::MemoryTaskStore::new());
+        let task_id = seed_task_record(&store, "task-rich-fold").await;
+        let node = bridge_core::ids::NodeId::parse("node-a").unwrap();
+        let op = operation_id_for_task(&task_id);
+        let now = crate::workflow_sink::now_ms();
+
+        let s1 = store
+            .record_node_started(&task_id, &node, &op, now)
+            .await
+            .unwrap();
+        let s2 = store
+            .record_event_sequenced(
+                &task_id,
+                &op,
+                now,
+                bridge_core::orch::OrchEventKind::ToolCall {
+                    tool_call_id: "t1".into(),
+                    title: "Reading".into(),
+                    kind: "read".into(),
+                    status: "in_progress".into(),
+                    locations: vec![],
+                    content: None,
+                },
+            )
+            .await
+            .unwrap();
+        let s3 = store
+            .record_event_sequenced(
+                &task_id,
+                &op,
+                now,
+                bridge_core::orch::OrchEventKind::ToolCallUpdate {
+                    tool_call_id: "t1".into(),
+                    title: None,
+                    kind: None,
+                    status: Some("completed".into()),
+                    locations: None,
+                    content: None,
+                },
+            )
+            .await
+            .unwrap();
+        let s4 = store
+            .put_node_checkpoint_sequenced(&task_id, &node, &op, "out-a", true, now)
+            .await
+            .unwrap();
+        assert_eq!((s1, s2, s3, s4), (1, 2, 3, 4));
+
+        let store_dyn: std::sync::Arc<dyn bridge_core::task_store::TaskStore> = store;
+        let folded = fold_or_typed_snapshot(&store_dyn, &task_id).await.unwrap();
+        let frames = rich_snapshot_frames(&folded.snap, &folded.events, None);
+        assert_eq!(
+            tags(&frames),
+            vec![
+                (3, "tool_call".to_string()),
+                (4, "node_finished".to_string()),
+            ],
+            "expected the folded tool_call (last-applied seq 3) then node_finished (seq 4): {frames:?}"
+        );
+    }
+
     /// (8a) Terminal task with 2 checkpoints (seqs 1, 2) + terminal_seq 3, no cursor.
     /// Expected frames: [(1,"node_finished"),(2,"node_finished"),(2,"snapshot_complete"),(3,"terminal")]
     #[tokio::test]

```

## Arm B diff

```diff
diff --git a/crates/bridge-a2a-inbound/src/reattach.rs b/crates/bridge-a2a-inbound/src/reattach.rs
index 3cf20ef..35b614e 100644
--- a/crates/bridge-a2a-inbound/src/reattach.rs
+++ b/crates/bridge-a2a-inbound/src/reattach.rs
@@ -38,11 +38,9 @@ impl TerminalOutcome {
 #[derive(Clone, Debug, Serialize)]
 #[serde(tag = "kind", rename_all = "snake_case")]
 pub(crate) enum FrameKind {
-    #[allow(dead_code)] // Task 7 lands before the rich sink/projection callers.
     Plan {
         entries: Vec<PlanEntry>,
     },
-    #[allow(dead_code)] // Task 7 lands before the rich sink/projection callers.
     ToolCall {
         tool_call_id: String,
         title: String,
@@ -52,7 +50,6 @@ pub(crate) enum FrameKind {
         locations: Vec<String>,
         content_preview: Option<String>,
     },
-    #[allow(dead_code)] // Task 7 lands before the rich sink/projection callers.
     ToolCallUpdate {
         tool_call_id: String,
         #[serde(skip_serializing_if = "Option::is_none")]
@@ -96,7 +93,6 @@ pub(crate) struct WorkflowProgressFrame {
     pub kind: FrameKind,
 }
 
-#[allow(dead_code)] // Task 7 lands before the rich sink/projection callers.
 pub(crate) fn frame_from_orch(
     kind: &OrchEventKind,
     phase: Phase,
diff --git a/crates/bridge-a2a-inbound/src/server.rs b/crates/bridge-a2a-inbound/src/server.rs
index 429de03..1624a4e 100644
--- a/crates/bridge-a2a-inbound/src/server.rs
+++ b/crates/bridge-a2a-inbound/src/server.rs
@@ -1021,11 +1021,11 @@ async fn subscribe_to_task(
             if rec.status.is_terminal() {
                 // --- Terminal-task flow (Task 8) --- read the snapshot and replay it
                 // as a FINITE SSE stream (snapshot → SnapshotComplete → Terminal → close).
-                let snap = match fold_or_typed_snapshot(&srv.task_store, &task_id).await {
-                    Ok(s) => s,
+                let folded = match fold_or_typed_snapshot(&srv.task_store, &task_id).await {
+                    Ok(f) => f,
                     Err(_) => return bridge_err_to_jsonrpc(id, &BridgeError::StoreFailure),
                 };
-                terminal_sse_response(&snap, cursor)
+                terminal_sse_response(&folded.snap, &folded.events, cursor)
             } else {
                 // --- Working-task flow (Task 9) --- subscribe-first, then snapshot,
                 // then live-tail the hub until the Terminal frame.
@@ -1048,10 +1048,11 @@ async fn subscribe_to_task(
 /// reader-trap suggesting more may come).
 fn terminal_sse_response(
     snap: &bridge_core::task_store::TaskProgressSnapshot,
+    events: &[bridge_core::orch::OrchEvent],
     cursor: Option<i64>,
 ) -> Response {
-    // Build snapshot frames (cursor-filtered, seq-ordered).
-    let mut frames = snapshot_frames(snap, cursor);
+    // Build merged, cursor-filtered, seq-ordered snapshot frames (node + rich).
+    let mut frames = rich_snapshot_frames(snap, events, cursor);
 
     // Append SnapshotComplete sentinel (seq = max snapshot frame seq or cut_seq).
     let sentinel_seq = frames.last().map(|f| f.seq).unwrap_or(snap.cut_seq);
@@ -1099,10 +1100,19 @@ fn terminal_sse_response(
     Sse::new(sse_stream).into_response()
 }
 
+/// The node-resume snapshot AND the raw journal events, from the SAME
+/// `journal_fold_inputs` read (PFIX-H: one consistent read feeds both the node-frame
+/// projection (`snapshot_frames`) and the rich-fold projection
+/// (`rich_snapshot_frames`), rather than re-reading the journal separately).
+struct FoldedSnapshot {
+    snap: bridge_core::task_store::TaskProgressSnapshot,
+    events: Vec<bridge_core::orch::OrchEvent>,
+}
+
 async fn fold_or_typed_snapshot(
     store: &Arc<dyn bridge_core::task_store::TaskStore>,
     task: &TaskId,
-) -> Result<bridge_core::task_store::TaskProgressSnapshot, BridgeError> {
+) -> Result<FoldedSnapshot, BridgeError> {
     let fi = store.journal_fold_inputs(task).await?;
     let is_terminal = matches!(
         fi.scalars.status,
@@ -1112,11 +1122,15 @@ async fn fold_or_typed_snapshot(
             | bridge_core::task_store::TaskRecordStatus::Interrupted
     );
     let eligible = fi.complete_from_birth && (!is_terminal || fi.scalars.terminal_seq.is_some());
-    if eligible {
-        bridge_core::task_store::fold_journal_to_snapshot(&fi.events, &fi.scalars)
+    let snap = if eligible {
+        bridge_core::task_store::fold_journal_to_snapshot(&fi.events, &fi.scalars)?
     } else {
-        store.progress_snapshot(task).await
-    }
+        store.progress_snapshot(task).await?
+    };
+    Ok(FoldedSnapshot {
+        snap,
+        events: fi.events,
+    })
 }
 
 /// Build the streaming working SSE response: subscribe to the task's live progress
@@ -1157,7 +1171,7 @@ async fn working_sse_response(
             return match srv.task_store.get(task_id).await {
                 Ok(Some(rec)) if rec.status.is_terminal() => {
                     match fold_or_typed_snapshot(&srv.task_store, task_id).await {
-                        Ok(snap) => terminal_sse_response(&snap, cursor),
+                        Ok(folded) => terminal_sse_response(&folded.snap, &folded.events, cursor),
                         Err(_) => bridge_err_to_jsonrpc(id, &BridgeError::StoreFailure),
                     }
                 }
@@ -1177,22 +1191,25 @@ async fn working_sse_response(
     let rx = hub.subscribe();
 
     // Read the durable snapshot.
-    let snap = match fold_or_typed_snapshot(&srv.task_store, task_id).await {
-        Ok(s) => s,
+    let folded = match fold_or_typed_snapshot(&srv.task_store, task_id).await {
+        Ok(f) => f,
         Err(_) => return bridge_err_to_jsonrpc(id, &BridgeError::StoreFailure),
     };
 
     // I5: the task finished during/just-before the snapshot read → replay the
     // terminal snapshot (do NOT rely on `rx` Closed; the runner may have published
     // its Terminal frame before we subscribed).
-    if snap.status.is_terminal() {
-        return terminal_sse_response(&snap, cursor);
+    if folded.snap.status.is_terminal() {
+        return terminal_sse_response(&folded.snap, &folded.events, cursor);
     }
 
-    // Snapshot phase: cursor-filtered, seq-ordered frames + a SnapshotComplete
-    // sentinel (seq = max snapshot frame seq, else cut_seq).
-    let mut snapshot_vec = snapshot_frames(&snap, cursor);
-    let sentinel_seq = snapshot_vec.last().map(|f| f.seq).unwrap_or(snap.cut_seq);
+    // Snapshot phase: merged (node + rich), cursor-filtered, seq-ordered frames +
+    // a SnapshotComplete sentinel (seq = max snapshot frame seq, else cut_seq).
+    let mut snapshot_vec = rich_snapshot_frames(&folded.snap, &folded.events, cursor);
+    let sentinel_seq = snapshot_vec
+        .last()
+        .map(|f| f.seq)
+        .unwrap_or(folded.snap.cut_seq);
     snapshot_vec.push(crate::reattach::WorkflowProgressFrame {
         v: 1,
         seq: sentinel_seq,
@@ -1202,7 +1219,7 @@ async fn working_sse_response(
 
     // Dedup floor: a cursor-less subscriber keeps seq 0, and the snapshot↔live
     // overlap is deduped (drop live frames already covered by the snapshot cut).
-    let dedup_floor = cursor.unwrap_or(-1).max(snap.cut_seq);
+    let dedup_floor = cursor.unwrap_or(-1).max(folded.snap.cut_seq);
 
     // Build the streaming SSE body: the snapshot vec first, then the live tail from
     // `rx`. `async_stream::stream!` lets us write the imperative snapshot-then-tail
@@ -1319,6 +1336,139 @@ fn snapshot_frames(
     frames
 }
 
+/// Build the merged, seq-ordered `Vec<WorkflowProgressFrame>` for the snapshot
+/// phase: the S6 node frames (`snapshot_frames`, byte-identical for a no-rich run)
+/// merged with the folded rich frames (latest `Plan`; `ToolCall`/`ToolCallUpdate`
+/// folded per `tool_call_id` — PFIX-H), then cursor-filtered ONCE on the merged
+/// list (not twice — filtering the node frames alone would double-apply the cursor).
+fn rich_snapshot_frames(
+    snap: &bridge_core::task_store::TaskProgressSnapshot,
+    events: &[bridge_core::orch::OrchEvent],
+    cursor: Option<i64>,
+) -> Vec<crate::reattach::WorkflowProgressFrame> {
+    let pass = |seq: i64| cursor.is_none_or(|k| seq > k);
+
+    let mut frames = snapshot_frames(snap, None);
+    frames.extend(fold_rich_events(events));
+    frames.retain(|f| pass(f.seq));
+    frames.sort_by_key(|f| f.seq);
+    frames
+}
+
+/// Fold rich `OrchEvent`s (seq order) into ONE frame per logical entity: keep only
+/// the LATEST `Plan` (complete-replace); per `tool_call_id`, merge `ToolCall` (the
+/// base) and `ToolCallUpdate` (a sparse patch) into the current state, emitting ONE
+/// `ToolCall` frame at the last-applied seq if a base `ToolCall` was seen, else a
+/// `ToolCallUpdate` frame (an orphan update, no prior base) at its last-applied seq.
+fn fold_rich_events(
+    events: &[bridge_core::orch::OrchEvent],
+) -> Vec<crate::reattach::WorkflowProgressFrame> {
+    use bridge_core::orch::OrchEventKind;
+
+    #[derive(Default)]
+    struct ToolCallFold {
+        title: Option<String>,
+        kind: Option<String>,
+        status: Option<String>,
+        locations: Option<Vec<String>>,
+        content: Option<bridge_core::orch::ContentSummary>,
+        last_seq: i64,
+        had_base: bool,
+    }
+
+    let mut latest_plan: Option<(i64, Vec<bridge_core::orch::PlanEntry>)> = None;
+    let mut tool_calls: HashMap<String, ToolCallFold> = HashMap::new();
+
+    for event in events {
+        match &event.kind {
+            OrchEventKind::Plan { entries } => {
+                latest_plan = Some((event.seq, entries.clone()));
+            }
+            OrchEventKind::ToolCall {
+                tool_call_id,
+                title,
+                kind,
+                status,
+                locations,
+                content,
+            } => {
+                let fold = tool_calls.entry(tool_call_id.clone()).or_default();
+                fold.title = Some(title.clone());
+                fold.kind = Some(kind.clone());
+                fold.status = Some(status.clone());
+                fold.locations = Some(locations.clone());
+                fold.content = content.clone();
+                fold.last_seq = event.seq;
+                fold.had_base = true;
+            }
+            OrchEventKind::ToolCallUpdate {
+                tool_call_id,
+                title,
+                kind,
+                status,
+                locations,
+                content,
+            } => {
+                let fold = tool_calls.entry(tool_call_id.clone()).or_default();
+                if title.is_some() {
+                    fold.title = title.clone();
+                }
+                if kind.is_some() {
+                    fold.kind = kind.clone();
+                }
+                if status.is_some() {
+                    fold.status = status.clone();
+                }
+                if locations.is_some() {
+                    fold.locations = locations.clone();
+                }
+                if content.is_some() {
+                    fold.content = content.clone();
+                }
+                fold.last_seq = event.seq;
+            }
+            _ => {}
+        }
+    }
+
+    let mut frames = Vec::new();
+    if let Some((seq, entries)) = latest_plan {
+        frames.push(crate::reattach::frame_from_orch(
+            &OrchEventKind::Plan { entries },
+            crate::reattach::Phase::Snapshot,
+            seq,
+        ));
+    }
+    for (tool_call_id, fold) in tool_calls {
+        let seq = fold.last_seq;
+        let kind = if fold.had_base {
+            OrchEventKind::ToolCall {
+                tool_call_id,
+                title: fold.title.unwrap_or_default(),
+                kind: fold.kind.unwrap_or_default(),
+                status: fold.status.unwrap_or_default(),
+                locations: fold.locations.unwrap_or_default(),
+                content: fold.content,
+            }
+        } else {
+            OrchEventKind::ToolCallUpdate {
+                tool_call_id,
+                title: fold.title,
+                kind: fold.kind,
+                status: fold.status,
+                locations: fold.locations,
+                content: fold.content,
+            }
+        };
+        frames.push(crate::reattach::frame_from_orch(
+            &kind,
+            crate::reattach::Phase::Snapshot,
+            seq,
+        ));
+    }
+    frames
+}
+
 /// Spawn the local-backend producer for an already-resolved [`LocalDispatch`]: drive
 /// the translator on the bound backend and forward each translated event into the
 /// mpsc channel. Stops if the receiver is dropped (client disconnect).
@@ -8865,7 +9015,7 @@ mod tests {
         let typed_frames = snapshot_frames(&typed, None);
         let store_dyn: std::sync::Arc<dyn bridge_core::task_store::TaskStore> = store.clone();
         let folded = fold_or_typed_snapshot(&store_dyn, &task_id).await.unwrap();
-        let folded_frames = snapshot_frames(&folded, None);
+        let folded_frames = snapshot_frames(&folded.snap, None);
         assert_eq!(
             serialize_frames(&typed_frames),
             serialize_frames(&folded_frames)
@@ -8901,7 +9051,7 @@ mod tests {
         let typed_frames = snapshot_frames(&typed, None);
         let store_dyn: std::sync::Arc<dyn bridge_core::task_store::TaskStore> = store.clone();
         let folded = fold_or_typed_snapshot(&store_dyn, &task_id).await.unwrap();
-        let folded_frames = snapshot_frames(&folded, None);
+        let folded_frames = snapshot_frames(&folded.snap, None);
         assert_eq!(
             serialize_frames(&typed_frames),
             serialize_frames(&folded_frames)
@@ -8942,7 +9092,7 @@ mod tests {
         assert_eq!(typed_frames.len(), 1, "legacy typed checkpoint is required");
         let store_dyn: std::sync::Arc<dyn bridge_core::task_store::TaskStore> = store;
         let folded = fold_or_typed_snapshot(&store_dyn, &task_id).await.unwrap();
-        let folded_frames = snapshot_frames(&folded, None);
+        let folded_frames = snapshot_frames(&folded.snap, None);
         assert_eq!(
             serialize_frames(&typed_frames),
             serialize_frames(&folded_frames)
@@ -9032,6 +9182,417 @@ mod tests {
         );
     }
 
+    /// Extract `(seq, kind)` tags from a `Vec<WorkflowProgressFrame>` for assertions
+    /// (mirrors `collect_sse_wire_tuples`'s `kind` extraction, but over in-memory
+    /// frames rather than a serialized SSE body).
+    fn tags(frames: &[crate::reattach::WorkflowProgressFrame]) -> Vec<(i64, String)> {
+        frames
+            .iter()
+            .map(|f| {
+                let v = serde_json::to_value(f).unwrap();
+                (f.seq, v["kind"].as_str().unwrap().to_string())
+            })
+            .collect()
+    }
+
+    /// A rich run: `node_started(1)`, `tool_call(2,t1,in_progress)`,
+    /// `tool_call_update(3,t1->completed)`, `node_finished(4)`. The merged snapshot
+    /// projection collapses the node start (it finished) and folds the tool call to
+    /// its LATEST state at the last-applied seq (3), interleaved by seq with the
+    /// node_finished frame (4).
+    #[tokio::test]
+    async fn rich_snapshot_folds_toolcall_interleaved() {
+        let store = std::sync::Arc::new(bridge_core::task_store::MemoryTaskStore::new());
+        let task_id = bridge_core::ids::TaskId::parse("task-rich-fold").unwrap();
+        store
+            .create(&working_record("task-rich-fold"))
+            .await
+            .unwrap();
+        let node = bridge_core::ids::NodeId::parse("node-a").unwrap();
+        let op = operation_id_for_task(&task_id);
+        let now = crate::workflow_sink::now_ms();
+
+        let s1 = store
+            .record_node_started(&task_id, &node, &op, now)
+            .await
+            .unwrap();
+        let s2 = store
+            .record_event_sequenced(
+                &task_id,
+                &op,
+                now,
+                bridge_core::orch::OrchEventKind::ToolCall {
+                    tool_call_id: "t1".into(),
+                    title: "Reading file".into(),
+                    kind: "read".into(),
+                    status: "in_progress".into(),
+                    locations: vec![],
+                    content: None,
+                },
+            )
+            .await
+            .unwrap();
+        let s3 = store
+            .record_event_sequenced(
+                &task_id,
+                &op,
+                now,
+                bridge_core::orch::OrchEventKind::ToolCallUpdate {
+                    tool_call_id: "t1".into(),
+                    title: None,
+                    kind: None,
+                    status: Some("completed".into()),
+                    locations: None,
+                    content: None,
+                },
+            )
+            .await
+            .unwrap();
+        let s4 = store
+            .put_node_checkpoint_sequenced(&task_id, &node, &op, "out-a", true, now)
+            .await
+            .unwrap();
+        assert_eq!((s1, s2, s3, s4), (1, 2, 3, 4));
+
+        let store_dyn: std::sync::Arc<dyn bridge_core::task_store::TaskStore> = store;
+        let folded = fold_or_typed_snapshot(&store_dyn, &task_id).await.unwrap();
+        let frames = rich_snapshot_frames(&folded.snap, &folded.events, None);
+        assert_eq!(
+            tags(&frames),
+            vec![
+                (3, "tool_call".to_string()),
+                (4, "node_finished".to_string()),
+            ],
+            "the node start collapses (finished); the tool call folds to its latest \
+             state at the last-applied seq, interleaved by seq: {frames:?}"
+        );
+    }
+
+    /// A `ToolCallUpdate` with NO prior `ToolCall` for its `tool_call_id` (an orphan
+    /// update — e.g. the base landed in a journal window this snapshot doesn't cover)
+    /// must fold to a `ToolCallUpdate` frame, NOT a `ToolCall` frame, at its own seq.
+    /// This exercises the `had_base == false` branch of `fold_rich_events`, which the
+    /// interleaved-fold test above never reaches.
+    #[tokio::test]
+    async fn rich_snapshot_folds_orphan_toolcall_update() {
+        let store = std::sync::Arc::new(bridge_core::task_store::MemoryTaskStore::new());
+        let task_id = bridge_core::ids::TaskId::parse("task-rich-orphan").unwrap();
+        store
+            .create(&working_record("task-rich-orphan"))
+            .await
+            .unwrap();
+        let op = operation_id_for_task(&task_id);
+        let now = crate::workflow_sink::now_ms();
+
+        let s1 = store
+            .record_event_sequenced(
+                &task_id,
+                &op,
+                now,
+                bridge_core::orch::OrchEventKind::ToolCallUpdate {
+                    tool_call_id: "orphan-1".into(),
+                    title: None,
+                    kind: None,
+                    status: Some("completed".into()),
+                    locations: None,
+                    content: None,
+                },
+            )
+            .await
+            .unwrap();
+        assert_eq!(s1, 1);
+
+        let store_dyn: std::sync::Arc<dyn bridge_core::task_store::TaskStore> = store;
+        let folded = fold_or_typed_snapshot(&store_dyn, &task_id).await.unwrap();
+        let frames = rich_snapshot_frames(&folded.snap, &folded.events, None);
+        assert_eq!(
+            tags(&frames),
+            vec![(1, "tool_call_update".to_string())],
+            "an orphan ToolCallUpdate (no prior base) must fold to a tool_call_update \
+             frame, not tool_call: {frames:?}"
+        );
+    }
+
+    /// Two `Plan` events at different seqs: only the LATEST survives the fold
+    /// (complete-replace semantics), emitted at the latest event's own seq.
+    #[tokio::test]
+    async fn rich_snapshot_keeps_latest_plan_only() {
+        let store = std::sync::Arc::new(bridge_core::task_store::MemoryTaskStore::new());
+        let task_id = bridge_core::ids::TaskId::parse("task-rich-plan").unwrap();
+        store
+            .create(&working_record("task-rich-plan"))
+            .await
+            .unwrap();
+        let op = operation_id_for_task(&task_id);
+        let now = crate::workflow_sink::now_ms();
+
+        let s1 = store
+            .record_event_sequenced(
+                &task_id,
+                &op,
+                now,
+                bridge_core::orch::OrchEventKind::Plan {
+                    entries: vec![bridge_core::orch::PlanEntry {
+                        content: "step one".into(),
+                        priority: "high".into(),
+                        status: "pending".into(),
+                    }],
+                },
+            )
+            .await
+            .unwrap();
+        let s2 = store
+            .record_event_sequenced(
+                &task_id,
+                &op,
+                now,
+                bridge_core::orch::OrchEventKind::Plan {
+                    entries: vec![bridge_core::orch::PlanEntry {
+                        content: "step one".into(),
+                        priority: "high".into(),
+                        status: "completed".into(),
+                    }],
+                },
+            )
+            .await
+            .unwrap();
+        assert_eq!((s1, s2), (1, 2));
+
+        let store_dyn: std::sync::Arc<dyn bridge_core::task_store::TaskStore> = store;
+        let folded = fold_or_typed_snapshot(&store_dyn, &task_id).await.unwrap();
+        let frames = rich_snapshot_frames(&folded.snap, &folded.events, None);
+        assert_eq!(
+            frames.len(),
+            1,
+            "only the LATEST Plan may survive the fold: {frames:?}"
+        );
+        assert_eq!(
+            frames[0].seq, 2,
+            "the surviving Plan must be at the latest seq"
+        );
+        match &frames[0].kind {
+            crate::reattach::FrameKind::Plan { entries } => {
+                assert_eq!(entries[0].status, "completed");
+            }
+            other => panic!("expected a Plan frame, got {other:?}"),
+        }
+    }
+
+    /// A cursor must exclude a folded rich frame the same way it excludes a node
+    /// frame: reusing the interleaved-fold journal (node_started(1), tool_call(2),
+    /// tool_call_update(3->completed), node_finished(4)), `cursor=3` drops the folded
+    /// `tool_call` frame (its last-applied seq is 3, not > 3) but keeps
+    /// `node_finished` (seq 4). Guards the "cursor-filtered ONCE on the MERGED list"
+    /// invariant — a bug that filtered only the node-frame portion (or forgot to
+    /// filter rich frames at all) would leak the tool_call frame through here.
+    #[tokio::test]
+    async fn rich_snapshot_frames_cursor_excludes_covered_rich_frame() {
+        let store = std::sync::Arc::new(bridge_core::task_store::MemoryTaskStore::new());
+        let task_id = bridge_core::ids::TaskId::parse("task-rich-cursor").unwrap();
+        store
+            .create(&working_record("task-rich-cursor"))
+            .await
+            .unwrap();
+        let node = bridge_core::ids::NodeId::parse("node-a").unwrap();
+        let op = operation_id_for_task(&task_id);
+        let now = crate::workflow_sink::now_ms();
+
+        store
+            .record_node_started(&task_id, &node, &op, now)
+            .await
+            .unwrap();
+        store
+            .record_event_sequenced(
+                &task_id,
+                &op,
+                now,
+                bridge_core::orch::OrchEventKind::ToolCall {
+                    tool_call_id: "t1".into(),
+                    title: "Reading file".into(),
+                    kind: "read".into(),
+                    status: "in_progress".into(),
+                    locations: vec![],
+                    content: None,
+                },
+            )
+            .await
+            .unwrap();
+        store
+            .record_event_sequenced(
+                &task_id,
+                &op,
+                now,
+                bridge_core::orch::OrchEventKind::ToolCallUpdate {
+                    tool_call_id: "t1".into(),
+                    title: None,
+                    kind: None,
+                    status: Some("completed".into()),
+                    locations: None,
+                    content: None,
+                },
+            )
+            .await
+            .unwrap();
+        store
+            .put_node_checkpoint_sequenced(&task_id, &node, &op, "out-a", true, now)
+            .await
+            .unwrap();
+
+        let store_dyn: std::sync::Arc<dyn bridge_core::task_store::TaskStore> = store;
+        let folded = fold_or_typed_snapshot(&store_dyn, &task_id).await.unwrap();
+        let frames = rich_snapshot_frames(&folded.snap, &folded.events, Some(3));
+        assert_eq!(
+            tags(&frames),
+            vec![(4, "node_finished".to_string())],
+            "cursor=3 must exclude the folded tool_call frame (seq 3) but keep \
+             node_finished (seq 4): {frames:?}"
+        );
+    }
+
+    /// End-to-end: SUBSCRIBE_TO_TASK on a TERMINAL task whose journal has a rich
+    /// ToolCall/ToolCallUpdate interleaved with node frames. Exercises the
+    /// `terminal_sse_response` call site's wiring to `rich_snapshot_frames` — before
+    /// Task 8 this call site used bare `snapshot_frames`, which silently drops every
+    /// rich event, so this test would fail (no "tool_call" tag) on the pre-change code.
+    #[tokio::test]
+    async fn subscribe_terminal_task_includes_rich_toolcall_frame() {
+        let store = std::sync::Arc::new(bridge_core::task_store::MemoryTaskStore::new());
+        let task_id = seed_task_record(&store, "t-rich-terminal").await;
+        let node = bridge_core::ids::NodeId::parse("node-a").unwrap();
+        let op = operation_id_for_task(&task_id);
+        let now = crate::workflow_sink::now_ms();
+
+        let s1 = store
+            .record_node_started(&task_id, &node, &op, now)
+            .await
+            .unwrap();
+        let s2 = store
+            .record_event_sequenced(
+                &task_id,
+                &op,
+                now,
+                bridge_core::orch::OrchEventKind::ToolCall {
+                    tool_call_id: "t1".into(),
+                    title: "Reading file".into(),
+                    kind: "read".into(),
+                    status: "in_progress".into(),
+                    locations: vec![],
+                    content: None,
+                },
+            )
+            .await
+            .unwrap();
+        let s3 = store
+            .record_event_sequenced(
+                &task_id,
+                &op,
+                now,
+                bridge_core::orch::OrchEventKind::ToolCallUpdate {
+                    tool_call_id: "t1".into(),
+                    title: None,
+                    kind: None,
+                    status: Some("completed".into()),
+                    locations: None,
+                    content: None,
+                },
+            )
+            .await
+            .unwrap();
+        let s4 = store
+            .put_node_checkpoint_sequenced(&task_id, &node, &op, "out-a", true, now)
+            .await
+            .unwrap();
+        let s5 = store
+            .set_terminal_sequenced(
+                &task_id,
+                &op,
+                bridge_core::task_store::TaskRecordStatus::Completed,
+                Some("done"),
+                None,
+                now,
+            )
+            .await
+            .unwrap();
+        assert_eq!((s1, s2, s3, s4, s5), (1, 2, 3, 4, 5));
+
+        let srv = build_with_task_store(store);
+        let resp = call_subscribe(&srv, "t-rich-terminal", None).await;
+        assert_eq!(resp.status(), StatusCode::OK);
+        let frames = collect_sse_frames(resp).await;
+        assert_eq!(
+            frames,
+            vec![
+                (3, "tool_call".to_string()),
+                (4, "node_finished".to_string()),
+                (4, "snapshot_complete".to_string()),
+                (5, "terminal".to_string()),
+            ],
+            "terminal-task reattach must surface the folded rich tool_call frame: {frames:?}"
+        );
+    }
+
+    /// End-to-end: SUBSCRIBE_TO_TASK on a WORKING task (hub registered, snapshot
+    /// phase read before the live tail) whose durable journal already has a rich
+    /// `ToolCall` (no update — the base-only fold branch) interleaved with a node
+    /// checkpoint. Exercises the `working_sse_response` call site's wiring to
+    /// `rich_snapshot_frames` — before Task 8 this call site used bare
+    /// `snapshot_frames` on the snapshot phase, which silently dropped the rich
+    /// event, so this test would fail (no "tool_call" tag) on the pre-change code.
+    #[tokio::test]
+    async fn subscribe_working_snapshot_includes_rich_toolcall_frame() {
+        let store = std::sync::Arc::new(bridge_core::task_store::MemoryTaskStore::new());
+        let task_id = seed_task_record(&store, "t-rich-working").await;
+        let node = bridge_core::ids::NodeId::parse("node-a").unwrap();
+        let op = operation_id_for_task(&task_id);
+        let now = crate::workflow_sink::now_ms();
+
+        let s1 = store
+            .record_node_started(&task_id, &node, &op, now)
+            .await
+            .unwrap();
+        let s2 = store
+            .record_event_sequenced(
+                &task_id,
+                &op,
+                now,
+                bridge_core::orch::OrchEventKind::ToolCall {
+                    tool_call_id: "t1".into(),
+                    title: "Reading file".into(),
+                    kind: "read".into(),
+                    status: "in_progress".into(),
+                    locations: vec![],
+                    content: None,
+                },
+            )
+            .await
+            .unwrap();
+        let s3 = store
+            .put_node_checkpoint_sequenced(&task_id, &node, &op, "out-a", true, now)
+            .await
+            .unwrap();
+        assert_eq!((s1, s2, s3), (1, 2, 3));
+
+        let srv = build_with_task_store(store);
+        let hub = insert_hub(&srv, &task_id).await;
+        let resp = call_subscribe(&srv, "t-rich-working", None).await;
+        assert_eq!(resp.status(), StatusCode::OK);
+        // End the stream so the collected body is finite.
+        hub.publish(live_terminal(4));
+
+        let frames = collect_sse_frames(resp).await;
+        assert_eq!(
+            frames,
+            vec![
+                (2, "tool_call".to_string()),
+                (3, "node_finished".to_string()),
+                (3, "snapshot_complete".to_string()),
+                (4, "terminal".to_string()),
+            ],
+            "working-task reattach snapshot phase must surface the folded rich \
+             tool_call frame: {frames:?}"
+        );
+    }
+
     /// (8a) Terminal task with 2 checkpoints (seqs 1, 2) + terminal_seq 3, no cursor.
     /// Expected frames: [(1,"node_finished"),(2,"node_finished"),(2,"snapshot_complete"),(3,"terminal")]
     #[tokio::test]

```
