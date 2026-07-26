# Blind pairwise code-review judgment — task IMPL-06

Two different engineers (Arm A, Arm B) independently completed the SAME task
from the same starting commit. You see the task brief and both final diffs.
You do NOT know who the engineers are; judge only the work. Both arms passed
the repo's build and the task's mechanical test evidence (suite green in both cases).

Answer the JSON schema exactly. Binary verdicts: `a_materially_better` /
`b_materially_better` may not both be true; both false = parity. "Materially
better" = a reviewer would insist the other arm adopt the difference
(correctness, safety, coverage of the specified requirements) — NOT style.

## Task brief (verbatim, both arms received this)

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

Is the reattach snapshot merge byte-identical on the golden path (no reordering/duplication of folded toolcall events)?

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
index 429de03..6f95d44 100644
--- a/crates/bridge-a2a-inbound/src/server.rs
+++ b/crates/bridge-a2a-inbound/src/server.rs
@@ -1021,11 +1021,11 @@ async fn subscribe_to_task(
             if rec.status.is_terminal() {
                 // --- Terminal-task flow (Task 8) --- read the snapshot and replay it
                 // as a FINITE SSE stream (snapshot → SnapshotComplete → Terminal → close).
-                let snap = match fold_or_typed_snapshot(&srv.task_store, &task_id).await {
+                let folded = match fold_or_typed_snapshot(&srv.task_store, &task_id).await {
                     Ok(s) => s,
                     Err(_) => return bridge_err_to_jsonrpc(id, &BridgeError::StoreFailure),
                 };
-                terminal_sse_response(&snap, cursor)
+                terminal_sse_response(&folded.snap, &folded.events, cursor)
             } else {
                 // --- Working-task flow (Task 9) --- subscribe-first, then snapshot,
                 // then live-tail the hub until the Terminal frame.
@@ -1048,12 +1048,13 @@ async fn subscribe_to_task(
 /// reader-trap suggesting more may come).
 fn terminal_sse_response(
     snap: &bridge_core::task_store::TaskProgressSnapshot,
+    events: &[bridge_core::orch::OrchEvent],
     cursor: Option<i64>,
 ) -> Response {
-    // Build snapshot frames (cursor-filtered, seq-ordered).
-    let mut frames = snapshot_frames(snap, cursor);
+    // Build the merged node+rich snapshot frames (cursor-filtered, seq-ordered).
+    let mut frames = rich_snapshot_frames(snap, events, cursor);
 
-    // Append SnapshotComplete sentinel (seq = max snapshot frame seq or cut_seq).
+    // Append SnapshotComplete sentinel (seq = max MERGED frame seq or cut_seq).
     let sentinel_seq = frames.last().map(|f| f.seq).unwrap_or(snap.cut_seq);
     frames.push(crate::reattach::WorkflowProgressFrame {
         v: 1,
@@ -1099,10 +1100,18 @@ fn terminal_sse_response(
     Sse::new(sse_stream).into_response()
 }
 
+/// One consistent reattach read: the node-only snapshot plus the raw journal
+/// events the rich projection folds over (both from the SAME `journal_fold_inputs`
+/// read, so the rich frames can never run ahead of the node frames).
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
@@ -1112,11 +1121,15 @@ async fn fold_or_typed_snapshot(
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
@@ -1157,7 +1170,7 @@ async fn working_sse_response(
             return match srv.task_store.get(task_id).await {
                 Ok(Some(rec)) if rec.status.is_terminal() => {
                     match fold_or_typed_snapshot(&srv.task_store, task_id).await {
-                        Ok(snap) => terminal_sse_response(&snap, cursor),
+                        Ok(folded) => terminal_sse_response(&folded.snap, &folded.events, cursor),
                         Err(_) => bridge_err_to_jsonrpc(id, &BridgeError::StoreFailure),
                     }
                 }
@@ -1177,21 +1190,22 @@ async fn working_sse_response(
     let rx = hub.subscribe();
 
     // Read the durable snapshot.
-    let snap = match fold_or_typed_snapshot(&srv.task_store, task_id).await {
-        Ok(s) => s,
-        Err(_) => return bridge_err_to_jsonrpc(id, &BridgeError::StoreFailure),
-    };
+    let FoldedSnapshot { snap, events } =
+        match fold_or_typed_snapshot(&srv.task_store, task_id).await {
+            Ok(s) => s,
+            Err(_) => return bridge_err_to_jsonrpc(id, &BridgeError::StoreFailure),
+        };
 
     // I5: the task finished during/just-before the snapshot read → replay the
     // terminal snapshot (do NOT rely on `rx` Closed; the runner may have published
     // its Terminal frame before we subscribed).
     if snap.status.is_terminal() {
-        return terminal_sse_response(&snap, cursor);
+        return terminal_sse_response(&snap, &events, cursor);
     }
 
-    // Snapshot phase: cursor-filtered, seq-ordered frames + a SnapshotComplete
-    // sentinel (seq = max snapshot frame seq, else cut_seq).
-    let mut snapshot_vec = snapshot_frames(&snap, cursor);
+    // Snapshot phase: cursor-filtered, seq-ordered merged node+rich frames + a
+    // SnapshotComplete sentinel (seq = max merged frame seq, else cut_seq).
+    let mut snapshot_vec = rich_snapshot_frames(&snap, &events, cursor);
     let sentinel_seq = snapshot_vec.last().map(|f| f.seq).unwrap_or(snap.cut_seq);
     snapshot_vec.push(crate::reattach::WorkflowProgressFrame {
         v: 1,
@@ -1319,6 +1333,151 @@ fn snapshot_frames(
     frames
 }
 
+/// The merged snapshot projection: the S6 node frames interleaved (by seq) with the
+/// rich transcript folded from the journal events, cursor-filtered ONCE on the
+/// merged list.
+///
+/// The rich fold (events walked in seq order):
+/// - `Plan`: complete-replace semantics — only the LATEST plan survives, at its seq.
+/// - `ToolCall`/`ToolCallUpdate`, per `tool_call_id`: a `ToolCall` sets/replaces the
+///   base; a `ToolCallUpdate` patches the current state's PRESENT fields (sparse:
+///   `Some` replaces, including `Some(empty)`; `None` leaves the field). One frame
+///   per id: the merged `ToolCall` at the LAST-applied seq when a base exists, else
+///   the merged `ToolCallUpdate` (orphan — no prior base) at its seq.
+///
+/// A no-rich journal folds to zero rich frames, so the merged list is byte-identical
+/// to `snapshot_frames` (the S6 wire contract).
+fn rich_snapshot_frames(
+    snap: &bridge_core::task_store::TaskProgressSnapshot,
+    events: &[bridge_core::orch::OrchEvent],
+    cursor: Option<i64>,
+) -> Vec<crate::reattach::WorkflowProgressFrame> {
+    use bridge_core::orch::OrchEventKind;
+
+    let mut frames = snapshot_frames(snap, None);
+
+    let mut latest_plan: Option<(i64, Vec<bridge_core::orch::PlanEntry>)> = None;
+    // tool_call_id -> (merged state: ToolCall base or ToolCallUpdate orphan, last-applied seq)
+    let mut tool_calls: HashMap<String, (OrchEventKind, i64)> = HashMap::new();
+    for event in events {
+        match &event.kind {
+            OrchEventKind::Plan { entries } => {
+                latest_plan = Some((event.seq, entries.clone()));
+            }
+            OrchEventKind::ToolCall { tool_call_id, .. } => {
+                tool_calls.insert(tool_call_id.clone(), (event.kind.clone(), event.seq));
+            }
+            OrchEventKind::ToolCallUpdate { tool_call_id, .. } => {
+                match tool_calls.get_mut(tool_call_id) {
+                    Some((state, last_seq)) => {
+                        patch_tool_call_state(state, &event.kind);
+                        *last_seq = event.seq;
+                    }
+                    // Orphan update (no prior base): carry the merged sparse patch.
+                    None => {
+                        tool_calls.insert(tool_call_id.clone(), (event.kind.clone(), event.seq));
+                    }
+                }
+            }
+            _ => {}
+        }
+    }
+
+    if let Some((seq, entries)) = latest_plan {
+        frames.push(crate::reattach::frame_from_orch(
+            &OrchEventKind::Plan { entries },
+            crate::reattach::Phase::Snapshot,
+            seq,
+        ));
+    }
+    for (state, last_seq) in tool_calls.into_values() {
+        frames.push(crate::reattach::frame_from_orch(
+            &state,
+            crate::reattach::Phase::Snapshot,
+            last_seq,
+        ));
+    }
+
+    // Merge seq-sorted (every journal seq is unique per task), THEN cursor-filter once.
+    frames.sort_by_key(|f| f.seq);
+    if let Some(k) = cursor {
+        frames.retain(|f| f.seq > k);
+    }
+    frames
+}
+
+/// Apply a sparse `ToolCallUpdate` patch onto the current per-id state (a `ToolCall`
+/// base or an orphan `ToolCallUpdate`): `Some` replaces the field (including
+/// `Some(empty)`), `None` leaves it untouched.
+fn patch_tool_call_state(
+    state: &mut bridge_core::orch::OrchEventKind,
+    update: &bridge_core::orch::OrchEventKind,
+) {
+    use bridge_core::orch::OrchEventKind;
+    let OrchEventKind::ToolCallUpdate {
+        title: u_title,
+        kind: u_kind,
+        status: u_status,
+        locations: u_locations,
+        content: u_content,
+        ..
+    } = update
+    else {
+        return;
+    };
+    match state {
+        OrchEventKind::ToolCall {
+            title,
+            kind,
+            status,
+            locations,
+            content,
+            ..
+        } => {
+            if let Some(t) = u_title {
+                *title = t.clone();
+            }
+            if let Some(k) = u_kind {
+                *kind = k.clone();
+            }
+            if let Some(s) = u_status {
+                *status = s.clone();
+            }
+            if let Some(l) = u_locations {
+                *locations = l.clone();
+            }
+            if u_content.is_some() {
+                *content = u_content.clone();
+            }
+        }
+        OrchEventKind::ToolCallUpdate {
+            title,
+            kind,
+            status,
+            locations,
+            content,
+            ..
+        } => {
+            if u_title.is_some() {
+                *title = u_title.clone();
+            }
+            if u_kind.is_some() {
+                *kind = u_kind.clone();
+            }
+            if u_status.is_some() {
+                *status = u_status.clone();
+            }
+            if u_locations.is_some() {
+                *locations = u_locations.clone();
+            }
+            if u_content.is_some() {
+                *content = u_content.clone();
+            }
+        }
+        _ => {}
+    }
+}
+
 /// Spawn the local-backend producer for an already-resolved [`LocalDispatch`]: drive
 /// the translator on the bound backend and forward each translated event into the
 /// mpsc channel. Stops if the receiver is dropped (client disconnect).
@@ -8865,7 +9024,7 @@ mod tests {
         let typed_frames = snapshot_frames(&typed, None);
         let store_dyn: std::sync::Arc<dyn bridge_core::task_store::TaskStore> = store.clone();
         let folded = fold_or_typed_snapshot(&store_dyn, &task_id).await.unwrap();
-        let folded_frames = snapshot_frames(&folded, None);
+        let folded_frames = snapshot_frames(&folded.snap, None);
         assert_eq!(
             serialize_frames(&typed_frames),
             serialize_frames(&folded_frames)
@@ -8901,7 +9060,7 @@ mod tests {
         let typed_frames = snapshot_frames(&typed, None);
         let store_dyn: std::sync::Arc<dyn bridge_core::task_store::TaskStore> = store.clone();
         let folded = fold_or_typed_snapshot(&store_dyn, &task_id).await.unwrap();
-        let folded_frames = snapshot_frames(&folded, None);
+        let folded_frames = snapshot_frames(&folded.snap, None);
         assert_eq!(
             serialize_frames(&typed_frames),
             serialize_frames(&folded_frames)
@@ -8942,7 +9101,7 @@ mod tests {
         assert_eq!(typed_frames.len(), 1, "legacy typed checkpoint is required");
         let store_dyn: std::sync::Arc<dyn bridge_core::task_store::TaskStore> = store;
         let folded = fold_or_typed_snapshot(&store_dyn, &task_id).await.unwrap();
-        let folded_frames = snapshot_frames(&folded, None);
+        let folded_frames = snapshot_frames(&folded.snap, None);
         assert_eq!(
             serialize_frames(&typed_frames),
             serialize_frames(&folded_frames)
@@ -9032,6 +9191,190 @@ mod tests {
         );
     }
 
+    /// `(seq, kind-tag)` pairs from the wire JSON — the merged-projection assertion shape.
+    fn frame_tags(frames: &[crate::reattach::WorkflowProgressFrame]) -> Vec<(i64, String)> {
+        frames
+            .iter()
+            .map(|f| {
+                let v: serde_json::Value = serde_json::to_value(f).unwrap();
+                (f.seq, v["kind"].as_str().unwrap_or_default().to_string())
+            })
+            .collect()
+    }
+
+    #[tokio::test]
+    async fn rich_snapshot_folds_toolcall_interleaved() {
+        let store = std::sync::Arc::new(bridge_core::task_store::MemoryTaskStore::new());
+        let task_id = bridge_core::ids::TaskId::parse("task-rich-golden").unwrap();
+        store
+            .create(&working_record("task-rich-golden"))
+            .await
+            .unwrap();
+        let node = bridge_core::ids::NodeId::parse("a").unwrap();
+        let op = operation_id_for_task(&task_id);
+        let now = crate::workflow_sink::now_ms();
+
+        // journal: node_started(1), tool_call(2,t1,in_progress), tool_call_update(3,t1->completed),
+        // node_finished(4)
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
+                    title: "read file".into(),
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
+        let fi = store.journal_fold_inputs(&task_id).await.unwrap();
+        let snap =
+            bridge_core::task_store::fold_journal_to_snapshot(&fi.events, &fi.scalars).unwrap();
+
+        // expect (seq, tag) ordered: (3,"tool_call" folded current=completed), (4,"node_finished")
+        // [start collapsed]
+        let frames = rich_snapshot_frames(&snap, &fi.events, None);
+        assert_eq!(
+            frame_tags(&frames),
+            vec![
+                (3, "tool_call".to_string()),
+                (4, "node_finished".to_string())
+            ]
+        );
+        // the folded tool_call carries the CURRENT (patched) state: base fields kept,
+        // the update's status applied.
+        let v: serde_json::Value = serde_json::to_value(&frames[0]).unwrap();
+        assert_eq!(v["tool_call_id"], "t1");
+        assert_eq!(v["title"], "read file");
+        assert_eq!(v["tool_kind"], "read");
+        assert_eq!(v["status"], "completed");
+    }
+
+    #[tokio::test]
+    async fn rich_snapshot_plan_latest_orphan_update_and_cursor() {
+        let store = std::sync::Arc::new(bridge_core::task_store::MemoryTaskStore::new());
+        let task_id = bridge_core::ids::TaskId::parse("task-rich-plan").unwrap();
+        store
+            .create(&working_record("task-rich-plan"))
+            .await
+            .unwrap();
+        let node = bridge_core::ids::NodeId::parse("a").unwrap();
+        let op = operation_id_for_task(&task_id);
+        let now = crate::workflow_sink::now_ms();
+
+        // journal: plan(1), plan(2, replaces), tool_call_update(3, ORPHAN t9),
+        // node_started(4), node_finished(5)
+        let entry = |content: &str| bridge_core::orch::PlanEntry {
+            content: content.into(),
+            priority: "medium".into(),
+            status: "pending".into(),
+        };
+        store
+            .record_event_sequenced(
+                &task_id,
+                &op,
+                now,
+                bridge_core::orch::OrchEventKind::Plan {
+                    entries: vec![entry("old")],
+                },
+            )
+            .await
+            .unwrap();
+        store
+            .record_event_sequenced(
+                &task_id,
+                &op,
+                now,
+                bridge_core::orch::OrchEventKind::Plan {
+                    entries: vec![entry("new")],
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
+                    tool_call_id: "t9".into(),
+                    title: None,
+                    kind: None,
+                    status: Some("failed".into()),
+                    locations: None,
+                    content: None,
+                },
+            )
+            .await
+            .unwrap();
+        store
+            .record_node_started(&task_id, &node, &op, now)
+            .await
+            .unwrap();
+        store
+            .put_node_checkpoint_sequenced(&task_id, &node, &op, "out-a", true, now)
+            .await
+            .unwrap();
+
+        let fi = store.journal_fold_inputs(&task_id).await.unwrap();
+        let snap =
+            bridge_core::task_store::fold_journal_to_snapshot(&fi.events, &fi.scalars).unwrap();
+
+        // No cursor: LATEST plan only (seq 2), the orphan update at ITS seq (3), node@5.
+        let frames = rich_snapshot_frames(&snap, &fi.events, None);
+        assert_eq!(
+            frame_tags(&frames),
+            vec![
+                (2, "plan".to_string()),
+                (3, "tool_call_update".to_string()),
+                (5, "node_finished".to_string()),
+            ]
+        );
+        let plan_json: serde_json::Value = serde_json::to_value(&frames[0]).unwrap();
+        assert_eq!(plan_json["entries"][0]["content"], "new");
+
+        // Cursor applied ONCE on the MERGED list: seq > 2 drops the plan frame too.
+        let frames = rich_snapshot_frames(&snap, &fi.events, Some(2));
+        assert_eq!(
+            frame_tags(&frames),
+            vec![
+                (3, "tool_call_update".to_string()),
+                (5, "node_finished".to_string()),
+            ]
+        );
+    }
+
     /// (8a) Terminal task with 2 checkpoints (seqs 1, 2) + terminal_seq 3, no cursor.
     /// Expected frames: [(1,"node_finished"),(2,"node_finished"),(2,"snapshot_complete"),(3,"terminal")]
     #[tokio::test]

```

## Arm B diff

```diff
diff --git a/crates/bridge-a2a-inbound/src/server.rs b/crates/bridge-a2a-inbound/src/server.rs
index 429de03..65d444e 100644
--- a/crates/bridge-a2a-inbound/src/server.rs
+++ b/crates/bridge-a2a-inbound/src/server.rs
@@ -1021,11 +1021,11 @@ async fn subscribe_to_task(
             if rec.status.is_terminal() {
                 // --- Terminal-task flow (Task 8) --- read the snapshot and replay it
                 // as a FINITE SSE stream (snapshot → SnapshotComplete → Terminal → close).
-                let snap = match fold_or_typed_snapshot(&srv.task_store, &task_id).await {
+                let snapshot = match fold_or_typed_snapshot(&srv.task_store, &task_id).await {
                     Ok(s) => s,
                     Err(_) => return bridge_err_to_jsonrpc(id, &BridgeError::StoreFailure),
                 };
-                terminal_sse_response(&snap, cursor)
+                terminal_sse_response(&snapshot, cursor)
             } else {
                 // --- Working-task flow (Task 9) --- subscribe-first, then snapshot,
                 // then live-tail the hub until the Terminal frame.
@@ -1046,12 +1046,10 @@ async fn subscribe_to_task(
 /// (the post-subscribe snapshot read sees a terminal status). A terminal stream is
 /// FINITE — it ends after the Terminal frame, so NO keep-alive (which would be a
 /// reader-trap suggesting more may come).
-fn terminal_sse_response(
-    snap: &bridge_core::task_store::TaskProgressSnapshot,
-    cursor: Option<i64>,
-) -> Response {
+fn terminal_sse_response(snapshot: &FoldedProgressSnapshot, cursor: Option<i64>) -> Response {
+    let snap = &snapshot.snap;
     // Build snapshot frames (cursor-filtered, seq-ordered).
-    let mut frames = snapshot_frames(snap, cursor);
+    let mut frames = rich_snapshot_frames(snap, &snapshot.events, cursor);
 
     // Append SnapshotComplete sentinel (seq = max snapshot frame seq or cut_seq).
     let sentinel_seq = frames.last().map(|f| f.seq).unwrap_or(snap.cut_seq);
@@ -1099,10 +1097,15 @@ fn terminal_sse_response(
     Sse::new(sse_stream).into_response()
 }
 
+struct FoldedProgressSnapshot {
+    snap: bridge_core::task_store::TaskProgressSnapshot,
+    events: Vec<bridge_core::orch::OrchEvent>,
+}
+
 async fn fold_or_typed_snapshot(
     store: &Arc<dyn bridge_core::task_store::TaskStore>,
     task: &TaskId,
-) -> Result<bridge_core::task_store::TaskProgressSnapshot, BridgeError> {
+) -> Result<FoldedProgressSnapshot, BridgeError> {
     let fi = store.journal_fold_inputs(task).await?;
     let is_terminal = matches!(
         fi.scalars.status,
@@ -1112,11 +1115,15 @@ async fn fold_or_typed_snapshot(
             | bridge_core::task_store::TaskRecordStatus::Interrupted
     );
     let eligible = fi.complete_from_birth && (!is_terminal || fi.scalars.terminal_seq.is_some());
-    if eligible {
+    let snap = if eligible {
         bridge_core::task_store::fold_journal_to_snapshot(&fi.events, &fi.scalars)
     } else {
         store.progress_snapshot(task).await
-    }
+    }?;
+    Ok(FoldedProgressSnapshot {
+        snap,
+        events: fi.events,
+    })
 }
 
 /// Build the streaming working SSE response: subscribe to the task's live progress
@@ -1157,7 +1164,7 @@ async fn working_sse_response(
             return match srv.task_store.get(task_id).await {
                 Ok(Some(rec)) if rec.status.is_terminal() => {
                     match fold_or_typed_snapshot(&srv.task_store, task_id).await {
-                        Ok(snap) => terminal_sse_response(&snap, cursor),
+                        Ok(snapshot) => terminal_sse_response(&snapshot, cursor),
                         Err(_) => bridge_err_to_jsonrpc(id, &BridgeError::StoreFailure),
                     }
                 }
@@ -1177,21 +1184,22 @@ async fn working_sse_response(
     let rx = hub.subscribe();
 
     // Read the durable snapshot.
-    let snap = match fold_or_typed_snapshot(&srv.task_store, task_id).await {
+    let snapshot = match fold_or_typed_snapshot(&srv.task_store, task_id).await {
         Ok(s) => s,
         Err(_) => return bridge_err_to_jsonrpc(id, &BridgeError::StoreFailure),
     };
+    let snap = &snapshot.snap;
 
     // I5: the task finished during/just-before the snapshot read → replay the
     // terminal snapshot (do NOT rely on `rx` Closed; the runner may have published
     // its Terminal frame before we subscribed).
     if snap.status.is_terminal() {
-        return terminal_sse_response(&snap, cursor);
+        return terminal_sse_response(&snapshot, cursor);
     }
 
     // Snapshot phase: cursor-filtered, seq-ordered frames + a SnapshotComplete
     // sentinel (seq = max snapshot frame seq, else cut_seq).
-    let mut snapshot_vec = snapshot_frames(&snap, cursor);
+    let mut snapshot_vec = rich_snapshot_frames(snap, &snapshot.events, cursor);
     let sentinel_seq = snapshot_vec.last().map(|f| f.seq).unwrap_or(snap.cut_seq);
     snapshot_vec.push(crate::reattach::WorkflowProgressFrame {
         v: 1,
@@ -1319,6 +1327,159 @@ fn snapshot_frames(
     frames
 }
 
+#[derive(Clone)]
+struct ToolCallBase {
+    tool_call_id: String,
+    title: String,
+    kind: String,
+    status: String,
+    locations: Vec<String>,
+    content: Option<bridge_core::orch::ContentSummary>,
+}
+
+#[derive(Clone, Default)]
+struct ToolCallPatch {
+    tool_call_id: String,
+    title: Option<String>,
+    kind: Option<String>,
+    status: Option<String>,
+    locations: Option<Vec<String>>,
+    content: Option<bridge_core::orch::ContentSummary>,
+}
+
+#[derive(Default)]
+struct ToolCallFold {
+    base: Option<ToolCallBase>,
+    patch: ToolCallPatch,
+    last_seq: i64,
+}
+
+/// Build the ordered, cursor-filtered snapshot phase including folded rich ACP rows.
+///
+/// Node frames come from the existing S6 projection unchanged. Rich rows are folded
+/// over the durable journal in seq order, merged with node frames, and only then
+/// filtered by the cursor so the reattach snapshot has one consistent ordering.
+fn rich_snapshot_frames(
+    snap: &bridge_core::task_store::TaskProgressSnapshot,
+    events: &[bridge_core::orch::OrchEvent],
+    cursor: Option<i64>,
+) -> Vec<crate::reattach::WorkflowProgressFrame> {
+    let mut frames = snapshot_frames(snap, None);
+    let mut latest_plan = None;
+    let mut tool_calls = std::collections::HashMap::<String, ToolCallFold>::new();
+
+    for event in events {
+        match &event.kind {
+            bridge_core::orch::OrchEventKind::Plan { .. } => {
+                latest_plan = Some(crate::reattach::frame_from_orch(
+                    &event.kind,
+                    crate::reattach::Phase::Snapshot,
+                    event.seq,
+                ));
+            }
+            bridge_core::orch::OrchEventKind::ToolCall {
+                tool_call_id,
+                title,
+                kind,
+                status,
+                locations,
+                content,
+            } => {
+                let entry = tool_calls.entry(tool_call_id.clone()).or_default();
+                entry.base = Some(ToolCallBase {
+                    tool_call_id: tool_call_id.clone(),
+                    title: title.clone(),
+                    kind: kind.clone(),
+                    status: status.clone(),
+                    locations: locations.clone(),
+                    content: content.clone(),
+                });
+                entry.patch = ToolCallPatch::default();
+                entry.last_seq = event.seq;
+            }
+            bridge_core::orch::OrchEventKind::ToolCallUpdate {
+                tool_call_id,
+                title,
+                kind,
+                status,
+                locations,
+                content,
+            } => {
+                let entry = tool_calls.entry(tool_call_id.clone()).or_default();
+                if let Some(base) = entry.base.as_mut() {
+                    if let Some(title) = title {
+                        base.title = title.clone();
+                    }
+                    if let Some(kind) = kind {
+                        base.kind = kind.clone();
+                    }
+                    if let Some(status) = status {
+                        base.status = status.clone();
+                    }
+                    if let Some(locations) = locations {
+                        base.locations = locations.clone();
+                    }
+                    if let Some(content) = content {
+                        base.content = Some(content.clone());
+                    }
+                } else {
+                    entry.patch.tool_call_id = tool_call_id.clone();
+                    if let Some(title) = title {
+                        entry.patch.title = Some(title.clone());
+                    }
+                    if let Some(kind) = kind {
+                        entry.patch.kind = Some(kind.clone());
+                    }
+                    if let Some(status) = status {
+                        entry.patch.status = Some(status.clone());
+                    }
+                    if let Some(locations) = locations {
+                        entry.patch.locations = Some(locations.clone());
+                    }
+                    if let Some(content) = content {
+                        entry.patch.content = Some(content.clone());
+                    }
+                }
+                entry.last_seq = event.seq;
+            }
+            _ => {}
+        }
+    }
+
+    if let Some(frame) = latest_plan {
+        frames.push(frame);
+    }
+
+    frames.extend(tool_calls.into_values().map(|tool| {
+        let kind = if let Some(base) = tool.base {
+            bridge_core::orch::OrchEventKind::ToolCall {
+                tool_call_id: base.tool_call_id,
+                title: base.title,
+                kind: base.kind,
+                status: base.status,
+                locations: base.locations,
+                content: base.content,
+            }
+        } else {
+            bridge_core::orch::OrchEventKind::ToolCallUpdate {
+                tool_call_id: tool.patch.tool_call_id,
+                title: tool.patch.title,
+                kind: tool.patch.kind,
+                status: tool.patch.status,
+                locations: tool.patch.locations,
+                content: tool.patch.content,
+            }
+        };
+        crate::reattach::frame_from_orch(&kind, crate::reattach::Phase::Snapshot, tool.last_seq)
+    }));
+
+    frames.sort_by_key(|frame| frame.seq);
+    frames
+        .into_iter()
+        .filter(|frame| cursor.is_none_or(|k| frame.seq > k))
+        .collect()
+}
+
 /// Spawn the local-backend producer for an already-resolved [`LocalDispatch`]: drive
 /// the translator on the bound backend and forward each translated event into the
 /// mpsc channel. Stops if the receiver is dropped (client disconnect).
@@ -8673,6 +8834,23 @@ mod tests {
             .collect()
     }
 
+    fn snapshot_tags(frames: &[crate::reattach::WorkflowProgressFrame]) -> Vec<(i64, String)> {
+        frames
+            .iter()
+            .map(|frame| {
+                let value = serde_json::to_value(frame).unwrap();
+                (
+                    frame.seq,
+                    value
+                        .get("kind")
+                        .and_then(|kind| kind.as_str())
+                        .unwrap()
+                        .to_string(),
+                )
+            })
+            .collect()
+    }
+
     struct LegacyFallbackStore {
         inner: std::sync::Arc<bridge_core::task_store::MemoryTaskStore>,
     }
@@ -8865,7 +9043,7 @@ mod tests {
         let typed_frames = snapshot_frames(&typed, None);
         let store_dyn: std::sync::Arc<dyn bridge_core::task_store::TaskStore> = store.clone();
         let folded = fold_or_typed_snapshot(&store_dyn, &task_id).await.unwrap();
-        let folded_frames = snapshot_frames(&folded, None);
+        let folded_frames = snapshot_frames(&folded.snap, None);
         assert_eq!(
             serialize_frames(&typed_frames),
             serialize_frames(&folded_frames)
@@ -8901,7 +9079,7 @@ mod tests {
         let typed_frames = snapshot_frames(&typed, None);
         let store_dyn: std::sync::Arc<dyn bridge_core::task_store::TaskStore> = store.clone();
         let folded = fold_or_typed_snapshot(&store_dyn, &task_id).await.unwrap();
-        let folded_frames = snapshot_frames(&folded, None);
+        let folded_frames = snapshot_frames(&folded.snap, None);
         assert_eq!(
             serialize_frames(&typed_frames),
             serialize_frames(&folded_frames)
@@ -8942,7 +9120,7 @@ mod tests {
         assert_eq!(typed_frames.len(), 1, "legacy typed checkpoint is required");
         let store_dyn: std::sync::Arc<dyn bridge_core::task_store::TaskStore> = store;
         let folded = fold_or_typed_snapshot(&store_dyn, &task_id).await.unwrap();
-        let folded_frames = snapshot_frames(&folded, None);
+        let folded_frames = snapshot_frames(&folded.snap, None);
         assert_eq!(
             serialize_frames(&typed_frames),
             serialize_frames(&folded_frames)
@@ -9032,6 +9210,82 @@ mod tests {
         );
     }
 
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
+                    tool_call_id: "t1".to_string(),
+                    title: "Read file".to_string(),
+                    kind: "read".to_string(),
+                    status: "in_progress".to_string(),
+                    locations: vec!["src/lib.rs".to_string()],
+                    content: Some(bridge_core::orch::ContentSummary {
+                        item_count: 1,
+                        preview: "opening".to_string(),
+                    }),
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
+                    tool_call_id: "t1".to_string(),
+                    title: None,
+                    kind: None,
+                    status: Some("completed".to_string()),
+                    locations: None,
+                    content: None,
+                },
+            )
+            .await
+            .unwrap();
+        let s4 = store
+            .put_node_checkpoint_sequenced(&task_id, &node, &op, "node-out", true, now)
+            .await
+            .unwrap();
+        assert_eq!((s1, s2, s3, s4), (1, 2, 3, 4));
+
+        let inputs = store.journal_fold_inputs(&task_id).await.unwrap();
+        let snap =
+            bridge_core::task_store::fold_journal_to_snapshot(&inputs.events, &inputs.scalars)
+                .unwrap();
+        let frames = rich_snapshot_frames(&snap, &inputs.events, None);
+        assert_eq!(
+            snapshot_tags(&frames),
+            vec![
+                (3, "tool_call".to_string()),
+                (4, "node_finished".to_string())
+            ]
+        );
+
+        let tool_frame = frames.first().unwrap();
+        let value = serde_json::to_value(tool_frame).unwrap();
+        assert_eq!(value["status"], "completed");
+        assert_eq!(value["content_preview"], "opening");
+    }
+
     /// (8a) Terminal task with 2 checkpoints (seqs 1, 2) + terminal_seq 3, no cursor.
     /// Expected frames: [(1,"node_finished"),(2,"node_finished"),(2,"snapshot_complete"),(3,"terminal")]
     #[tokio::test]

```
