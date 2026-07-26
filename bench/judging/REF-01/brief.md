# Blind pairwise code-review judgment — task REF-01

Two different engineers (Arm A, Arm B) independently completed the SAME task
from the same starting commit. You see the task brief and both final diffs.
You do NOT know who the engineers are; judge only the work. Both arms passed
the repo's build and the task's mechanical test evidence (suite green in both cases).

Answer the JSON schema exactly. Binary verdicts: `a_materially_better` /
`b_materially_better` may not both be true; both false = parity. "Materially
better" = a reviewer would insist the other arm adopt the difference
(correctness, safety, coverage of the specified requirements) — NOT style.

## Task brief (verbatim, both arms received this)

You are implementing ONE task in the a2a-bridge Rust workspace. Session cwd IS the repo root (/Users/wesleyjinks/code/a2a-bridge, branch feat/slice-1-config-reconcile). TDD, test+impl TOGETHER. Work ONLY on this task's file. EXACT commit message. This is a REFACTOR that MUST preserve mint behavior byte-identical.

KNOWN FLAKE: if `cargo test`/golden frames hang at `_dyld_start`, leave UNCOMMITTED, confirm `cargo build -p bridge-acp` clean, report BLOCKED(_dyld_start) + files — controller verifies+commits.

READ FIRST (authoritative, on disk): docs/superpowers/plans/2026-06-17-slice-1-config-reconcile.md — read **Task 4** AND the "v2 — dual plan-review fixes folded" section (PF-1, PF-5) AND the "v3 — apply-or-expire" section (PF-9). These are BINDING. Also read the real code: crates/bridge-acp/src/acp_backend.rs (AgentSession ~266-310, mint closure ~1184-1290, configure_model_option ~524-584, apply_effort_walkdown ~622-710, set_config_option ~480-495, set_model ~605-620) and crates/bridge-acp/src/model_effort.rs (EffortDecision, effort_opt, etc.).

=== TASK 4 (per the plan, with PF-1/PF-5/PF-9 folded) ===
Implement Task 4 from the plan: cache the session/new config surface on `AgentSession` + extract a callable-on-warm `apply_model_effort` helper from the mint closure. Key requirements (from the plan's Task 4 + PF sections):

1. Add to `AgentSession`: `config_surface: StdMutex<Option<ConfigSurface>>` (init None in `new()`); define `struct ConfigSurface { opts: Vec<SessionConfigOption>, models: Option<SessionModelState> }` (derive Clone, Default) near it.
2. Extract `apply_model_effort(cx, agent_session_id, agent_id, surface: &ConfigSurface, model: Option<&str>, effort: Option<Effort>, purpose: ApplyPurpose) -> Result<(ConfigSurface /*refreshed*/, String /*current_model*/), ApplyConfigError>` where `enum ApplyPurpose { Mint, Warm }` and `enum ApplyConfigError { NotAdvertised(BridgeError), Rejected(BridgeError) }` (carry the NATIVE error). It reuses `configure_model_option` (model) + the effort path (effort). PF-5: change `apply_effort_walkdown` to ALSO return the last refreshed `Vec<SessionConfigOption>` so `apply_model_effort` folds it into the returned `ConfigSurface.opts` (cache stays fresh). PF-1/PF-9 effort semantics: at `Mint`, effort-no-surface / FellBack / Skip stay NON-fatal (today's behavior). At `Warm`, a requested effort that does NOT apply EXACTLY (no surface, Unsupported, FellBack, or skipped) → `Err(ApplyConfigError::NotAdvertised)`; an effort RPC rejection → `Err(Rejected)`. Model: map `configure_model_option`'s `Err(config_invalid)` → `NotAdvertised(b)`, `Err(agent_crashed)` → `Rejected(b)` (preserve the native error b).
3. Rewire the mint closure to call `apply_model_effort(..., ApplyPurpose::Mint)`, `.map_err(|e| match e { NotAdvertised(b) | Rejected(b) => b })?` so MINT re-raises the EXACT native error (byte-identical: the "valid models: …" message, the resolved_log_line, the model_current). Keep `set_mode` + `minted_cwd.set` in the closure unchanged. After mint, cache the refreshed surface: `*entry.config_surface.lock() = Some(refreshed)`.

CRITICAL: mint behavior MUST stay byte-identical — the golden-frame + `configure_session_applies_*_at_mint` tests are the regression guard. Run them.

Tests to add: (a) mint still applies model/effort (regression — or rely on existing golden/mint tests passing); (b) after mint, `config_surface` is populated.

Verify: `cargo test -p bridge-acp --lib` + `cargo test -p bridge-acp --test golden_frames` + `cargo build -p bridge-acp`.

Commit:
```
git add crates/bridge-acp/src/acp_backend.rs crates/bridge-acp/src/model_effort.rs
git commit -m "refactor(acp): cache session/new config surface + extract apply_model_effort (mint-parity, PF-1/5/9)"
```
(stage model_effort.rs only if you changed apply_effort_walkdown's return there; do NOT stage examples/prompts.)

REPORT BACK: status DONE(committed)/BLOCKED(_dyld_start)/BLOCKED(other); golden-frame + mint test results if obtained; how you preserved the native mint error (PF-1); whether apply_effort_walkdown now returns refreshed opts (PF-5); commit hash; modified files. If preserving mint byte-identical is impossible with this extraction, STOP and report the specifics rather than changing mint behavior.


## Probe question (answer in `probe_answer`, per arm)

REFACTOR PARITY: mint behavior must stay byte-identical (native error messages, resolved_log_line, model_current). Does each arm (a) preserve mint exactly, (b) implement the Mint/Warm purpose semantics as specified (Warm: non-exact effort => NotAdvertised; RPC rejection => Rejected), (c) fold refreshed opts into the returned surface (PF-5)?

## Arm A diff

```diff
diff --git a/crates/bridge-acp/src/acp_backend.rs b/crates/bridge-acp/src/acp_backend.rs
index 03afb4d..9a2d2aa 100644
--- a/crates/bridge-acp/src/acp_backend.rs
+++ b/crates/bridge-acp/src/acp_backend.rs
@@ -32,11 +32,13 @@ use tokio::sync::{mpsc, oneshot, Mutex, OnceCell, OwnedMutexGuard};
 use tokio_util::compat::{TokioAsyncReadCompatExt, TokioAsyncWriteCompatExt};
 
 use crate::model_effort::{
-    caps_from_config_options, effort_opt, is_unsupported_effort_error, model_state_values,
-    model_values, resolve_effort, resolve_model, resolved_log_line, EffortDecision, ModelDecision,
-    EFFORT_ORDER,
+    caps_from_config_options, effort_level_name, effort_opt, is_unsupported_effort_error,
+    model_state_values, model_values, resolve_effort, resolve_model, resolved_log_line,
+    EffortDecision, ModelDecision, EFFORT_ORDER,
+};
+use bridge_core::domain::{
+    Effort, PermissionDecision, PermissionRequest, SessionContext, SessionSpec,
 };
-use bridge_core::domain::{PermissionDecision, PermissionRequest, SessionContext, SessionSpec};
 use bridge_core::error::BridgeError;
 use bridge_core::ids::SessionId;
 use bridge_core::ports::{
@@ -295,6 +297,11 @@ struct AgentSession {
     /// actually killed; the kill switch is what makes the in-process transport —
     /// which has no process to kill — unblock deterministically too.)
     turn_kill: Arc<StdMutex<Option<Arc<tokio::sync::Notify>>>>,
+    /// The advertised config surface from `session/new` (+ refreshed by
+    /// set_config_option), cached so a warm `reconcile_config` can re-apply
+    /// model/effort without re-minting. Set once at mint; updated under the
+    /// turn_lock on a warm re-apply. [Slice 1]
+    config_surface: StdMutex<Option<ConfigSurface>>,
 }
 
 impl AgentSession {
@@ -305,10 +312,47 @@ impl AgentSession {
             turn_lock: Arc::new(Mutex::new(())),
             cancel_requested: AtomicBool::new(false),
             turn_kill: Arc::new(StdMutex::new(None)),
+            config_surface: StdMutex::new(None),
         }
     }
 }
 
+/// The advertised config surface from `session/new` (+ refreshed by each
+/// successful `session/set_config_option`): the config options plus the
+/// unstable `models` state (kiro). Cached on [`AgentSession`] so a warm
+/// `reconcile_config` can re-apply model/effort without re-minting. [Slice 1]
+#[derive(Clone, Default)]
+struct ConfigSurface {
+    opts: Vec<SessionConfigOption>,
+    models: Option<SessionModelState>,
+}
+
+/// Who is calling [`AcpBackend::apply_model_effort`] (PF-1/PF-9). At `Mint`,
+/// effort keeps today's NON-fatal fallback semantics (FellBack/Skip/no surface
+/// are warn-and-proceed). At `Warm` (a live-session reconcile), every requested
+/// field must apply EXACTLY — anything less is an error, so the caller can
+/// discard the session rather than keep one whose live state may not match its
+/// fingerprint.
+#[derive(Clone, Copy, Debug, PartialEq, Eq)]
+enum ApplyPurpose {
+    Mint,
+    /// Warm reconcile of a live session (the Task-5 `reconcile_config` caller).
+    #[allow(dead_code)]
+    Warm,
+}
+
+/// Why [`AcpBackend::apply_model_effort`] could not fully apply the requested
+/// config. Carries the NATIVE [`BridgeError`] (PF-1): `NotAdvertised` wraps the
+/// `config_invalid` (the advertised surface cannot express the request — e.g.
+/// the "valid models: …" message), `Rejected` wraps the `agent_crashed` (the
+/// agent refused an RPC at runtime). The mint caller re-raises the inner error
+/// unchanged; the warm caller maps the variant to a `ReconcileOutcome`.
+#[derive(Debug)]
+enum ApplyConfigError {
+    NotAdvertised(BridgeError),
+    Rejected(BridgeError),
+}
+
 // ── Public struct ────────────────────────────────────────────────────────────
 
 pub struct AcpBackend {
@@ -619,13 +663,17 @@ impl AcpBackend {
         Ok(())
     }
 
+    /// Walk the requested effort down the advertised levels until one applies.
+    /// Also returns the LAST successful `set_config_option` refresh (PF-5) so
+    /// the caller's cached config surface stays fresh; `None` when nothing
+    /// applied (or the agent returned no refreshed options).
     async fn apply_effort_walkdown(
         cx: &ConnectionTo<Agent>,
         agent_session_id: &AgentSessionId,
         agent_id: &str,
         initial: EffortDecision,
         advertised_levels: &[String],
-    ) -> EffortDecision {
+    ) -> (EffortDecision, Option<Vec<SessionConfigOption>>) {
         let (config_id, requested_from, mut level) = match initial {
             EffortDecision::Apply { config_id, level } => (config_id, level.clone(), level),
             EffortDecision::FellBack {
@@ -641,21 +689,29 @@ impl AcpBackend {
                 );
                 (config_id, from, to)
             }
-            EffortDecision::Skip => return EffortDecision::Skip,
-            EffortDecision::Unsupported { from } => return EffortDecision::Unsupported { from },
+            EffortDecision::Skip => return (EffortDecision::Skip, None),
+            EffortDecision::Unsupported { from } => {
+                return (EffortDecision::Unsupported { from }, None)
+            }
         };
 
         loop {
             match Self::set_config_option(cx, agent_session_id, &config_id, &level).await {
-                Ok(_) => {
+                Ok(refreshed) => {
+                    // An empty refresh means the agent returned no options; keep
+                    // the caller's previous view (mirrors configure_model_option).
+                    let refreshed = (!refreshed.is_empty()).then_some(refreshed);
                     if level == requested_from {
-                        return EffortDecision::Apply { config_id, level };
+                        return (EffortDecision::Apply { config_id, level }, refreshed);
                     }
-                    return EffortDecision::FellBack {
-                        config_id,
-                        from: requested_from,
-                        to: level,
-                    };
+                    return (
+                        EffortDecision::FellBack {
+                            config_id,
+                            from: requested_from,
+                            to: level,
+                        },
+                        refreshed,
+                    );
                 }
                 Err(e) => {
                     let code = Self::error_code_i64(e.code);
@@ -667,7 +723,7 @@ impl AcpBackend {
                             error = ?e,
                             "session/set_config_option(effort) failed; stopping effort walk-down"
                         );
-                        return EffortDecision::Skip;
+                        return (EffortDecision::Skip, None);
                     }
 
                     let Some(next) = Self::next_lower_effort(&level, advertised_levels) else {
@@ -678,9 +734,12 @@ impl AcpBackend {
                             error = ?e,
                             "session/set_config_option(effort) unsupported and no lower advertised level remains"
                         );
-                        return EffortDecision::Unsupported {
-                            from: requested_from,
-                        };
+                        return (
+                            EffortDecision::Unsupported {
+                                from: requested_from,
+                            },
+                            None,
+                        );
                     };
                     tracing::warn!(
                         agent = %agent_id,
@@ -709,6 +768,148 @@ impl AcpBackend {
             .map(|level| (*level).to_string())
     }
 
+    /// Apply model + effort against an advertised `surface` on a live agent
+    /// session, returning the REFRESHED surface + the current model id. Pure of
+    /// `session/new` — callable at mint (with the freshly-minted surface) AND on
+    /// a warm session (`reconcile_config`, with the cached surface). [Slice 1]
+    ///
+    /// `purpose` drives the ONE semantic divergence (PF-1/PF-9): at `Mint`, a
+    /// requested effort that falls back / is unsupported / has no surface stays
+    /// NON-fatal (today's mint behavior); at `Warm`, every requested field must
+    /// apply EXACTLY — a surface that cannot express the request errors
+    /// `NotAdvertised`, an agent that refuses an RPC errors `Rejected` — so the
+    /// caller never treats a maybe-diverged live session as reconciled. Both
+    /// variants carry the NATIVE error (the mint caller re-raises it unchanged).
+    async fn apply_model_effort(
+        cx: &ConnectionTo<Agent>,
+        agent_session_id: &AgentSessionId,
+        agent_id: &str,
+        surface: &ConfigSurface,
+        model: Option<&str>,
+        effort: Option<Effort>,
+        purpose: ApplyPurpose,
+    ) -> Result<(ConfigSurface, String), ApplyConfigError> {
+        // Model — over both advertised surfaces (config_options / `models`).
+        // `config_invalid` means the surface does not advertise the request →
+        // NotAdvertised; anything else is the agent refusing an RPC → Rejected.
+        let (refreshed_opts, model_current) = Self::configure_model_option(
+            cx,
+            agent_session_id,
+            agent_id,
+            &surface.opts,
+            surface.models.as_ref(),
+            model,
+        )
+        .await
+        .map_err(|e| {
+            if matches!(e, BridgeError::ConfigInvalid { .. }) {
+                ApplyConfigError::NotAdvertised(e)
+            } else {
+                ApplyConfigError::Rejected(e)
+            }
+        })?;
+
+        // Effort — resolve against the refreshed post-model options, apply via
+        // the walk-down. `effort_refreshed` carries the walk-down's last
+        // successful refresh (PF-5) so the returned surface stays fresh.
+        let mut effort_rpc_rejected = false;
+        let (effort_outcome, effort_refreshed) = match effort_opt(&refreshed_opts) {
+            Some(advertised) => {
+                let decision = resolve_effort(effort, &advertised);
+                match decision {
+                    EffortDecision::Unsupported { from } => {
+                        tracing::warn!(
+                            agent = %agent_id,
+                            effort = %from,
+                            valid = ?advertised.levels,
+                            "configured effort is below the lowest advertised effort level; skipping"
+                        );
+                        (EffortDecision::Unsupported { from }, None)
+                    }
+                    EffortDecision::Skip => (EffortDecision::Skip, None),
+                    decision @ (EffortDecision::Apply { .. } | EffortDecision::FellBack { .. }) => {
+                        let (outcome, refreshed) = Self::apply_effort_walkdown(
+                            cx,
+                            agent_session_id,
+                            agent_id,
+                            decision,
+                            &advertised.levels,
+                        )
+                        .await;
+                        // The walk-down entered WANTING a change; coming back
+                        // `Skip` means the agent rejected the RPC with an
+                        // unrelated error, not that nothing was requested.
+                        effort_rpc_rejected = outcome == EffortDecision::Skip;
+                        (outcome, refreshed)
+                    }
+                }
+            }
+            None => {
+                if purpose == ApplyPurpose::Mint {
+                    if let Some(effort) = effort {
+                        tracing::warn!(
+                            agent = %agent_id,
+                            effort = ?effort,
+                            "agent advertised no effort option; skipping configured effort"
+                        );
+                    }
+                }
+                (EffortDecision::Skip, None)
+            }
+        };
+        tracing::info!(
+            "{}",
+            resolved_log_line(agent_id, &model_current, &effort_outcome)
+        );
+
+        // PF-9 (Warm only): a *requested* effort must have applied EXACTLY —
+        // no surface / Unsupported / FellBack / a skipped request all leave the
+        // live session in a state the caller must NOT record as reconciled.
+        if purpose == ApplyPurpose::Warm && effort.is_some() {
+            let want = effort.map(effort_level_name).unwrap_or_default();
+            match &effort_outcome {
+                EffortDecision::Apply { .. } => {}
+                EffortDecision::Skip if effort_rpc_rejected => {
+                    return Err(ApplyConfigError::Rejected(BridgeError::agent_crashed(
+                        format!(
+                            "agent {agent_id} rejected session/set_config_option(effort={want})"
+                        ),
+                    )));
+                }
+                EffortDecision::FellBack { from, to, .. } => {
+                    return Err(ApplyConfigError::NotAdvertised(BridgeError::config_invalid(
+                        format!(
+                            "agent {agent_id} effort={from} did not apply exactly (fell back to {to})"
+                        ),
+                    )));
+                }
+                EffortDecision::Unsupported { from } => {
+                    return Err(ApplyConfigError::NotAdvertised(BridgeError::config_invalid(
+                        format!("agent {agent_id} effort={from} is not advertised"),
+                    )));
+                }
+                EffortDecision::Skip => {
+                    return Err(ApplyConfigError::NotAdvertised(BridgeError::config_invalid(
+                        format!(
+                            "agent {agent_id} advertised no effort option but effort={want} requested"
+                        ),
+                    )));
+                }
+            }
+        }
+
+        // Fold the walk-down's refresh into the returned surface (PF-5). The
+        // kiro `set_model` path returns no refreshed options, so keep its cached
+        // `models` state fresh by updating `current_model_id` directly (the
+        // available model values are static per session).
+        let opts = effort_refreshed.unwrap_or(refreshed_opts);
+        let mut models = surface.models.clone();
+        if let Some(state) = models.as_mut() {
+            state.current_model_id = model_current.clone().into();
+        }
+        Ok((ConfigSurface { opts, models }, model_current))
+    }
+
     /// **Production** constructor: spawn `cmd args` as a `Supervised` child
     /// (its own process group, tested SIGTERM→SIGKILL reaping) and drive the
     /// ACP connection over its stdin/stdout as `ByteStreams`.
@@ -1218,65 +1419,37 @@ impl AcpBackend {
                         })?;
                 }
 
-                // (3) model — HARD validation against the agent-advertised model
-                // config option, then apply through session/set_config_option. A
-                // configured model that the agent did not advertise is operator
-                // config drift, so mint fails before any prompt is sent.
-                let (refreshed_opts, model_current) = Self::configure_model_option(
+                // (3)+(4) model + effort — via the shared `apply_model_effort`
+                // (Slice 1): the same helper a warm `reconcile_config` calls with
+                // the cached surface. Model validation stays a HARD mint error;
+                // effort keeps its non-fatal walk-down (`ApplyPurpose::Mint`).
+                // The NATIVE error is re-raised unchanged (PF-1), so a bad pin
+                // still fails the mint with today's exact `config_invalid`/
+                // `agent_crashed` before any prompt is sent.
+                let surface0 = ConfigSurface {
+                    opts: opts0,
+                    models: models0,
+                };
+                let (refreshed, _model_current) = Self::apply_model_effort(
                     cx,
                     &id,
                     &agent_id_for_mint,
-                    &opts0,
-                    models0.as_ref(),
+                    &surface0,
                     model.as_deref(),
+                    effort,
+                    ApplyPurpose::Mint,
                 )
-                .await?;
-
-                // (4) effort — resolve against the refreshed post-model options.
-                // Applying effort is non-fatal, but only unsupported-effort internal
-                // errors trigger walk-down; unrelated errors stop immediately.
-                let effort_outcome = match effort_opt(&refreshed_opts) {
-                    Some(advertised) => {
-                        let decision = resolve_effort(effort, &advertised);
-                        match decision {
-                            EffortDecision::Unsupported { from } => {
-                                tracing::warn!(
-                                    agent = %agent_id_for_mint,
-                                    effort = %from,
-                                    valid = ?advertised.levels,
-                                    "configured effort is below the lowest advertised effort level; skipping"
-                                );
-                                EffortDecision::Unsupported { from }
-                            }
-                            EffortDecision::Skip => EffortDecision::Skip,
-                            decision @ (EffortDecision::Apply { .. }
-                            | EffortDecision::FellBack { .. }) => {
-                                Self::apply_effort_walkdown(
-                                    cx,
-                                    &id,
-                                    &agent_id_for_mint,
-                                    decision,
-                                    &advertised.levels,
-                                )
-                                .await
-                            }
-                        }
-                    }
-                    None => {
-                        if let Some(effort) = effort {
-                            tracing::warn!(
-                                agent = %agent_id_for_mint,
-                                effort = ?effort,
-                                "agent advertised no effort option; skipping configured effort"
-                            );
-                        }
-                        EffortDecision::Skip
-                    }
-                };
-                tracing::info!(
-                    "{}",
-                    resolved_log_line(&agent_id_for_mint, &model_current, &effort_outcome)
-                );
+                .await
+                .map_err(|e| match e {
+                    ApplyConfigError::NotAdvertised(b) | ApplyConfigError::Rejected(b) => b,
+                })?;
+
+                // Cache the refreshed session/new config surface so a warm
+                // `reconcile_config` can re-apply model/effort without
+                // re-minting. [Slice 1]
+                if let Ok(mut cached) = entry.config_surface.lock() {
+                    *cached = Some(refreshed);
+                }
 
                 // (5) Record the cwd that was actually used to mint this session so
                 // the immutability guard below can compare future requests against
@@ -4410,6 +4583,109 @@ mod tests {
         );
     }
 
+    // ── Slice 1 (Task 4): config-surface cache + apply_model_effort ───────────
+
+    #[tokio::test]
+    async fn mint_caches_the_refreshed_config_surface() {
+        // After a mint that applies BOTH model and effort, `config_surface` is
+        // populated with the REFRESHED surface — not the stale session/new
+        // originals: the model select's current value reflects the applied
+        // model, the post-model effort levels replaced the originals, and the
+        // effort select's current value reflects the applied effort (proving
+        // the walk-down's refreshed options were folded in, PF-5).
+        let rec = Recorder::new("agent-sess-SURFACE");
+        // After the model applies, the agent advertises DIFFERENT effort levels;
+        // only the refreshed surface carries them.
+        *rec.refreshed_effort_values_after_model.lock().await =
+            Some(vec!["low".to_string(), "high".to_string()]);
+        let be = connect_recording(rec.clone()).await;
+        let key = bkey("bridge-SURFACE");
+
+        be.configure_session(
+            &key,
+            &SessionSpec::from_config(EffectiveConfig {
+                model: Some("m".to_string()),
+                effort: Some(Effort::High),
+                mode: None,
+            }),
+        )
+        .await
+        .unwrap();
+        be.ensure_session(&key).await.unwrap();
+
+        let entry = be.session_entry(&key).await;
+        let surface = entry
+            .config_surface
+            .lock()
+            .unwrap()
+            .clone()
+            .expect("config_surface must be populated after mint");
+        let (_, model_current, _) =
+            model_values(&surface.opts).expect("cached surface carries the model select");
+        assert_eq!(model_current, "m", "cached model reflects the applied value");
+        let advertised = effort_opt(&surface.opts).expect("cached surface carries the effort select");
+        assert_eq!(
+            advertised.levels,
+            vec!["low".to_string(), "high".to_string()],
+            "cached options are the post-model REFRESHED ones"
+        );
+        let effort_current = surface
+            .opts
+            .iter()
+            .find_map(|opt| match (&*opt.id.0, &opt.kind) {
+                ("effort", SessionConfigKind::Select(sel)) => {
+                    Some(sel.current_value.0.to_string())
+                }
+                _ => None,
+            })
+            .expect("effort select cached");
+        assert_eq!(
+            effort_current, "high",
+            "the effort walk-down's refresh was folded into the cache (PF-5)"
+        );
+    }
+
+    #[tokio::test]
+    async fn mint_caches_models_surface_with_applied_current() {
+        // kiro surface: no config_options, model applied via session/set_model
+        // (which returns no refreshed options). The cached surface must carry
+        // the `models` state with `current_model_id` updated to the APPLIED
+        // model, so a warm reconcile reads fresh values.
+        let rec = Recorder::new("agent-sess-SURFACE-KIRO");
+        rec.advertise_model_config.store(false, Ordering::SeqCst);
+        rec.advertise_effort_config.store(false, Ordering::SeqCst);
+        rec.advertise_models.store(true, Ordering::SeqCst);
+        *rec.model_state_values.lock().await =
+            vec!["auto".to_string(), "claude-sonnet-4.5".to_string()];
+        let be = connect_recording(rec.clone()).await;
+        let key = bkey("bridge-SURFACE-KIRO");
+
+        be.configure_session(
+            &key,
+            &SessionSpec::from_config(EffectiveConfig {
+                model: Some("claude-sonnet-4.5".to_string()),
+                effort: None,
+                mode: None,
+            }),
+        )
+        .await
+        .unwrap();
+        be.ensure_session(&key).await.unwrap();
+
+        let entry = be.session_entry(&key).await;
+        let surface = entry
+            .config_surface
+            .lock()
+            .unwrap()
+            .clone()
+            .expect("config_surface must be populated after mint");
+        let models = surface.models.expect("models state cached (kiro surface)");
+        assert_eq!(
+            &*models.current_model_id.0, "claude-sonnet-4.5",
+            "cached models.current_model_id tracks the APPLIED model"
+        );
+    }
+
     #[tokio::test]
     async fn effort_error_is_non_fatal() {
         // An unrelated config-option error must be NON-FATAL, and must not trigger

```

## Arm B diff

```diff
diff --git a/crates/bridge-acp/src/acp_backend.rs b/crates/bridge-acp/src/acp_backend.rs
index 03afb4d..1bfc155 100644
--- a/crates/bridge-acp/src/acp_backend.rs
+++ b/crates/bridge-acp/src/acp_backend.rs
@@ -36,7 +36,9 @@ use crate::model_effort::{
     model_values, resolve_effort, resolve_model, resolved_log_line, EffortDecision, ModelDecision,
     EFFORT_ORDER,
 };
-use bridge_core::domain::{PermissionDecision, PermissionRequest, SessionContext, SessionSpec};
+use bridge_core::domain::{
+    Effort, PermissionDecision, PermissionRequest, SessionContext, SessionSpec,
+};
 use bridge_core::error::BridgeError;
 use bridge_core::ids::SessionId;
 use bridge_core::ports::{
@@ -280,6 +282,9 @@ struct AgentSession {
     /// field) so `prompt` can take an OWNED guard (`lock_owned`) and move it into
     /// the driver task that holds it for the whole streamed turn.
     turn_lock: Arc<Mutex<()>>,
+    /// The advertised config surface from `session/new`, refreshed by later
+    /// `session/set_config_option` calls so warm config reconcile can reuse it.
+    config_surface: StdMutex<Option<ConfigSurface>>,
     /// Cancel latch: set by `request_cancel` when a cancel arrives before the
     /// agent session exists, so the minting task can fire `session/cancel` as
     /// soon as the id is known.
@@ -303,12 +308,31 @@ impl AgentSession {
             agent_id: OnceCell::new(),
             minted_cwd: OnceCell::new(),
             turn_lock: Arc::new(Mutex::new(())),
+            config_surface: StdMutex::new(None),
             cancel_requested: AtomicBool::new(false),
             turn_kill: Arc::new(StdMutex::new(None)),
         }
     }
 }
 
+#[derive(Clone, Default)]
+struct ConfigSurface {
+    opts: Vec<SessionConfigOption>,
+    models: Option<SessionModelState>,
+}
+
+#[derive(Clone, Copy)]
+#[allow(dead_code)]
+enum ApplyPurpose {
+    Mint,
+    Warm,
+}
+
+enum ApplyConfigError {
+    NotAdvertised(BridgeError),
+    Rejected(BridgeError),
+}
+
 // ── Public struct ────────────────────────────────────────────────────────────
 
 pub struct AcpBackend {
@@ -619,13 +643,131 @@ impl AcpBackend {
         Ok(())
     }
 
+    /// Apply model + effort against an advertised surface on a live agent session.
+    /// This is the mint-time config sequence lifted so warm reconcile can call the
+    /// same code without re-minting. Mint preserves today's permissive effort
+    /// behavior; warm requires an exact requested effort apply.
+    async fn apply_model_effort(
+        cx: &ConnectionTo<Agent>,
+        agent_session_id: &AgentSessionId,
+        agent_id: &str,
+        surface: &ConfigSurface,
+        model: Option<&str>,
+        effort: Option<Effort>,
+        purpose: ApplyPurpose,
+    ) -> Result<(ConfigSurface, String), ApplyConfigError> {
+        let (mut refreshed_opts, model_current) = Self::configure_model_option(
+            cx,
+            agent_session_id,
+            agent_id,
+            &surface.opts,
+            surface.models.as_ref(),
+            model,
+        )
+        .await
+        .map_err(|err| match err {
+            err @ BridgeError::ConfigInvalid { .. } => ApplyConfigError::NotAdvertised(err),
+            err @ BridgeError::AgentCrashed { .. } => ApplyConfigError::Rejected(err),
+            err => ApplyConfigError::Rejected(err),
+        })?;
+
+        let mut refreshed_models = surface.models.clone();
+        if model.is_some() && model_values(&surface.opts).is_none() {
+            if let Some(state) = refreshed_models.as_ref() {
+                refreshed_models = Some(SessionModelState::new(
+                    model_current.clone(),
+                    state.available_models.clone(),
+                ));
+            }
+        }
+
+        let effort_outcome = match effort_opt(&refreshed_opts) {
+            Some(advertised) => {
+                let decision = resolve_effort(effort, &advertised);
+                match decision {
+                    EffortDecision::Unsupported { from } => {
+                        tracing::warn!(
+                            agent = %agent_id,
+                            effort = %from,
+                            valid = ?advertised.levels,
+                            "configured effort is below the lowest advertised effort level; skipping"
+                        );
+                        EffortDecision::Unsupported { from }
+                    }
+                    EffortDecision::Skip => EffortDecision::Skip,
+                    decision @ (EffortDecision::Apply { .. } | EffortDecision::FellBack { .. }) => {
+                        match Self::apply_effort_walkdown(
+                            cx,
+                            agent_session_id,
+                            agent_id,
+                            decision,
+                            &advertised.levels,
+                        )
+                        .await
+                        {
+                            Ok((decision, refreshed)) => {
+                                if let Some(opts) = refreshed {
+                                    refreshed_opts = opts;
+                                }
+                                decision
+                            }
+                            Err(err) => {
+                                if matches!(purpose, ApplyPurpose::Warm) {
+                                    return Err(ApplyConfigError::Rejected(err));
+                                }
+                                EffortDecision::Skip
+                            }
+                        }
+                    }
+                }
+            }
+            None => {
+                if let Some(effort) = effort {
+                    tracing::warn!(
+                        agent = %agent_id,
+                        effort = ?effort,
+                        "agent advertised no effort option; skipping configured effort"
+                    );
+                }
+                EffortDecision::Skip
+            }
+        };
+        tracing::info!(
+            "{}",
+            resolved_log_line(agent_id, &model_current, &effort_outcome)
+        );
+
+        if matches!(purpose, ApplyPurpose::Warm) && effort.is_some() {
+            match &effort_outcome {
+                EffortDecision::Apply { .. } => {}
+                EffortDecision::Skip
+                | EffortDecision::FellBack { .. }
+                | EffortDecision::Unsupported { .. } => {
+                    return Err(ApplyConfigError::NotAdvertised(
+                        BridgeError::config_invalid(format!(
+                            "agent {agent_id} did not apply requested effort exactly"
+                        )),
+                    ));
+                }
+            }
+        }
+
+        Ok((
+            ConfigSurface {
+                opts: refreshed_opts,
+                models: refreshed_models,
+            },
+            model_current,
+        ))
+    }
+
     async fn apply_effort_walkdown(
         cx: &ConnectionTo<Agent>,
         agent_session_id: &AgentSessionId,
         agent_id: &str,
         initial: EffortDecision,
         advertised_levels: &[String],
-    ) -> EffortDecision {
+    ) -> Result<(EffortDecision, Option<Vec<SessionConfigOption>>), BridgeError> {
         let (config_id, requested_from, mut level) = match initial {
             EffortDecision::Apply { config_id, level } => (config_id, level.clone(), level),
             EffortDecision::FellBack {
@@ -641,21 +783,26 @@ impl AcpBackend {
                 );
                 (config_id, from, to)
             }
-            EffortDecision::Skip => return EffortDecision::Skip,
-            EffortDecision::Unsupported { from } => return EffortDecision::Unsupported { from },
+            EffortDecision::Skip => return Ok((EffortDecision::Skip, None)),
+            EffortDecision::Unsupported { from } => {
+                return Ok((EffortDecision::Unsupported { from }, None));
+            }
         };
 
         loop {
             match Self::set_config_option(cx, agent_session_id, &config_id, &level).await {
-                Ok(_) => {
+                Ok(refreshed) => {
                     if level == requested_from {
-                        return EffortDecision::Apply { config_id, level };
+                        return Ok((EffortDecision::Apply { config_id, level }, Some(refreshed)));
                     }
-                    return EffortDecision::FellBack {
-                        config_id,
-                        from: requested_from,
-                        to: level,
-                    };
+                    return Ok((
+                        EffortDecision::FellBack {
+                            config_id,
+                            from: requested_from,
+                            to: level,
+                        },
+                        Some(refreshed),
+                    ));
                 }
                 Err(e) => {
                     let code = Self::error_code_i64(e.code);
@@ -667,7 +814,9 @@ impl AcpBackend {
                             error = ?e,
                             "session/set_config_option(effort) failed; stopping effort walk-down"
                         );
-                        return EffortDecision::Skip;
+                        return Err(BridgeError::agent_crashed(format!(
+                            "session/set_config_option({config_id}) rejected: {e}"
+                        )));
                     }
 
                     let Some(next) = Self::next_lower_effort(&level, advertised_levels) else {
@@ -678,9 +827,12 @@ impl AcpBackend {
                             error = ?e,
                             "session/set_config_option(effort) unsupported and no lower advertised level remains"
                         );
-                        return EffortDecision::Unsupported {
-                            from: requested_from,
-                        };
+                        return Ok((
+                            EffortDecision::Unsupported {
+                                from: requested_from,
+                            },
+                            None,
+                        ));
                     };
                     tracing::warn!(
                         agent = %agent_id,
@@ -1218,65 +1370,28 @@ impl AcpBackend {
                         })?;
                 }
 
-                // (3) model — HARD validation against the agent-advertised model
-                // config option, then apply through session/set_config_option. A
-                // configured model that the agent did not advertise is operator
-                // config drift, so mint fails before any prompt is sent.
-                let (refreshed_opts, model_current) = Self::configure_model_option(
+                // (3) model + (4) effort. Model remains a hard mint error; effort
+                // remains best-effort at mint. The helper carries native errors so
+                // this mapping re-raises the exact config_invalid/agent_crashed.
+                let surface = ConfigSurface {
+                    opts: opts0,
+                    models: models0,
+                };
+                let (refreshed_surface, _model_current) = Self::apply_model_effort(
                     cx,
                     &id,
                     &agent_id_for_mint,
-                    &opts0,
-                    models0.as_ref(),
+                    &surface,
                     model.as_deref(),
+                    effort,
+                    ApplyPurpose::Mint,
                 )
-                .await?;
-
-                // (4) effort — resolve against the refreshed post-model options.
-                // Applying effort is non-fatal, but only unsupported-effort internal
-                // errors trigger walk-down; unrelated errors stop immediately.
-                let effort_outcome = match effort_opt(&refreshed_opts) {
-                    Some(advertised) => {
-                        let decision = resolve_effort(effort, &advertised);
-                        match decision {
-                            EffortDecision::Unsupported { from } => {
-                                tracing::warn!(
-                                    agent = %agent_id_for_mint,
-                                    effort = %from,
-                                    valid = ?advertised.levels,
-                                    "configured effort is below the lowest advertised effort level; skipping"
-                                );
-                                EffortDecision::Unsupported { from }
-                            }
-                            EffortDecision::Skip => EffortDecision::Skip,
-                            decision @ (EffortDecision::Apply { .. }
-                            | EffortDecision::FellBack { .. }) => {
-                                Self::apply_effort_walkdown(
-                                    cx,
-                                    &id,
-                                    &agent_id_for_mint,
-                                    decision,
-                                    &advertised.levels,
-                                )
-                                .await
-                            }
-                        }
-                    }
-                    None => {
-                        if let Some(effort) = effort {
-                            tracing::warn!(
-                                agent = %agent_id_for_mint,
-                                effort = ?effort,
-                                "agent advertised no effort option; skipping configured effort"
-                            );
-                        }
-                        EffortDecision::Skip
-                    }
-                };
-                tracing::info!(
-                    "{}",
-                    resolved_log_line(&agent_id_for_mint, &model_current, &effort_outcome)
-                );
+                .await
+                .map_err(|err| match err {
+                    ApplyConfigError::NotAdvertised(err) | ApplyConfigError::Rejected(err) => err,
+                })?;
+                *entry.config_surface.lock().expect("config_surface lock") =
+                    Some(refreshed_surface);
 
                 // (5) Record the cwd that was actually used to mint this session so
                 // the immutability guard below can compare future requests against
@@ -4595,6 +4710,38 @@ mod tests {
         );
     }
 
+    #[tokio::test]
+    async fn mint_populates_config_surface_cache_with_refreshed_opts() {
+        let rec = Recorder::new("agent-sess-CACHE");
+        let be = connect_recording(rec.clone()).await;
+        let key = bkey("bridge-CACHE");
+
+        be.configure_session(
+            &key,
+            &SessionSpec::from_config(EffectiveConfig {
+                model: Some("m".to_string()),
+                effort: Some(Effort::High),
+                mode: None,
+            }),
+        )
+        .await
+        .unwrap();
+        be.ensure_session(&key).await.unwrap();
+
+        let entry = be.session_entry(&key).await;
+        let surface = entry
+            .config_surface
+            .lock()
+            .expect("config_surface lock")
+            .clone()
+            .expect("mint must cache the refreshed config surface");
+        assert_eq!(select_current(&surface.opts, "model").as_deref(), Some("m"));
+        assert_eq!(
+            select_current(&surface.opts, "effort").as_deref(),
+            Some("high")
+        );
+    }
+
     #[tokio::test]
     async fn forget_session_drops_stash_falls_back_to_static_config() {
         // After `forget_session`, the stash entry is gone, so the NEXT mint falls

```
