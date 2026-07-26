# Blind pairwise code-review judgment — D1F-d1-IMPL-01

Two different engineers (Arm A, Arm B) independently completed the SAME task
from the same starting commit. You see the task brief and both final diffs.
You do NOT know who the engineers are; judge only the work. Answer the JSON
schema exactly; a_materially_better/b_materially_better may not both be true;
both false = parity.

## Task brief (both arms received this; one may have received extra process guidance — judge the WORK, not the process)

You are an expert Rust engineer working as the IMPLEMENTER on `a2a-bridge` (an ACP↔A2A bridge + workflow
orchestrator). Your session cwd IS the a2a-bridge repo, on feature branch `feat/slice-7b-watchdog`. You EDIT the
working tree and run `cargo`. The specific ONE task is below the marker; do EXACTLY it, no more.

## Operating rules
- **Scope discipline:** implement ONLY what the task specifies. Honor back-compat: with NO `[agents.watchdog]`
  config the behavior is BYTE-IDENTICAL to today (no watchdog task spawned, `watch=None`); the warm/dispatcher path
  is untouched; the SDK handler stays NON-BLOCKING (a short `StdMutex`, no `.await` under the lock).
- **The plan is GROUND TRUTH and APPROVED (dual plan-reviewed → fix-then-implement, all fixes folded).** Read
  `docs/superpowers/plans/2026-06-20-slice-7b-watchdog.md` — its **`## v2 … (BINDING; PFIX-A..M)` section SUPERSEDES
  any contradicting task body text. READ THE PFIX SECTION FIRST.** The binding spec is
  `docs/superpowers/specs/2026-06-20-slice-7b-watchdog.md` (FIX-1..12). VERIFY each signature against the REAL code.
- **Key real APIs (PFIX-confirmed — do NOT re-derive):** `WatchdogConfig` lives in `crates/bridge-core/src/domain.rs`
  (next to `SandboxConfig`), NOT bridge-acp; `AcpConfig.watchdog: Option<bridge_core::domain::WatchdogConfig>`.
  `AgentEntry` has NO Default → adding a field breaks ~31 `AgentEntry { … }` literals (grep them all, add
  `watchdog: None`). The error→state method is `disposition() -> A2aDisposition` (NOT `to_state`); `AgentTimedOut`
  lands on the `_ => SetState(Failed)` default. The ONE exhaustive `BridgeError` match to update is `table_key`
  (`resilient.rs:154`) + the exhaustiveness Vec (`:183`). The `RequestPermissionRequest` handler does NOT capture
  the update registry — add `let updates_perm = Arc::clone(&updates);`. The watchdog `select!` arm DISCARDS the
  inner cancel outcome (always `Err(())` + `timed_out_local=true`). The disabled path (`watchdog=None`) spawns NO
  task + the select arm uses a `Pending` future. `tokio::time::sleep_until` needs `tokio::time::Instant::from_std`
  (TurnWatch.turn_start is `std::time::Instant`). `ContainerRwConfig` has a test literal at `lib.rs:810`.
- **TDD:** write the failing test(s) FIRST, run them to fail, then implement to green. Tests assert REAL behavior.
- **Conventions:** match surrounding style; `std::sync::Mutex` where a sync method locks, `tokio::sync::Mutex` for
  async-held; derive what neighbours derive; read the cited code BEFORE coding.
- **DO NOT COMMIT. DO NOT run any `git` command that mutates state.** Leave changes UNCOMMITTED — the controller
  verifies + commits. `git status`/`git diff` (read-only) are fine.

## Process
1. Read the cited plan task + the PFIX section + the spec sections + the existing code you'll touch.
2. Implement TDD. Then run (report exact commands + counts):
   - the task's `cargo test -p <crate> …` target(s), THEN `cargo test --workspace --no-run` (MUST pass — the
     AgentEntry/AcpConfig/ContainerRwConfig literal ripple means a missed site is a compile error).
   - `cargo fmt --all` then `cargo fmt --all --check`; `cargo clippy -p <crate> --all-targets -- -D warnings`.
   - NOTE the `_dyld_start` PTY flake: if a test BINARY hangs at startup, report it (the controller re-runs). Use a
     `timeout` to distinguish a real deadlock.
3. Self-review: completeness vs the task; back-compat (no-config byte-identity); ALL literal/match call sites updated
   (`cargo test --workspace --no-run` green).

## Report (plain text — DO NOT commit)
- **STATUS:** DONE | DONE_WITH_CONCERNS | BLOCKED | NEEDS_CONTEXT
- What you implemented; the test list + results; files changed. Self-review findings + concerns.

THE TASK:

# Slice 7b — TASK 5: The watchdog task + the driver `select!` arm + the `AgentTimedOut` terminal (the KEYSTONE)

Implement **Task 5** from `docs/superpowers/plans/2026-06-20-slice-7b-watchdog.md` in
`crates/bridge-acp/src/acp_backend.rs`. The DRIVER owns the terminal; the watchdog only SIGNALS. Builds on Task 4
(the watch + tap).

## Binding (FIX-1/5/8/9 + PFIX-F/G/H/L)
- **PFIX-F — the watchdog arm DISCARDS the inner cancel outcome.** The existing `done_sender.closed()` arm
  (`:1974`) PROPAGATES its inner `prompt_fut` result (`Ok(resp)→Done`). The watchdog arm runs the SAME cancel-notify
  + inner grace `select!` (for liveness/escalation) but UNCONDITIONALLY `timed_out_local = true; Err(())` — EVEN if
  the agent honors cancel and returns `Done{cancelled}` within grace (KEYSTONE: honored-cancel-after-timeout =
  `AgentTimedOut`, not a user cancel). Do NOT reuse the `closed()` arm's result-propagation.
- **PFIX-G — the disabled path (`watchdog=None`) spawns NO task + the select arm is `Pending`.** Don't make the arm
  unconditional. The select arm awaits a future that's `Pending` when disabled:
  `_ = async { match &watchdog_fired { Some(n) => n.notified().await, None => std::future::pending::<()>().await } }
  => { … }`. When `None`: no watchdog task spawned, the arm never fires → byte-identical.
- **PFIX-H — `tokio::time::sleep_until` takes `tokio::time::Instant`.** `TurnWatch.turn_start` is `std::time::
  Instant`; convert the computed std deadline via `tokio::time::Instant::from_std(std_deadline)`.
- **PFIX-L — `la_instant = turn_start + Duration::from_millis(la.saturating_sub(1))`** (undo the `+1` sentinel).
  **FIX-5:** use `saturating_sub`/saturating for the idle math (the handler can advance `la` mid-check).

## Steps
1. Read the driver setup + `select!` (`acp_backend.rs:1944-2032`): the `turn_kill` install, the outer `select!`
   (`:1971`, arms: `prompt_fut` / `kill.notified()` / `done_sender.closed()`), the `done_sender.closed()` arm's
   bounded cancel (CancelNotification + inner `select!{ prompt_fut | kill | sleep(grace)→escalate_terminate }`), the
   terminal `match outcome` (`:2010`), the all-exit cleanup `map.remove` (`:2002`). The Task-4 `Arc<TurnWatch>`
   (`watch`) in scope.
2. TDD — failing tests FIRST (use the fake-ACP harness `gate_prompt`/scripted updates):
```rust
#[tokio::test]
async fn watchdog_cancels_a_hung_turn_as_timed_out() {
    // fake backend ACCEPTS the prompt then NEVER responds + emits nothing;
    // AcpConfig.watchdog = { idle: 10s, hard_wall_clock: 50ms }; drive prompt;
    // the stream's terminal item is Err(BridgeError::AgentTimedOut) within ~wall-clock.
}
#[tokio::test]
async fn watchdog_does_not_trip_active_or_unmodeled_turn() {
    // (a) a backend emitting a Text chunk every 20ms then Done (idle=100ms) -> completes, no timeout.
    // (b) FIX-11: a backend emitting ONLY UNMODELED updates (e.g. AgentThoughtChunk) every 20ms then Done,
    //     idle=100ms < total < wall=10s -> completes (the unmodeled events still bump activity).
}
#[tokio::test]
async fn no_watchdog_config_is_byte_identical() {
    // watchdog=None -> no task spawned; a hung turn behaves as today (no AgentTimedOut).
}
```
   Run → FAIL.
3. Implement (only when `self.config.watchdog.is_some()`):
   - In `prompt_inner`: `let watchdog_fired = self.config.watchdog.as_ref().map(|_| Arc::new(tokio::sync::Notify::
     new())); let (done_tx, done_rx) = tokio::sync::oneshot::channel::<()>();` (build `done_tx` only when enabled,
     else skip the task).
   - **Spawn the `'static` watchdog task** (only when enabled) capturing `Arc<TurnWatch>` (the Task-4 watch),
     `watchdog_fired.clone()`, the two `Duration`s (from `self.config.watchdog`), `done_rx`, `turn_start`: loop —
     compute the next std deadline `wall = turn_start + hard_wall_clock; idle = if la!=0 { la_instant +
     idle_timeout } else { wall }; deadline = min(wall, idle)`; `tokio::select! { _ = tokio::time::sleep_until(
     tokio::time::Instant::from_std(deadline)) => {}, _ = &mut done_rx => return }`; on wake: reload `la`; if
     `turn_start.elapsed() >= hard_wall_clock` OR (`la != 0` && `Instant::now().saturating_duration_since(la
     _instant) >= idle_timeout`) → `notify.notify_one(); return;` else loop. (`done_rx` is `&mut`-pinned across the
     loop.)
   - **The driver outer `select!` (`:1971`) gains an arm** (PFIX-G `Pending` when disabled): `_ = async { match
     &watchdog_fired { Some(n) => n.notified().await, None => std::future::pending::<()>().await } } => { <hoist the
     done_sender.closed() arm's bounded-cancel body: send CancelNotification(agent_id); inner select!{ &mut
     prompt_fut | kill.notified() | sleep(grace)→escalate_terminate }>; timed_out_local = true; Err(()) }`
     (DISCARD the inner result — always `Err(())`). Declare `let mut timed_out_local = false;` before the select.
   - **Teardown:** at the all-exit cleanup (`:2002`, after `map.remove`), `drop(done_tx);` (→ the watchdog's
     `done_rx` resolves → it exits) — guard for the `None`/no-task case.
   - **Terminal (`:2010`):** `Err(()) => if timed_out_local { TurnEvent::Failed(BridgeError::AgentTimedOut) } else {
     <existing AgentCrashed> }`. `Ok(resp) => <existing Done>` (a natural completion is NEVER AgentTimedOut — the
     outer select picked `prompt_fut`, not the watchdog arm).
4. Run → PASS (the 3 new tests + ALL existing acp turn/cancel tests — the no-config path identical). `cargo test -p
   bridge-acp`; `cargo test --workspace --no-run`; fmt; `cargo clippy -p bridge-acp --all-targets -- -D warnings`.
   (dyld/compile-stall flake → report; controller re-runs.)
5. Self-review: the watchdog arm ALWAYS yields `Err(())`+`timed_out_local` (no `Ok` leak, PFIX-F)? disabled path
   `Pending` + no task (PFIX-G)? `tokio::time::Instant::from_std` (PFIX-H)? `la_instant` round-trip + saturating
   (PFIX-L)? teardown `drop(done_tx)` on every exit (no leak)? a natural `Ok(resp)` never relabeled? no `&mut
   prompt_fut` borrow conflict?

Report STATUS + test names + results + files changed. DO NOT commit.


## Probe question (answer in `probe_answer`, per arm)

Focus on TEST RIGOR: for each arm, would its tests FAIL on the pre-change code (regression-catching), do they cover negative/edge cases per new code path, and do they assert real behavior rather than trivially passing? Name the strongest and weakest test in each arm.

## Arm A diff

```diff
diff --git a/crates/bridge-acp/src/acp_backend.rs b/crates/bridge-acp/src/acp_backend.rs
index 1fa600e..f38964d 100644
--- a/crates/bridge-acp/src/acp_backend.rs
+++ b/crates/bridge-acp/src/acp_backend.rs
@@ -12,7 +12,7 @@ use std::collections::HashMap;
 use std::path::PathBuf;
 use std::sync::atomic::{AtomicBool, AtomicU64, Ordering};
 use std::sync::{Arc, Mutex as StdMutex};
-use std::time::Instant;
+use std::time::{Duration, Instant};
 
 use agent_client_protocol::schema::{
     AgentCapabilities, AuthMethod, AuthMethodId, AuthenticateRequest, CancelNotification,
@@ -1966,19 +1966,13 @@ impl AcpBackend {
         let (tx, rx) = mpsc::unbounded_channel::<TurnEvent>();
         let done_sender = tx.clone();
         let registry = Arc::clone(self.updates()?);
-        let watch = if self
-            .config
-            .as_ref()
-            .and_then(|c| c.watchdog.as_ref())
-            .is_some()
-        {
-            Some(Arc::new(TurnWatch {
+        let watchdog_cfg = self.config.as_ref().and_then(|c| c.watchdog.clone());
+        let watch = watchdog_cfg.as_ref().map(|_| {
+            Arc::new(TurnWatch {
                 turn_start: Instant::now(),
                 last_activity_ms: AtomicU64::new(0),
-            }))
-        } else {
-            None
-        };
+            })
+        });
         {
             let mut map = registry
                 .lock()
@@ -1992,6 +1986,67 @@ impl AcpBackend {
             );
         }
 
+        // ── E9 watchdog (armed only when `[agents.watchdog]` is configured) ──
+        // A 'static task observes the turn's activity watch + the wall-clock and
+        // SIGNALS `watchdog_fired` on timeout; the DRIVER below owns the terminal
+        // decision via its `select!` arm. Armed only now — AFTER `ensure_session`
+        // + the sender registration — so it can never poison a not-yet-set-up
+        // turn. The driver stops it on every exit by dropping `watchdog_done_tx`
+        // (the task `select!`s its `done_rx`), so no task leaks across turns.
+        // With no config: `watchdog_fired`/`watchdog_done_tx` stay `None`, no
+        // task is spawned, and the driver's arm is a never-ready `Pending`.
+        let watchdog_fired = watchdog_cfg
+            .as_ref()
+            .map(|_| Arc::new(tokio::sync::Notify::new()));
+        let watchdog_done_tx = match (&watchdog_cfg, &watch, &watchdog_fired) {
+            (Some(cfg), Some(w), Some(fired)) => {
+                let (done_tx, mut done_rx) = oneshot::channel::<()>();
+                let w = Arc::clone(w);
+                let fired = Arc::clone(fired);
+                let idle_timeout = cfg.idle_timeout;
+                let hard_wall_clock = cfg.hard_wall_clock;
+                tokio::spawn(async move {
+                    let turn_start = w.turn_start;
+                    let wall_deadline = turn_start + hard_wall_clock;
+                    // The handler stores `elapsed_ms + 1` (`0` = no event yet);
+                    // undo the sentinel to recover the activity instant.
+                    let la_instant =
+                        |la: u64| turn_start + Duration::from_millis(la.saturating_sub(1));
+                    loop {
+                        // Sleep to the NEXT deadline: the wall-clock, or — once
+                        // first activity has been seen — the idle deadline too.
+                        let la = w.last_activity_ms.load(Ordering::Relaxed);
+                        let deadline = if la != 0 {
+                            wall_deadline.min(la_instant(la) + idle_timeout)
+                        } else {
+                            wall_deadline
+                        };
+                        tokio::select! {
+                            _ = tokio::time::sleep_until(
+                                tokio::time::Instant::from_std(deadline),
+                            ) => {}
+                            // Turn ended (driver dropped the sender): stand down.
+                            _ = &mut done_rx => return,
+                        }
+                        // Re-load: the handler may have bumped while we slept, so
+                        // `la` can be NEWER than the deadline we slept to — the
+                        // saturating math treats future activity as idle 0.
+                        let la = w.last_activity_ms.load(Ordering::Relaxed);
+                        let idle_hit = la != 0
+                            && Instant::now().saturating_duration_since(la_instant(la))
+                                >= idle_timeout;
+                        if turn_start.elapsed() >= hard_wall_clock || idle_hit {
+                            fired.notify_one();
+                            return;
+                        }
+                        // Activity advanced past the slept-to deadline: re-derive.
+                    }
+                });
+                Some(done_tx)
+            }
+            _ => None,
+        };
+
         let cx = self.cx()?.clone();
         let req = Self::prompt_request(agent_id.clone(), &parts);
 
@@ -2026,9 +2081,47 @@ impl AcpBackend {
             //     await so the lock releases and the caller's stream ends.
             let prompt_fut = cx.send_request(req).block_task();
             tokio::pin!(prompt_fut);
+            // Set ONLY by the watchdog arm below; read by the terminal match.
+            // Because the outer `select!` atomically picks ONE arm, a natural
+            // completion (`prompt_fut` first) can never be relabeled a timeout.
+            let mut timed_out_local = false;
             let outcome: Result<_, ()> = tokio::select! {
                 outcome = &mut prompt_fut => outcome.map_err(|_| ()),
                 _ = kill.notified() => Err(()),
+                // E9 watchdog fired (idle / wall-clock timeout). Run the SAME
+                // bounded graceful cancel the stream-drop arm below runs — but
+                // DISCARD its outcome: even an agent that honors the cancel and
+                // returns `Done{cancelled}` within grace TIMED OUT (that must
+                // surface as `AgentTimedOut`, not as a user cancel), so this arm
+                // unconditionally yields `Err(())` + `timed_out_local`. When the
+                // watchdog is disabled (`watchdog_fired` is `None`) the awaited
+                // future is `Pending` forever and this arm never fires.
+                _ = async {
+                    match &watchdog_fired {
+                        Some(fired) => fired.notified().await,
+                        None => std::future::pending::<()>().await,
+                    }
+                } => {
+                    let _ = cx.send_notification(CancelNotification::new(
+                        agent_id_for_driver.clone(),
+                    ));
+                    // Bounded wait for liveness only: the agent may honor the
+                    // cancel (or the kill switch may fire); past grace we
+                    // escalate exactly like the stream-drop arm.
+                    tokio::select! {
+                        _ = &mut prompt_fut => {}
+                        _ = kill.notified() => {}
+                        _ = tokio::time::sleep(grace) => {
+                            AcpBackend::escalate_terminate(
+                                &supervised_for_driver,
+                                &container_for_driver,
+                                &reaped_for_driver,
+                            );
+                        }
+                    }
+                    timed_out_local = true;
+                    Err(())
+                }
                 _ = done_sender.closed() => {
                     // Early stream-drop → cancel THIS turn's agent session, then
                     // CONTINUE awaiting the prompt result so the turn lock still
@@ -2060,6 +2153,10 @@ impl AcpBackend {
             if let Ok(mut map) = registry_for_driver.lock() {
                 map.remove(&agent_id_for_driver);
             }
+            // Stop the per-turn watchdog task (`None` = no-op): dropping the
+            // sender resolves its `done_rx` so it exits. Runs on EVERY driver
+            // exit (Ok/Err/kill/consumer-drop) — no watchdog task leaks.
+            drop(watchdog_done_tx);
             // Clear the kill switch slot now the turn is ending (next turn installs
             // its own); avoids a stale notify firing across turns.
             if let Ok(mut slot) = kill_slot.lock() {
@@ -2071,6 +2168,19 @@ impl AcpBackend {
                 Ok(resp) => TurnEvent::Done(Update::Done {
                     stop_reason: AcpBackend::stop_reason_str(resp.stop_reason),
                 }),
+                // A watchdog-fired turn (the arm set `timed_out_local`) surfaces
+                // the DISTINCT `AgentTimedOut` — even when the agent honored the
+                // cancel within grace — so downstream can tell a timeout from a
+                // user cancel. (A natural completion took the `Ok` arm above and
+                // is never relabeled.)
+                Err(()) if timed_out_local => {
+                    tracing::warn!(
+                        session = ?agent_id_for_driver,
+                        "turn watchdog fired (idle/wall-clock timeout): \
+                         surfacing AgentTimedOut"
+                    );
+                    TurnEvent::Failed(BridgeError::AgentTimedOut)
+                }
                 // A transport/agent error (agent crash / mid-turn transport
                 // failure), OR a kill-switch/grace escalation, FAILED the turn:
                 // surface a terminal Err on the stream so downstream reports the
@@ -2865,6 +2975,9 @@ mod tests {
         ToolCall,
         /// `session/update` with a context-window `usage_update`.
         Usage(u64, u64),
+        /// No update: pause this many ms before the next scripted update
+        /// (models a long-but-emitting turn whose activity is spread over time).
+        Sleep(u64),
     }
 
     #[derive(Default)]
@@ -3415,6 +3528,10 @@ mod tests {
                                     let updates = r2.prompt_updates.lock().await.clone();
                                     for u in updates {
                                         let update = match u {
+                                            ScriptedUpdate::Sleep(ms) => {
+                                                tokio::time::sleep(Duration::from_millis(ms)).await;
+                                                continue;
+                                            }
                                             ScriptedUpdate::Text(t) => {
                                                 SessionUpdate::AgentMessageChunk(ContentChunk::new(
                                                     ContentBlock::Text(TextContent::new(t)),
@@ -4303,6 +4420,157 @@ mod tests {
         );
     }
 
+    // ── Slice 7b: per-turn E9 watchdog ──────────────────────────────────────────
+
+    /// [`test_config`] plus a per-turn watchdog and a SHORT cancel grace, so a
+    /// hung turn's timeout → bounded-cancel → escalation runs fast in tests.
+    fn watchdog_config(idle_timeout: Duration, hard_wall_clock: Duration) -> AcpConfig {
+        AcpConfig {
+            watchdog: Some(bridge_core::domain::WatchdogConfig {
+                idle_timeout,
+                hard_wall_clock,
+            }),
+            cancel_grace: Duration::from_millis(150),
+            ..test_config()
+        }
+    }
+
+    #[tokio::test]
+    async fn watchdog_cancels_a_hung_turn_as_timed_out() {
+        // The agent ACCEPTS the prompt then parks forever: no updates, no
+        // response. The hard wall-clock (50ms) must fire the watchdog; the
+        // driver runs the bounded cancel (the hung agent ignores it → grace →
+        // escalation) and the stream's terminal item is the DISTINCT
+        // Err(AgentTimedOut) — not the generic AgentCrashed, not a hang.
+        let rec = Recorder::new("agent-sess-WDHUNG");
+        rec.gate_prompt.store(true, Ordering::SeqCst); // never released: hung
+        let cfg = watchdog_config(Duration::from_secs(10), Duration::from_millis(50));
+        let be = connect_recording_with(rec.clone(), cfg).await;
+        let key = bkey("bridge-WDHUNG");
+
+        let mut s = be.prompt(&key, vec![]).await.unwrap();
+        match tokio::time::timeout(Duration::from_secs(2), s.next())
+            .await
+            .expect("watchdog must end the hung turn within ~wall-clock + grace")
+        {
+            Some(Err(BridgeError::AgentTimedOut)) => {}
+            other => panic!("hung turn must surface Err(AgentTimedOut), got {other:?}"),
+        }
+        assert!(
+            s.next().await.is_none(),
+            "stream terminates after the timeout Err"
+        );
+
+        // The watchdog fired the EXISTING graceful cancel first (session/cancel
+        // reached the agent before the grace escalation).
+        tokio::time::timeout(Duration::from_secs(2), rec.cancel_seen.notified())
+            .await
+            .expect("watchdog must send session/cancel to the agent");
+        assert_eq!(rec.cancels.lock().await.as_slice(), &["agent-sess-WDHUNG"]);
+    }
+
+    #[tokio::test]
+    async fn watchdog_does_not_trip_active_or_unmodeled_turn() {
+        // (a) A turn emitting MODELED activity (a text chunk every ~20ms, total
+        // > idle_timeout) completes normally: each chunk bumps the watch, so the
+        // idle deadline keeps moving and the watchdog never fires.
+        let rec = Recorder::new("agent-sess-WDACT");
+        let mut script = Vec::new();
+        for _ in 0..8 {
+            script.push(ScriptedUpdate::Sleep(20));
+            script.push(ScriptedUpdate::Text("tick"));
+        }
+        rec.set_updates(script).await;
+        let cfg = watchdog_config(Duration::from_millis(100), Duration::from_secs(10));
+        let be = connect_recording_with(rec.clone(), cfg).await;
+        let key = bkey("bridge-WDACT");
+
+        let mut s = be.prompt(&key, vec![]).await.unwrap();
+        let mut texts = 0usize;
+        let done = loop {
+            match tokio::time::timeout(Duration::from_secs(5), s.next())
+                .await
+                .expect("active turn must complete")
+            {
+                Some(Ok(Update::Text(_))) => texts += 1,
+                Some(Ok(Update::Done { stop_reason })) => break stop_reason,
+                other => panic!("active turn must not fail/time out, got {other:?}"),
+            }
+        };
+        assert_eq!(done, "end_turn", "active turn completes normally");
+        assert_eq!(texts, 8, "all chunks streamed (turn ran past idle_timeout)");
+        assert!(
+            rec.cancels.lock().await.is_empty(),
+            "watchdog must not cancel an active turn"
+        );
+
+        // (b) FIX-11: a turn emitting ONLY UNMODELED updates (thought chunks the
+        // mapper drops) with idle_timeout < total < hard_wall_clock still
+        // completes — the handler bumps activity BEFORE mapping, so a dropped
+        // event still counts as the agent being alive.
+        let rec = Recorder::new("agent-sess-WDTHOUGHT");
+        let mut script = Vec::new();
+        for _ in 0..8 {
+            script.push(ScriptedUpdate::Sleep(20));
+            script.push(ScriptedUpdate::Thought("thinking"));
+        }
+        rec.set_updates(script).await;
+        let cfg = watchdog_config(Duration::from_millis(100), Duration::from_secs(10));
+        let be = connect_recording_with(rec.clone(), cfg).await;
+        let key = bkey("bridge-WDTHOUGHT");
+
+        let mut s = be.prompt(&key, vec![]).await.unwrap();
+        let done = loop {
+            match tokio::time::timeout(Duration::from_secs(5), s.next())
+                .await
+                .expect("unmodeled-only turn must complete")
+            {
+                Some(Ok(Update::Done { stop_reason })) => break stop_reason,
+                Some(Ok(_)) => continue,
+                other => panic!("unmodeled-only turn must not fail/time out, got {other:?}"),
+            }
+        };
+        assert_eq!(done, "end_turn", "unmodeled-only turn completes normally");
+        assert!(
+            rec.cancels.lock().await.is_empty(),
+            "unmodeled updates must still bump activity (no false trip)"
+        );
+    }
+
+    #[tokio::test]
+    async fn no_watchdog_config_is_byte_identical() {
+        // watchdog=None → no watchdog task spawned, the select arm never fires:
+        // a hung turn behaves exactly as today — nothing happens within a bound
+        // well past the wall-clock a configured watchdog would use, and the turn
+        // completes normally once the agent is released.
+        let rec = Recorder::new("agent-sess-WDNONE");
+        rec.gate_prompt.store(true, Ordering::SeqCst);
+        let be = connect_recording(rec.clone()).await; // test_config(): watchdog None
+        let key = bkey("bridge-WDNONE");
+
+        let mut s = be.prompt(&key, vec![]).await.unwrap();
+        assert!(
+            tokio::time::timeout(Duration::from_millis(300), s.next())
+                .await
+                .is_err(),
+            "without watchdog config a hung turn must NOT time out"
+        );
+        assert!(
+            rec.cancels.lock().await.is_empty(),
+            "no watchdog cancel may fire without config"
+        );
+
+        // Release the agent: the turn completes normally (no AgentTimedOut).
+        rec.prompt_gate.notify_one();
+        match tokio::time::timeout(Duration::from_secs(2), s.next())
+            .await
+            .expect("released turn completes")
+        {
+            Some(Ok(Update::Done { stop_reason })) => assert_eq!(stop_reason, "end_turn"),
+            other => panic!("expected the normal Done, got {other:?}"),
+        }
+    }
+
     // ── Task 5: reverse session/request_permission handler ─────────────────────
 
     #[tokio::test]

```

## Arm B diff

```diff
diff --git a/crates/bridge-acp/src/acp_backend.rs b/crates/bridge-acp/src/acp_backend.rs
index 1fa600e..09492a5 100644
--- a/crates/bridge-acp/src/acp_backend.rs
+++ b/crates/bridge-acp/src/acp_backend.rs
@@ -1658,6 +1658,56 @@ impl AcpBackend {
         AcpBackend::reap_container(container, reaped);
     }
 
+    /// The per-turn E9 watchdog task (FIX-1/5/9, PFIX-H/L). `'static` — no `&self`,
+    /// no shared terminal-decision state: it only observes `watch` and the wall
+    /// clock, and `notify`s `fired` (once) on timeout before exiting. The DRIVER's
+    /// `select!` arm is what decides the terminal outcome (PFIX-F); this task never
+    /// touches the prompt/cancel machinery directly.
+    ///
+    /// Loop: sleep until the sooner of the hard wall-clock deadline or the current
+    /// idle deadline (no activity yet ⇒ idle deadline = the wall deadline, so the
+    /// task never wakes early with nothing to check). On wake, reload the latest
+    /// activity timestamp and re-check both bounds against real elapsed time (the
+    /// handler may have bumped activity while we slept, in which case neither bound
+    /// is actually exceeded yet — re-derive and loop). Exits early, with no
+    /// notification, when `done_rx` resolves (driver teardown on every turn end).
+    async fn run_watchdog(
+        watch: Arc<TurnWatch>,
+        fired: Arc<tokio::sync::Notify>,
+        idle_timeout: std::time::Duration,
+        hard_wall_clock: std::time::Duration,
+        mut done_rx: oneshot::Receiver<()>,
+    ) {
+        let wall_deadline = watch.turn_start + hard_wall_clock;
+        loop {
+            let la = watch.last_activity_ms.load(Ordering::Relaxed);
+            let deadline = if la != 0 {
+                let la_instant =
+                    watch.turn_start + std::time::Duration::from_millis(la.saturating_sub(1));
+                std::cmp::min(wall_deadline, la_instant + idle_timeout)
+            } else {
+                wall_deadline
+            };
+            tokio::select! {
+                _ = tokio::time::sleep_until(tokio::time::Instant::from_std(deadline)) => {}
+                _ = &mut done_rx => return,
+            }
+
+            let la = watch.last_activity_ms.load(Ordering::Relaxed);
+            let wall_elapsed = watch.turn_start.elapsed() >= hard_wall_clock;
+            let idle_elapsed = la != 0 && {
+                let la_instant =
+                    watch.turn_start + std::time::Duration::from_millis(la.saturating_sub(1));
+                Instant::now().saturating_duration_since(la_instant) >= idle_timeout
+            };
+            if wall_elapsed || idle_elapsed {
+                fired.notify_one();
+                return;
+            }
+            // Else activity advanced since the deadline was computed — re-derive.
+        }
+    }
+
     /// Reap the agent's `:ro` container (idempotent; no-op when `container` is `None`). Called from every
     /// teardown site (spawn-failure, escalate_terminate, retire, Drop) — at most one `docker rm -f` total.
     fn reap_container(container: &Option<ContainerReap>, reaped: &Arc<AtomicBool>) {
@@ -1966,19 +2016,13 @@ impl AcpBackend {
         let (tx, rx) = mpsc::unbounded_channel::<TurnEvent>();
         let done_sender = tx.clone();
         let registry = Arc::clone(self.updates()?);
-        let watch = if self
-            .config
-            .as_ref()
-            .and_then(|c| c.watchdog.as_ref())
-            .is_some()
-        {
-            Some(Arc::new(TurnWatch {
+        let watchdog_cfg = self.config.as_ref().and_then(|c| c.watchdog.clone());
+        let watch = watchdog_cfg.as_ref().map(|_| {
+            Arc::new(TurnWatch {
                 turn_start: Instant::now(),
                 last_activity_ms: AtomicU64::new(0),
-            }))
-        } else {
-            None
-        };
+            })
+        });
         {
             let mut map = registry
                 .lock()
@@ -1992,6 +2036,30 @@ impl AcpBackend {
             );
         }
 
+        // Per-turn watchdog signal (FIX-1/8): `watchdog_fired` is the notify the
+        // `'static` watchdog task below fires on timeout; the DRIVER's `select!`
+        // arm (not the watchdog) is the sole terminal decision (PFIX-F).
+        // `watchdog_done_tx` is dropped at the driver's all-exit cleanup so the
+        // watchdog task's `done_rx` resolves and it exits on EVERY turn end, not
+        // just a timeout (no leak). Both are `None` when disabled: no task is
+        // spawned, and the driver's `select!` arm awaits a `Pending` future
+        // (PFIX-G) — byte-identical to today.
+        let watchdog_fired = watch.as_ref().map(|_| Arc::new(tokio::sync::Notify::new()));
+        let watchdog_done_tx = match (&watch, &watchdog_fired, &watchdog_cfg) {
+            (Some(w), Some(fired), Some(wd)) => {
+                let (done_tx, done_rx) = oneshot::channel::<()>();
+                tokio::spawn(Self::run_watchdog(
+                    Arc::clone(w),
+                    Arc::clone(fired),
+                    wd.idle_timeout,
+                    wd.hard_wall_clock,
+                    done_rx,
+                ));
+                Some(done_tx)
+            }
+            _ => None,
+        };
+
         let cx = self.cx()?.clone();
         let req = Self::prompt_request(agent_id.clone(), &parts);
 
@@ -2026,6 +2094,10 @@ impl AcpBackend {
             //     await so the lock releases and the caller's stream ends.
             let prompt_fut = cx.send_request(req).block_task();
             tokio::pin!(prompt_fut);
+            // Set ONLY by the watchdog arm below (PFIX-F): the driver's `select!`
+            // atomically picks one arm, so a `prompt_fut` completion can never be
+            // retro-labeled as a timeout — this flag is the sole terminal signal.
+            let mut timed_out_local = false;
             let outcome: Result<_, ()> = tokio::select! {
                 outcome = &mut prompt_fut => outcome.map_err(|_| ()),
                 _ = kill.notified() => Err(()),
@@ -2053,6 +2125,38 @@ impl AcpBackend {
                         }
                     }
                 }
+                _ = async {
+                    match &watchdog_fired {
+                        Some(fired) => fired.notified().await,
+                        // Disabled (PFIX-G): never resolves, so this arm never
+                        // fires and no watchdog task was spawned — byte-identical
+                        // to today.
+                        None => std::future::pending::<()>().await,
+                    }
+                } => {
+                    // KEYSTONE (PFIX-F): run the SAME bounded cancel the
+                    // `done_sender.closed()` arm runs (for liveness/escalation),
+                    // but DISCARD whatever it yields — even an honored cancel
+                    // that returns `Done{"cancelled"}` within grace is STILL
+                    // `AgentTimedOut`, not a user cancel. Do NOT reuse that arm's
+                    // result-propagating `outcome`.
+                    let _ = cx.send_notification(CancelNotification::new(
+                        agent_id_for_driver.clone(),
+                    ));
+                    tokio::select! {
+                        _ = &mut prompt_fut => {}
+                        _ = kill.notified() => {}
+                        _ = tokio::time::sleep(grace) => {
+                            AcpBackend::escalate_terminate(
+                                &supervised_for_driver,
+                                &container_for_driver,
+                                &reaped_for_driver,
+                            );
+                        }
+                    }
+                    timed_out_local = true;
+                    Err(())
+                }
             };
 
             // Unregister this turn's sender FIRST so no late chunk is routed
@@ -2065,12 +2169,28 @@ impl AcpBackend {
             if let Ok(mut slot) = kill_slot.lock() {
                 *slot = None;
             }
+            // Tear down the watchdog task (FIX-8): dropping its `done` sender
+            // resolves the task's `done_rx` on EVERY turn exit (success, error,
+            // kill, consumer-drop, timeout), so it never outlives the turn. A
+            // no-op when the watchdog was disabled (`None`).
+            drop(watchdog_done_tx);
             let event = match outcome {
                 // Turn COMPLETED (incl. a real StopReason::Cancelled, which maps
-                // to Done{"cancelled"} — NOT an error). Emit the mapped Done.
+                // to Done{"cancelled"} — NOT an error). Emit the mapped Done. A
+                // natural completion is NEVER relabeled AgentTimedOut: the outer
+                // `select!` picked `prompt_fut`, not the watchdog arm.
                 Ok(resp) => TurnEvent::Done(Update::Done {
                     stop_reason: AcpBackend::stop_reason_str(resp.stop_reason),
                 }),
+                // The watchdog arm fired: a DISTINCT timeout outcome (FIX-1/6),
+                // never the generic AgentCrashed below.
+                Err(()) if timed_out_local => {
+                    tracing::warn!(
+                        session = ?agent_id_for_driver,
+                        "session/prompt watchdog fired: surfacing AgentTimedOut"
+                    );
+                    TurnEvent::Failed(BridgeError::AgentTimedOut)
+                }
                 // A transport/agent error (agent crash / mid-turn transport
                 // failure), OR a kill-switch/grace escalation, FAILED the turn:
                 // surface a terminal Err on the stream so downstream reports the
@@ -3030,6 +3150,14 @@ mod tests {
         /// Tests assert against this to verify `ensure_session` passed the correct
         /// cwd down to the wire (stashed SessionSpec.cwd vs static AcpConfig.cwd).
         new_session_cwd: Arc<Mutex<Option<std::path::PathBuf>>>,
+
+        // ── Slice 7b (watchdog): pace scripted updates in real time ────────────
+        /// When set, the prompt handler sleeps this long BEFORE each scripted
+        /// `session/update` it emits, so a test can model a turn that stays alive
+        /// via periodic notifications spaced out in real time (exercising the
+        /// watchdog's idle-timeout math) instead of an instant burst. `None`
+        /// (default) preserves the original no-delay burst emission.
+        update_interval: Arc<Mutex<Option<std::time::Duration>>>,
     }
 
     impl Recorder {
@@ -3100,6 +3228,7 @@ mod tests {
                 set_models: Arc::new(Mutex::new(Vec::new())),
                 set_model_seen: Arc::new(Notify::new()),
                 new_session_cwd: Arc::new(Mutex::new(None)),
+                update_interval: Arc::new(Mutex::new(None)),
             }
         }
 
@@ -3189,6 +3318,12 @@ mod tests {
             *self.prompt_updates.lock().await = updates;
         }
 
+        /// Pace scripted `session/update`s `d` apart in real time (default: an
+        /// instant burst). See [`Recorder::update_interval`].
+        async fn set_update_interval(&self, d: std::time::Duration) {
+            *self.update_interval.lock().await = Some(d);
+        }
+
         /// Set the `StopReason` the prompt turn returns.
         async fn set_stop_reason(&self, sr: StopReason) {
             *self.stop_reason.lock().await = sr;
@@ -3413,7 +3548,11 @@ mod tests {
                                 // is the wire `session/update`.
                                 let emit_updates = || async {
                                     let updates = r2.prompt_updates.lock().await.clone();
+                                    let interval = *r2.update_interval.lock().await;
                                     for u in updates {
+                                        if let Some(d) = interval {
+                                            tokio::time::sleep(d).await;
+                                        }
                                         let update = match u {
                                             ScriptedUpdate::Text(t) => {
                                                 SessionUpdate::AgentMessageChunk(ContentChunk::new(
@@ -4250,6 +4389,149 @@ mod tests {
         );
     }
 
+    #[tokio::test]
+    async fn watchdog_cancels_a_hung_turn_as_timed_out() {
+        // A fake backend that ACCEPTS the prompt then NEVER responds and emits
+        // nothing (parked on `prompt_gate`, which the test never releases). With
+        // a tiny `hard_wall_clock` (well under the huge `idle_timeout`, so the
+        // wall bound is what trips) and a short `cancel_grace`, the watchdog
+        // must fire, the driver's watchdog arm must cancel + bound-escalate, and
+        // the stream's sole terminal item must be `Err(AgentTimedOut)` — a
+        // DISTINCT outcome from the generic `AgentCrashed` the kill-switch/
+        // transport-error path produces.
+        let rec = Recorder::new("agent-sess-WD-HUNG");
+        rec.gate_prompt.store(true, Ordering::SeqCst);
+        let cfg = AcpConfig {
+            cancel_grace: Duration::from_millis(50),
+            watchdog: Some(bridge_core::domain::WatchdogConfig {
+                idle_timeout: Duration::from_secs(10),
+                hard_wall_clock: Duration::from_millis(50),
+            }),
+            ..test_config()
+        };
+        let be = connect_recording_with(rec.clone(), cfg).await;
+        let key = bkey("bridge-WD-HUNG");
+
+        let mut s = be.prompt(&key, vec![]).await.unwrap();
+        match tokio::time::timeout(Duration::from_secs(2), s.next())
+            .await
+            .expect("watchdog must end the hung turn well within the 2s bound")
+        {
+            Some(Err(BridgeError::AgentTimedOut)) => {}
+            other => panic!("expected terminal Err(AgentTimedOut), got {other:?}"),
+        }
+        assert!(
+            s.next().await.is_none(),
+            "stream terminates after the AgentTimedOut"
+        );
+        // The watchdog arm sends the SAME CancelNotification the done_sender.
+        // closed() arm sends, so the (hung) agent still observes a cancel.
+        tokio::time::timeout(Duration::from_secs(2), rec.cancel_seen.notified())
+            .await
+            .expect("the watchdog arm must cancel the agent's turn");
+    }
+
+    #[tokio::test]
+    async fn watchdog_does_not_trip_active_or_unmodeled_turn() {
+        // (a) A backend emitting a Text chunk every 20ms then Done, with
+        // idle_timeout=150ms (well above the 20ms gaps) and a large wall clock,
+        // must complete normally — no timeout, despite the turn's total
+        // duration exceeding idle_timeout (activity keeps resetting the idle
+        // deadline).
+        let rec_text = Recorder::new("agent-sess-WD-TEXT");
+        rec_text
+            .set_updates(vec![ScriptedUpdate::Text("chunk"); 10])
+            .await;
+        rec_text
+            .set_update_interval(Duration::from_millis(20))
+            .await;
+        let cfg = AcpConfig {
+            watchdog: Some(bridge_core::domain::WatchdogConfig {
+                idle_timeout: Duration::from_millis(150),
+                hard_wall_clock: Duration::from_secs(5),
+            }),
+            ..test_config()
+        };
+        let be_text = connect_recording_with(rec_text.clone(), cfg.clone()).await;
+        let key_text = bkey("bridge-WD-TEXT");
+        let mut s_text = be_text.prompt(&key_text, vec![]).await.unwrap();
+        let mut chunks = 0;
+        loop {
+            match tokio::time::timeout(Duration::from_secs(2), s_text.next())
+                .await
+                .expect("an actively-emitting turn must not be watchdog-timed-out")
+            {
+                Some(Ok(Update::Text(_))) => chunks += 1,
+                Some(Ok(Update::Done { stop_reason })) => {
+                    assert_eq!(stop_reason, "end_turn");
+                    break;
+                }
+                other => panic!("unexpected item: {other:?}"),
+            }
+        }
+        assert_eq!(chunks, 10, "all 10 text chunks were streamed before Done");
+
+        // (b) FIX-11: a backend emitting ONLY unmodeled updates (agent thought
+        // chunks — the mapper drops these, so they never reach the caller's
+        // stream as an `Update`) every 20ms then Done must ALSO complete: the
+        // handler's activity bump runs BEFORE the modeled/unmodeled split, so a
+        // dropped event still counts as the agent being alive (the keystone
+        // FIX-3 behavior this case actually exercises).
+        let rec_thought = Recorder::new("agent-sess-WD-THOUGHT");
+        rec_thought
+            .set_updates(vec![ScriptedUpdate::Thought("thinking"); 10])
+            .await;
+        rec_thought
+            .set_update_interval(Duration::from_millis(20))
+            .await;
+        let be_thought = connect_recording_with(rec_thought.clone(), cfg).await;
+        let key_thought = bkey("bridge-WD-THOUGHT");
+        let mut s_thought = be_thought.prompt(&key_thought, vec![]).await.unwrap();
+        match tokio::time::timeout(Duration::from_secs(2), s_thought.next())
+            .await
+            .expect("an unmodeled-only but active turn must not be watchdog-timed-out")
+        {
+            Some(Ok(Update::Done { stop_reason })) => assert_eq!(stop_reason, "end_turn"),
+            other => panic!("expected terminal Done (no chunks were modeled), got {other:?}"),
+        }
+    }
+
+    #[tokio::test]
+    async fn no_watchdog_config_is_byte_identical() {
+        // With no `[agents.watchdog]` config (`watchdog: None`, the default), a
+        // hung turn (accepted, never responded to, no updates emitted) must
+        // behave EXACTLY as today: no watchdog task is spawned, so nothing ever
+        // resolves the stream on its own — it stays pending indefinitely (well
+        // past the bound a configured watchdog in the sibling test trips at).
+        let rec = Recorder::new("agent-sess-WD-NONE");
+        rec.gate_prompt.store(true, Ordering::SeqCst);
+        let cfg = AcpConfig {
+            watchdog: None,
+            ..test_config()
+        };
+        let be = connect_recording_with(rec.clone(), cfg).await;
+        let key = bkey("bridge-WD-NONE");
+
+        let mut s = be.prompt(&key, vec![]).await.unwrap();
+        assert!(
+            tokio::time::timeout(Duration::from_millis(300), s.next())
+                .await
+                .is_err(),
+            "no watchdog configured: a hung turn must not resolve on its own"
+        );
+
+        // Release the turn so the test cleans up (no leaked hung driver task).
+        rec.gate_prompt.store(false, Ordering::SeqCst);
+        rec.prompt_gate.notify_one();
+        match tokio::time::timeout(Duration::from_secs(2), s.next())
+            .await
+            .expect("released turn completes")
+        {
+            Some(Ok(Update::Done { stop_reason })) => assert_eq!(stop_reason, "end_turn"),
+            other => panic!("expected terminal Done after release, got {other:?}"),
+        }
+    }
+
     #[tokio::test]
     async fn dropping_stream_cancels_agent_turn() {
         // If the CONSUMER drops the returned BackendStream mid-turn (client

```
