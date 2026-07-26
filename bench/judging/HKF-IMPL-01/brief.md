# Blind pairwise code-review judgment — HKF-IMPL-01

Two different engineers (Arm A, Arm B) independently completed the SAME task
from the same starting commit. You see the task brief and both final diffs.
You do NOT know who the engineers are; judge only the work. Answer the JSON
schema exactly; a_materially_better/b_materially_better may not both be true;
both false = parity. Ignore any VERIFICATION.md or process-artifact files in
a diff — judge the code and tests.

## Task brief (both arms received this; process environments may differ — judge the WORK)

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

Focus on TEST RIGOR: for each arm, would its tests FAIL on the pre-change code, do they cover negative/edge cases per new code path, and do they assert real behavior rather than trivially passing? Name the strongest and weakest test in each arm.

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
index 1fa600e..add3471 100644
--- a/crates/bridge-acp/src/acp_backend.rs
+++ b/crates/bridge-acp/src/acp_backend.rs
@@ -1992,6 +1992,70 @@ impl AcpBackend {
             );
         }
 
+        // Per-turn watchdog: a `'static` task that only SIGNALS `watchdog_fired`
+        // on idle/wall-clock timeout — it never touches `self`/`cx`; the DRIVER
+        // (below) owns the terminal decision. `None` when disabled (`watch` is
+        // `None`): no task is spawned, so the driver's select! arm on it (below)
+        // never fires — byte-identical to today.
+        let watchdog_fired = watch.as_ref().map(|_| Arc::new(tokio::sync::Notify::new()));
+        let mut watchdog_done_tx = None;
+        if let (Some(watch_arc), Some(fired), Some(wd_cfg)) = (
+            &watch,
+            &watchdog_fired,
+            self.config.as_ref().and_then(|c| c.watchdog.as_ref()),
+        ) {
+            let (done_tx, mut done_rx) = oneshot::channel::<()>();
+            watchdog_done_tx = Some(done_tx);
+            let watch_arc = Arc::clone(watch_arc);
+            let fired = Arc::clone(fired);
+            let idle_timeout = wd_cfg.idle_timeout;
+            let hard_wall_clock = wd_cfg.hard_wall_clock;
+            tokio::spawn(async move {
+                loop {
+                    let la = watch_arc.last_activity_ms.load(Ordering::Relaxed);
+                    let wall_deadline = watch_arc.turn_start + hard_wall_clock;
+                    let idle_deadline = if la != 0 {
+                        let la_instant = watch_arc.turn_start
+                            + std::time::Duration::from_millis(la.saturating_sub(1));
+                        la_instant + idle_timeout
+                    } else {
+                        // No activity yet: still bound this sleep to at most
+                        // `idle_timeout` (anchored to NOW, not `turn_start` —
+                        // avoids re-deriving an already-past deadline and
+                        // spinning) so the watchdog re-derives periodically
+                        // instead of committing to `wall_deadline`. Without
+                        // this, the FIRST iteration — where `la` is virtually
+                        // ALWAYS still 0, since the prompt hasn't even been
+                        // sent yet when this task starts — would sleep the
+                        // FULL wall-clock and never notice activity that
+                        // starts, then goes silent, well before it elapses.
+                        Instant::now() + idle_timeout
+                    };
+                    let deadline = std::cmp::min(wall_deadline, idle_deadline);
+                    tokio::select! {
+                        _ = tokio::time::sleep_until(tokio::time::Instant::from_std(deadline)) => {}
+                        _ = &mut done_rx => return,
+                    }
+
+                    // Re-derive against the FRESH activity: the handler may have
+                    // bumped it while we slept (FIX-5: saturating, no underflow).
+                    let la = watch_arc.last_activity_ms.load(Ordering::Relaxed);
+                    let wall_hit = watch_arc.turn_start.elapsed() >= hard_wall_clock;
+                    let idle_hit = la != 0 && {
+                        let la_instant = watch_arc.turn_start
+                            + std::time::Duration::from_millis(la.saturating_sub(1));
+                        Instant::now().saturating_duration_since(la_instant) >= idle_timeout
+                    };
+                    if wall_hit || idle_hit {
+                        fired.notify_one();
+                        return;
+                    }
+                    // Else: activity advanced since the deadline was computed —
+                    // loop and re-derive a fresh deadline.
+                }
+            });
+        }
+
         let cx = self.cx()?.clone();
         let req = Self::prompt_request(agent_id.clone(), &parts);
 
@@ -2011,6 +2075,8 @@ impl AcpBackend {
         let reaped_for_driver = Arc::clone(&self.reaped);
         let kill_slot = Arc::clone(&entry.turn_kill);
         let grace = self.cancel_grace();
+        let watchdog_fired_for_driver = watchdog_fired;
+        let watchdog_done_tx_for_driver = watchdog_done_tx;
         tokio::spawn(async move {
             // Hold the turn lock for the entire turn.
             let _turn = turn_guard;
@@ -2023,7 +2089,13 @@ impl AcpBackend {
             //     turn lock; or
             //   * the external cancel grace-watcher firing the kill switch (a hung
             //     agent that ignored `session/cancel` past grace) — we abandon the
-            //     await so the lock releases and the caller's stream ends.
+            //     await so the lock releases and the caller's stream ends; or
+            //   * the per-turn WATCHDOG firing (idle/wall-clock timeout) — same
+            //     bounded cancel as the stream-drop arm below, but the outcome is
+            //     UNCONDITIONALLY a timeout (PFIX-F): even an agent that honors
+            //     the cancel and returns within grace is reported AgentTimedOut,
+            //     not a clean/cancelled completion.
+            let mut timed_out_local = false;
             let prompt_fut = cx.send_request(req).block_task();
             tokio::pin!(prompt_fut);
             let outcome: Result<_, ()> = tokio::select! {
@@ -2053,6 +2125,33 @@ impl AcpBackend {
                         }
                     }
                 }
+                _ = async {
+                    match &watchdog_fired_for_driver {
+                        Some(n) => n.notified().await,
+                        None => std::future::pending::<()>().await,
+                    }
+                } => {
+                    // SAME bounded cancel the stream-drop arm above runs (graceful
+                    // `session/cancel` first; escalate only past grace) — but its
+                    // inner outcome is DISCARDED: this arm always yields Err(())
+                    // with `timed_out_local = true` (the KEYSTONE, PFIX-F).
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
@@ -2065,12 +2164,27 @@ impl AcpBackend {
             if let Ok(mut slot) = kill_slot.lock() {
                 *slot = None;
             }
+            // Tear down the per-turn watchdog task (FIX-8): dropping its `done_tx`
+            // resolves the watchdog's `done_rx`, so it exits promptly instead of
+            // sleeping out its full deadline. `None` (disabled) is a no-op drop.
+            drop(watchdog_done_tx_for_driver);
             let event = match outcome {
                 // Turn COMPLETED (incl. a real StopReason::Cancelled, which maps
-                // to Done{"cancelled"} — NOT an error). Emit the mapped Done.
+                // to Done{"cancelled"} — NOT an error). Emit the mapped Done. A
+                // natural completion is NEVER relabeled AgentTimedOut: the outer
+                // select! above picked `prompt_fut`, not the watchdog arm.
                 Ok(resp) => TurnEvent::Done(Update::Done {
                     stop_reason: AcpBackend::stop_reason_str(resp.stop_reason),
                 }),
+                // The watchdog fired (idle/wall-clock) → a DISTINCT timeout outcome
+                // (never retried as transient; see `BridgeError::AgentTimedOut`).
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
@@ -3030,6 +3144,12 @@ mod tests {
         /// Tests assert against this to verify `ensure_session` passed the correct
         /// cwd down to the wire (stashed SessionSpec.cwd vs static AcpConfig.cwd).
         new_session_cwd: Arc<Mutex<Option<std::path::PathBuf>>>,
+
+        // ── Task 5 (watchdog): pace scripted updates to exercise idle timing ──
+        /// When set, `emit_updates` sleeps this long after EACH scripted update
+        /// (instead of emitting the whole burst instantly), so a watchdog test
+        /// can assert idle/wall-clock behavior against real elapsed time.
+        update_interval: Arc<Mutex<Option<Duration>>>,
     }
 
     impl Recorder {
@@ -3100,6 +3220,7 @@ mod tests {
                 set_models: Arc::new(Mutex::new(Vec::new())),
                 set_model_seen: Arc::new(Notify::new()),
                 new_session_cwd: Arc::new(Mutex::new(None)),
+                update_interval: Arc::new(Mutex::new(None)),
             }
         }
 
@@ -3189,6 +3310,12 @@ mod tests {
             *self.prompt_updates.lock().await = updates;
         }
 
+        /// Space each scripted update this far apart (instead of an instant
+        /// burst), so a watchdog test can exercise idle/wall-clock timing.
+        async fn set_update_interval(&self, d: Duration) {
+            *self.update_interval.lock().await = Some(d);
+        }
+
         /// Set the `StopReason` the prompt turn returns.
         async fn set_stop_reason(&self, sr: StopReason) {
             *self.stop_reason.lock().await = sr;
@@ -3444,6 +3571,9 @@ mod tests {
                                             sid.clone(),
                                             update,
                                         ))?;
+                                        if let Some(d) = *r2.update_interval.lock().await {
+                                            tokio::time::sleep(d).await;
+                                        }
                                     }
                                     Ok::<(), agent_client_protocol::Error>(())
                                 };
@@ -4250,6 +4380,215 @@ mod tests {
         );
     }
 
+    #[tokio::test]
+    async fn watchdog_cancels_a_hung_turn_as_timed_out() {
+        // A fake agent that ACCEPTS the prompt, emits NOTHING, and never
+        // responds (even after the watchdog's own cancel arrives) models a
+        // genuinely hung turn. A short hard_wall_clock must trip the
+        // watchdog, which runs the SAME bounded cancel the driver already
+        // has for `done_sender.closed()`, and the terminal item must be the
+        // DISTINCT AgentTimedOut — not the generic AgentCrashed a plain
+        // kill-switch escalation yields.
+        let rec = Recorder::new("agent-sess-WD-HUNG");
+        rec.wait_cancel_before_respond.store(true, Ordering::SeqCst);
+        rec.hang_after_cancel.store(true, Ordering::SeqCst);
+        let cfg = AcpConfig {
+            watchdog: Some(bridge_core::domain::WatchdogConfig {
+                idle_timeout: Duration::from_secs(10),
+                hard_wall_clock: Duration::from_millis(50),
+            }),
+            cancel_grace: Duration::from_millis(150),
+            ..test_config()
+        };
+        let be = connect_recording_with(rec.clone(), cfg).await;
+        let key = bkey("bridge-WD-HUNG");
+
+        let mut s = be.prompt(&key, vec![]).await.unwrap();
+        match tokio::time::timeout(Duration::from_secs(2), s.next())
+            .await
+            .expect("watchdog must terminate the hung turn, not hang")
+        {
+            Some(Err(BridgeError::AgentTimedOut)) => {}
+            other => panic!("hung turn must surface AgentTimedOut, got {other:?}"),
+        }
+        assert!(
+            s.next().await.is_none(),
+            "stream terminates after the timeout Err"
+        );
+    }
+
+    #[tokio::test]
+    async fn watchdog_idle_timeout_fires_after_activity_goes_silent() {
+        // Distinct from the wall-clock case above: the agent emits ONE chunk
+        // (bumping `last_activity_ms` away from the `la == 0` sentinel), then
+        // goes silent forever (even past cancel). `hard_wall_clock` is set
+        // large so ONLY the idle-timeout branch (`la != 0 && now - la_instant
+        // >= idle_timeout`) can plausibly fire within the test's bound —
+        // exercising the idle-after-first-activity math specifically, not
+        // just the `la == 0` fallback-to-wall-clock path.
+        let rec = Recorder::new("agent-sess-WD-IDLE");
+        rec.set_updates(vec![ScriptedUpdate::Text("first")]).await;
+        rec.wait_cancel_before_respond.store(true, Ordering::SeqCst);
+        rec.hang_after_cancel.store(true, Ordering::SeqCst);
+        let cfg = AcpConfig {
+            watchdog: Some(bridge_core::domain::WatchdogConfig {
+                idle_timeout: Duration::from_millis(60),
+                hard_wall_clock: Duration::from_secs(5),
+            }),
+            cancel_grace: Duration::from_millis(150),
+            ..test_config()
+        };
+        let be = connect_recording_with(rec.clone(), cfg).await;
+        let key = bkey("bridge-WD-IDLE");
+
+        let mut s = be.prompt(&key, vec![]).await.unwrap();
+        assert!(matches!(s.next().await, Some(Ok(Update::Text(t))) if t == "first"));
+
+        match tokio::time::timeout(Duration::from_secs(2), s.next())
+            .await
+            .expect("idle watchdog must terminate the silent turn, not hang")
+        {
+            Some(Err(BridgeError::AgentTimedOut)) => {}
+            other => panic!(
+                "silent-after-initial-activity turn must surface AgentTimedOut via idle, got {other:?}"
+            ),
+        }
+    }
+
+    #[tokio::test]
+    async fn watchdog_fired_cancel_honored_within_grace_is_still_timed_out() {
+        // KEYSTONE (PFIX-F): if the watchdog fires and the agent HONORS the
+        // graceful cancel — returning `Done{"cancelled"}` promptly, well
+        // within grace — the terminal outcome must STILL be `AgentTimedOut`,
+        // never a clean/cancelled `Done`. The watchdog arm's inner bounded
+        // cancel discards its result UNCONDITIONALLY; only the
+        // `done_sender.closed()` arm propagates a natural outcome.
+        let rec = Recorder::new("agent-sess-WD-HONOR");
+        rec.wait_cancel_before_respond.store(true, Ordering::SeqCst);
+        rec.set_stop_reason(StopReason::Cancelled).await;
+        // `hang_after_cancel` stays false (default): the fake agent responds
+        // PROMPTLY once `cancel_arrived` fires, i.e. as soon as the
+        // watchdog's own `CancelNotification` reaches it — well inside grace.
+        let cfg = AcpConfig {
+            watchdog: Some(bridge_core::domain::WatchdogConfig {
+                idle_timeout: Duration::from_secs(10),
+                hard_wall_clock: Duration::from_millis(50),
+            }),
+            cancel_grace: Duration::from_secs(2),
+            ..test_config()
+        };
+        let be = connect_recording_with(rec.clone(), cfg).await;
+        let key = bkey("bridge-WD-HONOR");
+
+        let mut s = be.prompt(&key, vec![]).await.unwrap();
+        match tokio::time::timeout(Duration::from_secs(2), s.next())
+            .await
+            .expect("watchdog-triggered honored cancel must still resolve, not hang")
+        {
+            Some(Err(BridgeError::AgentTimedOut)) => {}
+            other => panic!(
+                "an honored cancel AFTER a watchdog timeout must still be AgentTimedOut \
+                 (not a cancelled Done), got {other:?}"
+            ),
+        }
+    }
+
+    #[tokio::test]
+    async fn watchdog_does_not_trip_active_or_unmodeled_turn() {
+        // (a) steady MODELED text chunks keep the idle deadline pushed out —
+        // the turn completes normally, never timed out.
+        let rec_a = Recorder::new("agent-sess-WD-ACTIVE");
+        rec_a
+            .set_updates(vec![
+                ScriptedUpdate::Text("a"),
+                ScriptedUpdate::Text("b"),
+                ScriptedUpdate::Text("c"),
+                ScriptedUpdate::Text("d"),
+                ScriptedUpdate::Text("e"),
+            ])
+            .await;
+        rec_a.set_update_interval(Duration::from_millis(20)).await;
+        let cfg_a = AcpConfig {
+            watchdog: Some(bridge_core::domain::WatchdogConfig {
+                idle_timeout: Duration::from_millis(100),
+                hard_wall_clock: Duration::from_secs(10),
+            }),
+            ..test_config()
+        };
+        let be_a = connect_recording_with(rec_a.clone(), cfg_a).await;
+        let key_a = bkey("bridge-WD-ACTIVE");
+        let mut s_a = be_a.prompt(&key_a, vec![]).await.unwrap();
+        let done_a = loop {
+            match tokio::time::timeout(Duration::from_secs(2), s_a.next())
+                .await
+                .expect("actively-streaming turn must complete, not time out")
+            {
+                Some(Ok(Update::Done { stop_reason })) => break stop_reason,
+                Some(Ok(_)) => continue,
+                other => panic!("active turn must complete cleanly, got {other:?}"),
+            }
+        };
+        assert_eq!(done_a, "end_turn");
+
+        // (b) FIX-11: steady UNMODELED updates (thought chunks the mapper
+        // drops) must ALSO count as activity — the handler bumps BEFORE the
+        // modeled/unmodeled split, so a dropped event still counts as alive.
+        let rec_b = Recorder::new("agent-sess-WD-UNMODELED");
+        rec_b
+            .set_updates(vec![
+                ScriptedUpdate::Thought("t1"),
+                ScriptedUpdate::Thought("t2"),
+                ScriptedUpdate::Thought("t3"),
+                ScriptedUpdate::Thought("t4"),
+                ScriptedUpdate::Thought("t5"),
+                ScriptedUpdate::Thought("t6"),
+            ])
+            .await;
+        rec_b.set_update_interval(Duration::from_millis(20)).await;
+        let cfg_b = AcpConfig {
+            watchdog: Some(bridge_core::domain::WatchdogConfig {
+                idle_timeout: Duration::from_millis(100),
+                hard_wall_clock: Duration::from_secs(10),
+            }),
+            ..test_config()
+        };
+        let be_b = connect_recording_with(rec_b.clone(), cfg_b).await;
+        let key_b = bkey("bridge-WD-UNMODELED");
+        let mut s_b = be_b.prompt(&key_b, vec![]).await.unwrap();
+        let done_b = loop {
+            match tokio::time::timeout(Duration::from_secs(2), s_b.next())
+                .await
+                .expect("unmodeled-only turn must complete, not time out")
+            {
+                Some(Ok(Update::Done { stop_reason })) => break stop_reason,
+                Some(Ok(_)) => continue,
+                other => panic!("unmodeled-only turn must complete cleanly, got {other:?}"),
+            }
+        };
+        assert_eq!(done_b, "end_turn");
+    }
+
+    #[tokio::test]
+    async fn no_watchdog_config_is_byte_identical() {
+        // With NO [agents.watchdog] config, a hung turn behaves exactly as
+        // today: no watchdog task fires, so the stream stays pending (it is
+        // NOT terminated as AgentTimedOut, or at all) within a bound well
+        // past what a configured hard_wall_clock would have used above.
+        let rec = Recorder::new("agent-sess-WD-NONE");
+        rec.wait_cancel_before_respond.store(true, Ordering::SeqCst);
+        let be = connect_recording(rec.clone()).await; // test_config(): watchdog = None
+        let key = bkey("bridge-WD-NONE");
+
+        let mut s = be.prompt(&key, vec![]).await.unwrap();
+        let still_pending = tokio::time::timeout(Duration::from_millis(200), s.next())
+            .await
+            .is_err();
+        assert!(
+            still_pending,
+            "no watchdog config must never fire AgentTimedOut on a hung turn"
+        );
+    }
+
     #[tokio::test]
     async fn dropping_stream_cancels_agent_turn() {
         // If the CONSUMER drops the returned BackendStream mid-turn (client

```
