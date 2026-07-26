# Blind pairwise code-review judgment — HKW-IMPL-01

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
index 1fa600e..7c89cc1 100644
--- a/crates/bridge-acp/src/acp_backend.rs
+++ b/crates/bridge-acp/src/acp_backend.rs
@@ -2001,6 +2001,63 @@ impl AcpBackend {
         let kill = Arc::new(tokio::sync::Notify::new());
         *entry.turn_kill.lock().expect("turn_kill lock") = Some(Arc::clone(&kill));
 
+        // E9 watchdog (Task 5): when the agent has a `WatchdogConfig` (`watch`
+        // is `Some`, built above under the same `is_some()` check), spawn a
+        // `'static` task that observes the turn's `TurnWatch` for idle silence
+        // / hard wall-clock and `notify`s `watchdog_fired` on timeout, then
+        // exits. The task only SIGNALS — the DRIVER (its `select!` arm below)
+        // owns the cancel + terminal decision. `watch = None` → no task
+        // spawned and the arm never fires: byte-identical to today.
+        let watchdog_fired = watch.as_ref().map(|_| Arc::new(tokio::sync::Notify::new()));
+        let mut watchdog_done_tx: Option<oneshot::Sender<()>> = None;
+        if let (Some(turn_watch), Some(fired), Some(wd)) = (
+            watch.as_ref(),
+            watchdog_fired.as_ref(),
+            self.config.as_ref().and_then(|c| c.watchdog.as_ref()),
+        ) {
+            let (done_tx, mut done_rx) = oneshot::channel::<()>();
+            watchdog_done_tx = Some(done_tx);
+            let turn_watch = Arc::clone(turn_watch);
+            let fired = Arc::clone(fired);
+            let idle_timeout = wd.idle_timeout;
+            let hard_wall_clock = wd.hard_wall_clock;
+            tokio::spawn(async move {
+                loop {
+                    let la = turn_watch.last_activity_ms.load(Ordering::Relaxed);
+                    let wall_deadline = turn_watch.turn_start + hard_wall_clock;
+                    let deadline = if la != 0 {
+                        let idle_deadline = turn_watch.turn_start
+                            + std::time::Duration::from_millis(la.saturating_sub(1))
+                            + idle_timeout;
+                        std::cmp::min(wall_deadline, idle_deadline)
+                    } else {
+                        wall_deadline
+                    };
+                    tokio::select! {
+                        _ = tokio::time::sleep_until(tokio::time::Instant::from_std(deadline)) => {}
+                        _ = &mut done_rx => return,
+                    }
+                    // Re-check on wake: reload `la` (the handler may have bumped
+                    // it since we derived `deadline`) and test BOTH bounds with
+                    // saturating math (FIX-5) so a just-advanced activity can't
+                    // underflow into a false trip.
+                    let la = turn_watch.last_activity_ms.load(Ordering::Relaxed);
+                    let wall_timed_out = turn_watch.turn_start.elapsed() >= hard_wall_clock;
+                    let idle_timed_out = la != 0 && {
+                        let la_instant = turn_watch.turn_start
+                            + std::time::Duration::from_millis(la.saturating_sub(1));
+                        Instant::now().saturating_duration_since(la_instant) >= idle_timeout
+                    };
+                    if wall_timed_out || idle_timed_out {
+                        fired.notify_one();
+                        return;
+                    }
+                    // Else: activity advanced past our stale deadline — loop and
+                    // re-derive against the current `la`.
+                }
+            });
+        }
+
         // (3) Driver: holds the turn lock for the whole streamed turn (it OWNS
         // `turn_guard`, releasing the lock only when it finishes) and awaits the
         // `PromptResponse`; the SDK delivers chunks meanwhile via the handler.
@@ -2026,9 +2083,44 @@ impl AcpBackend {
             //     await so the lock releases and the caller's stream ends.
             let prompt_fut = cx.send_request(req).block_task();
             tokio::pin!(prompt_fut);
+            // Set only by the watchdog arm below (PFIX-F): a natural `Ok(resp)`
+            // (the `prompt_fut` arm winning the select) is NEVER relabeled, since
+            // the outer `select!` atomically picks exactly one arm.
+            let mut timed_out_local = false;
             let outcome: Result<_, ()> = tokio::select! {
                 outcome = &mut prompt_fut => outcome.map_err(|_| ()),
                 _ = kill.notified() => Err(()),
+                _ = async {
+                    match &watchdog_fired {
+                        Some(n) => n.notified().await,
+                        None => std::future::pending::<()>().await,
+                    }
+                } => {
+                    // The watchdog fired (idle or hard wall-clock exceeded). Run
+                    // the SAME bounded cancel the `done_sender.closed()` arm below
+                    // runs (for liveness/escalation), but UNCONDITIONALLY treat
+                    // the outcome as a timeout (PFIX-F/KEYSTONE): even an agent
+                    // that honors the cancel and returns `Done{"cancelled"}`
+                    // within grace is a timeout here, not a user cancel — this
+                    // arm and `done_sender.closed()` are NOT the same consumer,
+                    // so the inner `prompt_fut` result is discarded.
+                    let _ = cx.send_notification(CancelNotification::new(
+                        agent_id_for_driver.clone(),
+                    ));
+                    tokio::select! {
+                        outcome = &mut prompt_fut => { let _ = outcome; }
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
@@ -2065,17 +2157,32 @@ impl AcpBackend {
             if let Ok(mut slot) = kill_slot.lock() {
                 *slot = None;
             }
+            // Tear down the watchdog task (if any) on EVERY exit path: dropping
+            // its `done_tx` resolves the task's `done_rx` branch, so it returns
+            // instead of sleeping to a deadline that no longer matters. A no-op
+            // when the watchdog was never enabled (`None`).
+            drop(watchdog_done_tx);
             let event = match outcome {
                 // Turn COMPLETED (incl. a real StopReason::Cancelled, which maps
-                // to Done{"cancelled"} — NOT an error). Emit the mapped Done.
+                // to Done{"cancelled"} — NOT an error). Emit the mapped Done. The
+                // outer `select!` picked THIS arm, so the watchdog arm did not
+                // run: a natural completion is never relabeled AgentTimedOut.
                 Ok(resp) => TurnEvent::Done(Update::Done {
                     stop_reason: AcpBackend::stop_reason_str(resp.stop_reason),
                 }),
                 // A transport/agent error (agent crash / mid-turn transport
-                // failure), OR a kill-switch/grace escalation, FAILED the turn:
-                // surface a terminal Err on the stream so downstream reports the
-                // inbound A2A caller `Failed` — never a silent Done{"unknown"}
-                // that reads as a clean `Completed`.
+                // failure), a kill-switch/grace escalation, OR a watchdog-fired
+                // timeout, FAILED the turn: surface a terminal Err on the stream
+                // so downstream reports the inbound A2A caller `Failed` — never a
+                // silent Done{"unknown"} that reads as a clean `Completed`.
+                Err(()) if timed_out_local => {
+                    tracing::warn!(
+                        session = ?agent_id_for_driver,
+                        "session/prompt watchdog timeout (idle or hard wall-clock \
+                         exceeded): surfacing AgentTimedOut"
+                    );
+                    TurnEvent::Failed(BridgeError::AgentTimedOut)
+                }
                 Err(()) => {
                     tracing::warn!(
                         session = ?agent_id_for_driver,
@@ -2926,6 +3033,10 @@ mod tests {
         /// Scripted `session/update`s the prompt handler emits (in order) BEFORE
         /// it returns the `PromptResponse`. Empty by default.
         prompt_updates: Arc<Mutex<Vec<ScriptedUpdate>>>,
+        /// Delay slept AFTER emitting each scripted update (zero by default), so
+        /// watchdog tests can model a turn that drips activity over real wall-clock
+        /// time instead of emitting every chunk instantaneously.
+        update_delay: Arc<Mutex<Duration>>,
         /// The `StopReason` the prompt handler returns. `EndTurn` by default.
         stop_reason: Arc<Mutex<StopReason>>,
         /// When set, the prompt handler WAITS for a `session/cancel` to arrive
@@ -3048,6 +3159,7 @@ mod tests {
                 gate_prompt: Arc::new(AtomicBool::new(false)),
                 fail_prompt: Arc::new(AtomicBool::new(false)),
                 prompt_updates: Arc::new(Mutex::new(Vec::new())),
+                update_delay: Arc::new(Mutex::new(Duration::ZERO)),
                 stop_reason: Arc::new(Mutex::new(StopReason::EndTurn)),
                 wait_cancel_before_respond: Arc::new(AtomicBool::new(false)),
                 hang_after_cancel: Arc::new(AtomicBool::new(false)),
@@ -3189,6 +3301,12 @@ mod tests {
             *self.prompt_updates.lock().await = updates;
         }
 
+        /// Drip scripted updates over real wall-clock time: sleep `delay` after
+        /// emitting each one (default zero — emit instantaneously).
+        async fn set_update_delay(&self, delay: Duration) {
+            *self.update_delay.lock().await = delay;
+        }
+
         /// Set the `StopReason` the prompt turn returns.
         async fn set_stop_reason(&self, sr: StopReason) {
             *self.stop_reason.lock().await = sr;
@@ -3413,6 +3531,7 @@ mod tests {
                                 // is the wire `session/update`.
                                 let emit_updates = || async {
                                     let updates = r2.prompt_updates.lock().await.clone();
+                                    let delay = *r2.update_delay.lock().await;
                                     for u in updates {
                                         let update = match u {
                                             ScriptedUpdate::Text(t) => {
@@ -3444,6 +3563,9 @@ mod tests {
                                             sid.clone(),
                                             update,
                                         ))?;
+                                        if !delay.is_zero() {
+                                            tokio::time::sleep(delay).await;
+                                        }
                                     }
                                     Ok::<(), agent_client_protocol::Error>(())
                                 };
@@ -4303,6 +4425,156 @@ mod tests {
         );
     }
 
+    // ── Slice 7b Task 5: watchdog task + driver select! arm + AgentTimedOut ────
+
+    fn watchdog_config(
+        idle_timeout: Duration,
+        hard_wall_clock: Duration,
+    ) -> bridge_core::domain::WatchdogConfig {
+        bridge_core::domain::WatchdogConfig {
+            idle_timeout,
+            hard_wall_clock,
+        }
+    }
+
+    #[tokio::test]
+    async fn watchdog_cancels_a_hung_turn_as_timed_out() {
+        // The fake agent ACCEPTS the prompt then NEVER responds and emits nothing
+        // (parked on `prompt_gate`, never released). A short `hard_wall_clock`
+        // (well under the large `idle_timeout`) must trip the watchdog, which
+        // cancels the turn and — regardless of whether the agent honors the
+        // cancel — surfaces `AgentTimedOut` (the driver arm's terminal is
+        // unconditional, PFIX-F).
+        let rec = Recorder::new("agent-sess-WD-HUNG");
+        rec.gate_prompt.store(true, Ordering::SeqCst);
+        let cfg = AcpConfig {
+            watchdog: Some(watchdog_config(
+                Duration::from_secs(10),
+                Duration::from_millis(50),
+            )),
+            cancel_grace: Duration::from_millis(50),
+            ..test_config()
+        };
+        let be = connect_recording_with(rec.clone(), cfg).await;
+        let key = bkey("bridge-WD-HUNG");
+
+        let mut s = be.prompt(&key, vec![]).await.unwrap();
+        match tokio::time::timeout(Duration::from_secs(2), s.next())
+            .await
+            .expect("watchdog must trip within ~wall-clock + grace, not hang")
+        {
+            Some(Err(BridgeError::AgentTimedOut)) => {}
+            other => panic!("expected Err(AgentTimedOut), got {other:?}"),
+        }
+        assert!(
+            s.next().await.is_none(),
+            "stream terminates after the AgentTimedOut"
+        );
+
+        // Cleanup: release the fake agent so it doesn't linger past the test.
+        rec.gate_prompt.store(false, Ordering::SeqCst);
+        rec.prompt_gate.notify_one();
+    }
+
+    #[tokio::test]
+    async fn watchdog_does_not_trip_active_or_unmodeled_turn() {
+        // (a) A turn emitting a MODELED Text chunk every 20ms then Done, with
+        // idle=100ms << wall=10s, must run to completion — never timed out.
+        let rec = Recorder::new("agent-sess-WD-ACTIVE");
+        rec.set_updates(vec![
+            ScriptedUpdate::Text("a"),
+            ScriptedUpdate::Text("b"),
+            ScriptedUpdate::Text("c"),
+        ])
+        .await;
+        rec.set_update_delay(Duration::from_millis(20)).await;
+        let cfg = AcpConfig {
+            watchdog: Some(watchdog_config(
+                Duration::from_millis(100),
+                Duration::from_secs(10),
+            )),
+            ..test_config()
+        };
+        let be = connect_recording_with(rec.clone(), cfg).await;
+        let key = bkey("bridge-WD-ACTIVE");
+
+        let mut s = be.prompt(&key, vec![]).await.unwrap();
+        let done = loop {
+            match tokio::time::timeout(Duration::from_secs(2), s.next())
+                .await
+                .expect("actively-emitting turn must complete, not hang/timeout")
+            {
+                Some(Ok(Update::Done { stop_reason })) => break stop_reason,
+                Some(Ok(_)) => continue,
+                other => panic!("expected streamed text then Done, got {other:?}"),
+            }
+        };
+        assert_eq!(done, "end_turn", "an active turn is never watchdog-tripped");
+
+        // (b) FIX-11: a turn emitting ONLY UNMODELED updates (agent thought
+        // chunks — dropped by `map_session_update`) every 20ms then Done, with
+        // idle=100ms < total emission time < wall=10s, must ALSO complete: the
+        // handler bumps activity for every inbound update BEFORE the
+        // modeled/unmodeled split, so a dropped event still counts as alive.
+        let rec2 = Recorder::new("agent-sess-WD-UNMODELED");
+        rec2.set_updates(vec![
+            ScriptedUpdate::Thought("t1"),
+            ScriptedUpdate::Thought("t2"),
+            ScriptedUpdate::Thought("t3"),
+            ScriptedUpdate::Thought("t4"),
+        ])
+        .await;
+        rec2.set_update_delay(Duration::from_millis(20)).await;
+        let cfg2 = AcpConfig {
+            watchdog: Some(watchdog_config(
+                Duration::from_millis(100),
+                Duration::from_secs(10),
+            )),
+            ..test_config()
+        };
+        let be2 = connect_recording_with(rec2.clone(), cfg2).await;
+        let key2 = bkey("bridge-WD-UNMODELED");
+
+        let mut s2 = be2.prompt(&key2, vec![]).await.unwrap();
+        let done2 = loop {
+            match tokio::time::timeout(Duration::from_secs(2), s2.next())
+                .await
+                .expect("unmodeled-only turn must complete, not hang/timeout")
+            {
+                Some(Ok(Update::Done { stop_reason })) => break stop_reason,
+                Some(Ok(_)) => continue,
+                other => panic!("expected Done, got {other:?}"),
+            }
+        };
+        assert_eq!(
+            done2, "end_turn",
+            "unmodeled events still bump activity — never watchdog-tripped"
+        );
+    }
+
+    #[tokio::test]
+    async fn no_watchdog_config_is_byte_identical() {
+        // With `watchdog: None` (the default), a hung turn must behave exactly
+        // as before Slice 7b: no watchdog task is spawned, so nothing trips —
+        // the turn just stays parked. Assert no terminal item arrives within a
+        // bound well past both `hard_wall_clock` values used above.
+        let rec = Recorder::new("agent-sess-WD-NONE");
+        rec.gate_prompt.store(true, Ordering::SeqCst);
+        let be = connect_recording(rec.clone()).await; // test_config(): watchdog = None
+        let key = bkey("bridge-WD-NONE");
+
+        let mut s = be.prompt(&key, vec![]).await.unwrap();
+        let outcome = tokio::time::timeout(Duration::from_millis(300), s.next()).await;
+        assert!(
+            outcome.is_err(),
+            "no watchdog config → a hung turn must NOT be timed out (byte-identical), got {outcome:?}"
+        );
+
+        // Cleanup: release the fake agent so it doesn't linger past the test.
+        rec.gate_prompt.store(false, Ordering::SeqCst);
+        rec.prompt_gate.notify_one();
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
