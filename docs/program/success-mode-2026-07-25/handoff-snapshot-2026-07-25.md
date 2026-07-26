# HANDOFF — failure-mode mitigation program — 2026-07-25 (live doc)

## NEXT PASS: SUCCESS-MODE PROGRAM (owner-approved 2026-07-25 ~23:55 — START HERE after compaction)

Owner directive: the program has focused on preventing failure modes and mitigating
weaknesses; the next pass REINFORCES SUCCESSES — identify what works, operationalize it,
promote it. Same pipeline shape as the failure program, inverted: mine success signatures →
validate (exp-NN where causal claims need it) → operationalize (steering rules via SSOT
carrier, prompt/workflow templates, bridge features, detectors) → promote with owner
sign-off.

**Kickoff prompt for the next session:** Read this handoff top-to-bottom, then run the
success-mode pass: (1) curate the seed catalog below into candidate artifacts, each tagged
with its proposed operational form (steering rule / template clause / bridge feature /
detector signature / exp validation) and its evidence pointers; (2) sweep today's session +
the transcript corpus for success signatures the seed list misses (the mining/ tooling that
finds admission/frustration signatures can find their duals: attribution-control-present,
refutation-accepted, cap-honored); (3) draft the top artifacts for owner review — promotion
stays owner-gated exactly like the failure side; (4) keep servicing the in-flight bridge
queue (Task P → Task F → cleanup-2) per the resume protocol below.

**Seed catalog (validated 2026-07-25, evidence in this doc's checkpoint log + w2-tasks/):**
1. Fix-vs-redispatch decision rule: closed enumerable findings → targeted fix on the
   existing artifact (6/6 today); open-class findings (reviewer sampling an inexhaustible
   class) → STOP retrying, escalate to spec/design; fresh restart almost never optimal.
   Candidate: steering rule + bridge REJECT-classifier third arm in the convergence contract.
2. Attribution-control-before-blame: before attributing a regression, run the base artifact
   in the SAME environment (overturned wrong attribution twice: W2d 8-test batch, W2a-2
   cap failure). Candidate: steering rule + verify-pipeline feature (auto base-control on
   first-hermetic-gate failures).
3. Design-review ladder: sol draft → adversarial panel → resolutions-verified re-review →
   normative errata → charter; finding class converged coherence → code-grounding →
   wire-edge in 3 rounds. Candidate: named bridge workflow (design → spec-review loop with
   READY-TO-PLAN gate) + template.
4. Impossibility-argument-first: license premise refutation in design briefs; sol refused
   the task-as-framed and proved the frame wrong (classifier line), saving round 4+.
   Candidate: design-brief template clause (already partial in dispatch-brief contract).
5. Provenance-disclosed operator fixes: separate commits, authorship named, reviewers told
   to scrutinize the post-hoc fixes hardest — every such review engaged them specifically.
   Candidate: operator-fix protocol doc + review-input template.
6. Warm-specialist reuse: SendMessage continuation of the debug agent 3× — each round
   faster (topology context persisted); vs fresh agents re-deriving. Candidate: orchestrator
   guidance rule + measure the effect (exp).
7. Checkpoint-after-every-stage + durable evidence dirs (per-gate logs with exit codes):
   the session survived multiple gaps losslessly. Candidate: already partial discipline —
   formalize as template + schema-check extension.
8. Convergence cap declared BEFORE the round, then honored (W2b round 3): prevented churn
   the taxonomy documents at 11-14 rounds elsewhere. Candidate: steering rule + bridge
   max-round config.
9. Two-lens review with synth disagreement-resolution + per-reviewer refuted/confirmed
   accounting (codex REJECT decomposed 1 confirmed / 1 refuted / 1 scope) — reviewer
   accountability data. Candidate: detector signature + TRACKER metric.
10. Egress-catch class: enforcement gates must accept the honest degraded path or they
    incentivize fabrication (the gate blocking the compliant behavior was the bug).
    Candidate: generalize as a gate-design principle doc.

Also fold in the two failure-side nominations still pending: resource-residue-after-
completion; evidence-destroying error classification (smoke.config collapse, workflow
node failures needing RUST_LOG archaeology).

---

# ORIGINAL HANDOFF (2026-07-25 ~03:00 MDT) + running checkpoint log

Owner asleep; session near usage limit (resets ~05:00 MDT). A fresh session resumes from here.
Full evidence: `~/Documents/agent-failure-modes-2026-07-25.md`. Program tracker:
`~/code/prompts-skills-steering/TRACKER.md` ("Failure-mode mitigation waves" section).

## OWNER ACTIONS PENDING (2026-07-25 ~10:40; W2b item added ~17:00)

0. W2b RESOLVED-IN-PROGRESS (2026-07-25 ~20:45): owner ruled — mechanism redesign wins over
   round 4 of the classifier; architecture DECIDED: translator-cut + raw-record side-store at
   translator.rs:229-234 (metadata-propagation rejected unless provenance earns other
   consumers). Sol dispatched on spec v2 with the full panel verdict + findings-resolution
   table mandate (input w2b-sol-design-v2-input.md → w2b-sol-design-v2-doc.md). Then:
   charter implement task(s) (likely protocol-prerequisite + sanitizer). The three REJECTED
   classifier clones (impl-58028, impl-441) stay parked as evidence; the classifier line is
   DEAD. [Historical detail of the 3 rejected rounds: prior version of this item + checkpoint
   log.] Three review rounds,
   three REJECTs (v1: under-strip + resume bypass; v2: I'll over-strip + tool-use under-strip;
   round-3 fix: `I'm going to` path missed the new intent gate [BLOCKER, valid repro] +
   absent `sanitize_inputs` enables-by-shape on new multi-node configs [MAJOR — NOTE: my v2
   spec addendum's "derive from config, not hardcode false" wording steered the agent toward
   shape-derivation; partly a spec-authorship error, recorded]. Both round-3 findings are
   small and precisely enumerated (symmetry fix + default-false-with-snapshot-backcompat), so
   an authorized round 4 has good odds — but the oscillation pattern also suggests the
   example-driven heuristic boundary may deserve a design rethink (structural-marker-anchored
   stripping instead of line classification). Verdicts: w2b-review-verdict.md (+ the two run
   logs). Clones impl-58028 (v1) and impl-441 (v2+fix, gates all green) retained unmerged.
   This is also the cleanest convergence-contract case study of the day for TRACKER.

1. **RESOLVED 2026-07-25 ~11:20 (owner-relayed fix)** — host codex was NOT logged out; the
   bridge's AUTOMATIC auth lane invoked the advertised `chat-gpt` auth action, which hangs
   headless (`acp.authenticate.timeout`). Fix applied to w2-impl-gpt55.toml host codex entry:
   `pre_authenticated = true`, no `auth_method` (same rule as containers). Smoke now green:
   `authenticate:skipped`, exact PONG (`~/Documents/w2-tasks/codex-smoke2.txt`). Deferred codex
   correctness pass over merged W2a launched (implement-review-light → 
   `~/Documents/w2-tasks/w2a-review-codex-verdict.md`). NOTE: the in-flight W2d run loaded the
   OLD config — its reviewer_codex may still fail (claude-only review + disclosure again); the
   corrected config applies from the next launch (W2b) onward.
2. **W2a merged locally, NOT pushed** (see 10:40 checkpoint) — push feat/m4-slice3a-ownership-
   finalization when satisfied.
3. **Wave-3 taskset — DECISION NEEDED on mc-08**: the shared-code data-loss defect was repaired
   + fault-injection-witnessed (VERIFICATION.md "Curation fix"; mc-02 seed reproduces exactly;
   box 1 re-earned). Fresh-model probes (box 3): seeded 5/5 findable with correct citations;
   clean mc-06/mc-07 survive; REPAIRED mc-08 still REJECTed on severity-inflation judgment
   calls (no real defect found) — as a clean twin it now sits at the APPROVE/REJECT boundary.
   Full analysis + 3 options (harden error paths [bar-aware], re-score on findings-vs-bars,
   or drop to 7 items): tasksets/mechanism-claims-v0/PROBE.md. Box 3 withheld; box 4 yours;
   exp-w3a NOT run (its own header gate) — everything else is run-ready. Side-finding for
   TRACKER: sonnet severity tags varied SMELL↔WRONG on identical twin code — wrong-vs-smell
   steering binding-power datum.
4. RESOLVED + EXECUTED (2026-07-25 ~20:10): owner approved promoting "Verify before done"
   with an egress catch (environments that can't run the full suite report the runnable
   subset + exclusions in the done-claim — never silently skip). Carrier amended; REAL
   ROLLOUT DONE: all three targets byte-identical at sha 990bf12c… (~/.claude/CLAUDE.md,
   ~/.codex/AGENTS.md, ~/.kiro/steering/ssot.md — the bare-Kiro gap is CLOSED). Backups:
   ~/Documents/w2-tasks/ssot-backups-2026-07-25/. Future edits: carrier →
   tools/emit-instructions.mjs. ENFORCEMENT PARITY BUILT (2026-07-25 ~21:00, all
   uncommitted/untrusted — owner enables): codex Stop verify-gate
   (~/.codex/hooks/verify_gate_codex.sh + hooks.json, claude-parity loop guard, egress catch
   BUILT IN) + repo .codex brief-lint (Agent|spawn_agent, warn-only); kiro via agent configs
   (~/.kiro/agents/enforced.json + repo enforced.json carrying BOTH hooks — kiro shadows,
   doesn't merge); brief_lint + schema-check gained --codex-hook/--kiro-hook. Self-tests
   14/14 ×2; gate matrix 18/18; kiro validate rc 0. ENABLE STEPS + gaps G1-G9:
   ~/Documents/CODEX-KIRO-HOOKS-2026-07-25.md (codex /hooks trust — old hash pin
   deliberately stale; kiro set-default enforced + enableDelegate). ONE OWNER DELTA: the
   CLAUDE gate (verify_gate.sh) lacks the egress catch — ~6-line backport documented, NOT
   applied (it is your live Stop gate; your call).
4b. Phase-5 stop-hook: --hook mode BUILT + self-tested + timed (0.03-0.05s), uncommitted in
   prompts-skills-steering; prep note fully updated with the final snippet. Enabling = your
   one-line edit, BUT both repos' VERIFICATION.md currently carry live findings (warn at
   every stop until fixed/accepted) and /VERIFICATION.md sits in .git/info/exclude in both
   (discovery handles it). See ~/Documents/PHASE5-STOPHOOK-PREP-2026-07-25.md caveats.
5. RESOLVED (2026-07-25 ~23:10): cleanup-1 MERGED (e3f90e8 ten-item batch + 5b1b97a
   cache_key fix; two-reviewer REJECT was solely the E0382, fixed + light-review APPROVE
   with race-safety confirmed; gates green). Clears: W2a MINORs (exhaustiveness test,
   breadcrumb assertion, preflight single-flight hardening), W2d MINORs (effort-drop WARN,
   suffix-const unification, set_model + effort-only tests), W2c MAJORs (R3/R4 tokenizer,
   artifact persistence), constants hygiene (schedule-schema + dead-code preflight). Branch
   now 9 commits ahead, UNPUSHED since your earlier push (push again when ready). Remaining
   known non-merged work: smoke-subcommand 2 defects (cleanup-2, needs root-cause) + W2b
   attested-prefix implementation (chartering pending panel round 3).
6. **DISK: host hit 100% during hermetic debugging** (now ~11 GiB free after the debug agent
   cleaned only its own residue + two rebuildable clone target/ dirs). ~375 GB reclaimable in
   pipeline warm-cache docker volumes (`docker system df`) — decide a reap policy
   (`a2a-bridge containers reap` covers containers, not these named cache volumes).

## CHECKPOINT LOG (newest first — update as stages complete)

- 2026-07-25 23:45 MDT — **INSTRUMENT-CLOBBER INCIDENT (mine) + SYSTEMIC FINDING + Task P
  round-2 REJECT.** (a) The 4b smoke-claude ACP check PONG'd, then its Stop-gate servicing
  OVERWROTE ~/code/prompts-skills-steering/VERIFICATION.md (claude lane read-only is
  prompt-contract-only; I pointed session-cwd at a real repo instead of .b2a-scratch —
  dispatch error, mine). Recovery: 3 channels negative (no APFS snapshots; no transcript
  Write of prior content; no captured read). LOSS BOUNDED: VERIFICATION.md is an ephemeral
  per-session stop-artifact (79619797 shows routine `rm -f VERIFICATION.md`), pre-clobber
  content was already schema-noncompliant history. Smoke's version left in place (true
  record of last session); clobber copy + recovery scripts in success-mining/.
  (b) SYSTEMIC: ALL ~85 retained implement clones carry VERIFICATION.md — host claude ACP
  sessions (reviewers) run under the user Stop gate EVERYWHERE; the gate fires + gets
  serviced every claude review turn. Bridge finding: claude host lanes need hook isolation
  (or session-scoped settings) — queue for cleanup-2/owner; ALSO the smoke agent complied
  with the egress-catch teaching text exactly (S10 validation datum). NEW HARD RULE: any
  ACP smoke/instrument uses session-cwd ~/code/.b2a-scratch, NEVER a real repo.
  (c) Task P attempt-2 review REJECT (log tail): "no production path enables the nonce
  contract" BLOCKER + fenced-marker criterion "INVERTED in code and tests" (MAJOR) +
  sibling-binary unbuilt (MAJOR) + PATH-based child resolution vs pinned-child (MAJOR).
  Oscillation on fenced-marker = likely MY task-spec KEEP line contradicting design
  §13/§17.16 STRIP (W2b-v2-shaped spec-authorship error). Final attempt running (1h58m).
  At terminal: adjudicate spec-contradiction FIRST (check §13/§17.16 vs
  w2b-taskP-wrapper.md acceptance line), own the error, correct the spec before any fix
  round.

- 2026-07-25 23:05 MDT — **ALL SIX MINING SLICES IN + INSTRUMENT-CONTAMINATION FIXES
  APPLIED (owner: apply 1, approved 2-4).** Reports persisted: report-slice{A..F}.md under
  ~/Documents/success-mining/ (C/D/F persisted by orchestrator — subagent Write is
  harness-blocked for report files). Pool ≈45 candidate patterns + failure noms.
  FIXES: (1) harness claude executor isolated — claude_cli.py passes --settings
  isolated_settings.json ({}), Skill added to DISALLOWED_TOOLS, new test
  test_executor_child_is_isolated_from_user_settings, providers 27/27 (covers
  promptfoo_claude via run_claude; exp-w3a executor = claude-sonnet-5 was exposed).
  (2) PROBE.md instrument rule appended (fixed-token probes: isolated settings + assert
  token; prose = INSTRUMENT_CONTAMINATED). (3) ~/.claude/settings.json SessionStart
  command wrapped with `[ -n "$CLAUDE_INSTRUMENT_CHILD" ] && exit 0;` guard (backup:
  ssot-backups-2026-07-25/settings.json.pre-instrument-guard; both branches sh-validated;
  interactive sessions unaffected). (4a) OBSERVATION: the hook's bunx cache path
  (/private/var/folders/.../bunx-501-moshi-hooks@latest/) is ABSENT — new interactive
  sessions may already be silently hook-less (async:true hides it), or superpowers arrives
  via the plugins dir; owner should glance at next interactive session. (4b) smoke-claude
  ACP-lane check dispatched — NOTE: non-discriminating for hooks-honored right now (guard
  var set AND cache absent); a PONG only confirms lane health, prose would prove
  plugin-path injection. TRIAL DATA: slice-F citation spot-check 4/4 verbatim at cited
  lines (cfb7783b 4428/4470/5001/5049). NEXT: S11 reasoner-pass eval (E+F), full pool
  curation, Task P terminal (fix rounds still running).

- 2026-07-25 22:05 MDT — **S11 TRIAL SLICES DISPATCHED (owner-directed).** Two more miners:
  luna → slice E (a2a-bridge project corpus: 13 claude 14d + 64 codex, r2f excluded),
  sonnet → slice F (slicing/prism 60d: 14 claude + 407 codex, never-mined codex portion;
  f14884e6 knowns skipped). Both briefs enforce the S11 trial structure: EVIDENCE
  (file:line + verbatim quotes ×2-3) strictly separate from INTERPRETATION, findings too
  thin marked EVIDENCE-THIN — so a reasoner (fable/opus/sol, owner picks at eval time) can
  judge from citations alone. Trial metrics recorded in catalog S11: citation validity,
  evidence sufficiency, acceptance rate, novel-vs-known. Slice F cwd sanity-probed before
  dispatch (407=407 coincidence with slice B ruled out: 0 file overlap, spot-checked cwds
  all ~/code/slicing). Six miners now in flight (A sol, B luna, C sonnet, D opus, E luna,
  F sonnet) + Task P fix rounds continuing.

- 2026-07-25 21:40 MDT — **WAVE S0 DONE + WAVE S1 FAN-OUT LIVE + owner approvals executed.**
  (a) Owner APPROVED operator-fix-protocol.md incl. F additions. (b) Detector dual BUILT+RUN
  (detect_success_signatures.py: 8/8 known-incident validation, exit 0, 14,150 rows /
  2,619 claude + 3,748 codex files; adoption finding: codex expect_falsify_probe saturated
  at 13.8k rows/299 sessions; qualitative rider → 9 novel patterns persisted at
  success-mining/rider-findings-2026-07-25.md; full repo suite run per verify-before-done —
  its 1 failure was OUR mc-08 residue [dir orphaned when manifest dropped it, an F1
  instance] → archived to tasksets/archive/ with provenance README, ci re-green).
  (c) S11 reader-grounds-reasoner added to catalog (owner nomination: sonnet/luna readers
  grounding opus/sol/fable reasoners; exp-s3 sketched). (d) **Mining fan-out dispatched,
  owner-directed model mix**: sol/xhigh→531 codex stockTrading+ssot rollouts; luna/high→
  never-mined implement inner loop (81 claude clone-sessions + 407 codex); sonnet→13 claude
  stockTrading; opus→31 claude ssot+orchestrator+dogfood. Briefs/protocol/file-lists under
  ~/Documents/success-mining/; reports land there. **gpt-5.6-luna VALIDATED on this login**
  (first use, smoke green). Two dispatch defects hit + fixed en route: run-workflow --input
  requires task-spec front-matter (freeform) — re-learned; and --input is SILENTLY DROPPED
  unless a node prompt contains the `{{input}}` placeholder (sol/luna round 1 returned
  "missing INPUT"; placeholder appended, both re-dispatched; silent-drop → bridge-defect
  nomination for cleanup-2: warn when --input goes unconsumed). (e) **Task P mid-run
  REJECT observed** (not terminal; fix rounds continue at 1h02m): BLOCKER fence-tracking
  KEEP-vs-STRIP in resolve_marker_text (§13/§17.16) + 3 MAJORs (flush_prompt_buffer
  reordering, latent Task-F-activation deadlock, missing parse_prefix_control_notification
  tests). ADJUDICATION NOTE: my task-spec line "agent-quotes-marker in fences → KEEP" may
  CONTRADICT design §13/§17.16 (STRIP for unique unescaped in-fence marker) — check at
  terminal; if so it is a spec-authorship error (mine), disclose like the W2b v2 incident.

- 2026-07-25 20:50 MDT — **SUCCESS-MODE PASS STARTED** (post-compaction). CLOCK NOTE: this
  entry is real wall-clock; the four entries below stamped 21:20-23:40 were written with a
  fast clock (their events actually ran ~19:15-20:30 MDT — witness: Task P process start
  20:12 vs its "23:40" dispatch entry). Order is still newest-first. Task P confirmed ALIVE
  (PID 15079, launched 20:12, clone impl-15079-lv7uhzla; quiet log normal at this phase).
  Executed while it cooks: (1) **Task F spec WRITTEN** (w2-tasks/w2b-taskF-sanitizer.md —
  from spec §15.2 + §18 items 1/4/5; carries the executor.rs:2552 seam correction, the
  audit-regardless-of-ok criterion, the run()-wrapper choice + ~14 translator test-site
  blast radius, and re-locate-by-structure since Task P will shift line numbers; dispatch
  ONLY after Task P merges — sequential discipline). (2) **Success catalog v1 DRAFTED** →
  ~/Documents/agent-success-modes-2026-07-25.md: 10 seeds curated with form/evidence/
  priority (NOW: S1+S8 "Convergence discipline" steering draft, S2 "Attribution control"
  steering draft, S10 honest-degraded-paths principle doc — full texts in §2, NOT applied,
  owner sign-off queue in §4; EXP: warm-reuse exp-s1, steering-text exp-s2; F1/F2 routed to
  failure taxonomy). (3) **TRACKER success-mode section added** (uncommitted). (4)
  **Detector-dual build DELEGATED** (background agent): detect_success_signatures.py — 6
  detectors, known-incident validation vs today's session, baseline+nominations, plus a
  qualitative rider for novel patterns in top historical sessions; uncommitted; report
  pending.

- 2026-07-25 23:40 — **READY-TO-PLAN** (round-3 panel verdict, w2b-v3-rereview-verdict.md):
  all round-2 findings verified FIXED; residue = dictated punch-list (fan-in seam is
  executor.rs:2552 NOT the cited ranges — "silently fails multi-node" trap; 2 named
  pre-coding decisions with prescribed patterns; ok=false audit obligation; run() wrapper
  test blast radius; jsonrpc.rs:2341 citation) — folded into the spec as §18 NORMATIVE
  ERRATA. Spec CHECKED INTO REPO (docs/design/attested-prefix-cut-v3.md, commit 1d94680,
  PUSHED). Cleanup-1 merged earlier (e3f90e8+5b1b97a, pushed). **TASK P DISPATCHED**
  (w2b-taskP-wrapper.md → w2b-taskP-run.log; wrapper + marker + capability plumbing;
  KEEP-everywhere until Task F). Task F queues behind P (spec §15 + §18 items 4-5). Then:
  cleanup-2 (smoke subcommand pair). Owner-interactive still pending: codex /hooks trust;
  kiro login + set-default.

- 2026-07-25 22:50 — SOL V3 LANDED (1538 lines): round-2 findings ALL resolved code-anchored
  (fan-in path pinned executor.rs:1693-1752/2427-2507; side-store trait+DDL+HarvestAudit
  PersistFailed; synthetic text fully classified; serde attrs; nonce-specific marker grammar
  + backslash-parity escaping with zero/multiple/empty-suffix → KEEP; wrapper private
  handshake + _meta; 16-rule acceptance principle incl. store-before-release + no-semantic-k
  rule; Task P/F charters in §15). ROUND-3 PANEL RE-REVIEW DISPATCHED (scrutiny incl.
  chunk-boundary/split-marker wire holes) → w2b-v3-rereview-verdict.md. Also in flight:
  cleanup-1 cache_key fix light review (gates were green). CLEANUP-1 state: ten-item batch
  d969cb7 + one-line E0382 fix committed on clone impl-24382; merge on APPROVE.

- 2026-07-25 22:15 — OWNER BATCH 2 EXECUTED: (a) EGRESS BACKPORT LIVE in
  ~/.claude/hooks/verify_gate.sh (env-limited marker + named exclusion accepts; reason text
  teaches the compliant form) — 4/4 synthetic Stop cases pass (allow/block/unchanged/block,
  JSON-valid), syntax-checked, backup at ssot-backups-2026-07-25/verify_gate.sh.pre-egress.
  (b) KIRO: chat.enableDelegate=true took (workspace scope); set-default BLOCKED on host
  login (kiro-cli not logged in on host — owner: `kiro-cli login --use-device-flow` then
  `kiro-cli agent set-default --name enforced`, or use --agent enforced per chat). (c) B1
  DECIDED = adapter-boundary sentinel (owner); (d) V3 DISPATCHED to sol with the sentinel
  contract requirements (marker collision→KEEP semantics, wrapper contract, prompt-contract
  half, capability = the wrapper) + B2-B5 + m1-m4 → w2b-sol-design-v3-doc.md. cleanup-1
  still in flight (attempt 2/review).

- 2026-07-25 21:50 — V2 RE-REVIEW: NOT-READY; Task P + Task F both NOT-CHARTERABLE. Round-2
  findings are spec-to-CODE grounding gaps, all code-anchored + enumerable: B1 codex channel
  roles ABSENT from the ACP schema (Task P's only capable backend can't express attestation
  on today's wire — may need codex-acp fork / adapter wrapper / in-adapter sentinel — OWNER
  INPUT NEEDED, gates v3); B2 fan-in effective-body delivery path unnamed; B3
  capability/turn-id API hooks unnamed; B4 side-store trait/DDL/error-variant unspecified;
  B5 synthetic bridge text unclassified; plus code-confirmed MINORs (serde default attr on
  WorkflowNode graph.rs:49; run_id-across-resume audit semantics; 3 named change sites;
  saw_text_delta branch guard at translator.rs:229-234). Trend is CONVERGENT (coherence →
  grounding). v3 dispatch HELD on the B1 fork decision. cleanup-1 still live (attempt 2,
  review phase). Verdict: w2b-v2-rereview-verdict.md.

- 2026-07-25 21:20 — SOL SPEC V2 LANDED (w2b-sol-design-v2-doc.md, 749 lines): all 16 panel
  findings mapped in a resolution table — B2 resolved by ELIMINATING separators (bridge
  emits zero bytes, no gap exception), B3 via per-backend capability contract (codex
  capable; claude/kiro declared incapable + diagnostic), M1 committed to UTF-8 String bytes,
  M2 via >90%-prefix suspicious-attestation KEEP guard + trust boundary, M9 via
  transactional translator-side raw+decision store (store-commit BEFORE artifact emission),
  9-case decidable acceptance principle, Task P (backend prerequisite) + Task F (translator
  sanitizer+audit) decomposition with per-task criteria. RE-REVIEW DISPATCHED (panel round
  2: verify each claimed resolution real-vs-hollow, scrutinize the NEW material hardest,
  charter verdicts per task) → w2b-v2-rereview-verdict.md. Charter implement tasks on
  READY-TO-PLAN. Also in flight: cleanup-1 implement (running ~100min — watch).

- 2026-07-25 20:30 — PRESSURE TEST VERDICT on Attested Prefix Cut (two-reviewer spec-review,
  w2b-design-pressure-test-verdict.md): mechanism SURVIVES (nobody broke the attestation
  concept; impossibility argument holds in scoped form per m1 — bounded lexical stripping
  isn't impossible, just a weaker different product), but spec NOT READY TO PLAN — 3
  BLOCKERs: B1 feasibility claim ADJUDICATED FALSE in-source (Update::Text(String)
  everywhere, ports.rs:22-29, zero provenance) ⇒ prerequisite MANDATORY and forks into
  translator-cut (~2 files + per-backend, journal loses pre-cut text) vs
  metadata-propagation (5+ crates, preserves raw records) — OWNER CHOICE; B2 "bridge-owned
  separators" undefined; B3 per-backend attestation API unspecified. MAJORs: byte-contract
  vs UTF-8 String pipeline; bad-attestation trust bounds; recovery-path entanglement (M9);
  explicit "v1 does not strip legacy unannotated outputs" statement. Findings are CLOSED
  and ENUMERABLE ⇒ per today's decision rule this is fix-the-findings territory: on owner's
  B1 pick, send sol a revision round with the panel verdict, then charter the implement.
  Operator recommendation: translator-cut + raw-record side-store at the translator seam
  (m3 names it: translator.rs:229-234) — proportionate to a default-OFF mitigation;
  propagation only if segment provenance gains other roadmap consumers.

- 2026-07-25 19:20 — SOL DESIGN LANDED: "Attested Prefix Cut v1"
  (w2-tasks/w2b-sol-design-doc.md, 247 lines). Core: impossibility argument (no text-only
  classifier can satisfy never-truncate) → producer-attested process|deliverable segments as
  transport metadata; bridge cuts only a validated leading process run; all fallbacks KEEP;
  safety theorem + decidable 3-case acceptance principle + property/fuzz test plan. REFUTES
  both the per-line classifier AND the marker-anchored candidate (its "reserved out-of-band
  commit token" variant collapses INTO this protocol). Named residual: producer
  mis-attestation (bounded: non-empty deliverable suffix required). Load-bearing feasibility
  claim: single bridge task ONLY IF finalization already exposes channel/segment provenance
  (else protocol prerequisite; flat strings ⇒ honest passthrough). Spec-level verdict: any
  acceptance test demanding bare-string stripping contradicts the invariant — reframes W2b's
  original spec. PRESSURE TEST DISPATCHED per owner: spec-review two-reviewer panel
  (draft→refine ×2 + synth) with repo access to verify the feasibility claim in source;
  input w2b-design-pressure-test-input.md → verdict w2b-design-pressure-test-verdict.md.
  Still in flight: cleanup-1 implement; validator --hook agent.

- 2026-07-25 18:55 — OWNER DECISIONS EXECUTED (batch): (2) branch PUSHED to
  github.com:shoedog/a2acp feat/m4-slice3a-ownership-finalization. (sol) SMOKE VALIDATED via
  run-workflow impl-smoke lane: sol[xhigh] in-container mints + PONGs (effort_applied:true,
  fell_back:false) — W2d acceptance closed; the `smoke` SUBCOMMAND itself has 2 defects
  (container-agent model-override config failure at prompt_start + classifier discards the
  underlying ConfigX message) — queued for cleanup-2 after root-cause. (3) mc-08 DROPPED from
  v0: manifest + both exp yamls updated, base rate 0.714 documented, PROBE.md resolution
  appended; exp-w3a now gated ONLY on bar sign-off (box 4). (0) W2b sol MECHANISM RETHINK
  DISPATCHED (design task via new sol-design workflow in sol-smoke.toml; brief
  w2b-sol-design-brief.md — open-brief, marker-anchoring labeled candidate-not-premise, 3-round
  corpus as acceptance set; out → w2b-sol-design-doc.md); pressure-test via spec-review
  workflow planned on the design doc when it lands. (5) CLEANUP-1 implement dispatched
  (10-item spec w2-cleanup-1.md: W2a/W2d MINORs incl. verify-item-3-first cache race, W2c
  tokenizer/artifact MAJORs, constants hygiene; log w2-cleanup-1-run.log). (4b) validator
  --hook mode delegated (prompts-skills-steering agent; will update the PHASE5 prep note).
  (6) TAXONOMY NOMINATION from owner: resource-residue-after-completion (clones/targets/
  volumes not reaped) is a failure mode — add to mining/TRACKER nominations; ALSO nominate:
  evidence-destroying error classification (smoke.config collapsing 4 variants + dropping
  messages; observed twice today incl. workflow node failures needing RUST_LOG archaeology).
  (4) SSOT: awaiting owner ruling on promoting "Verify before done" — rule text + enforcement
  asymmetry reported (its header says enforcement lives in claude hooks/bridge verify;
  promotion adds instruction-tier everywhere incl. unenforced Kiro).

- 2026-07-25 18:35 — **W2 QUEUE COMPLETE.** W2c MERGED (0f7d80d brief-lint + 65e38a9
  cap-family fix; scoped light review APPROVE — which also spotted a FIFTH family member in
  dead code, compatibility_schedule_preflight.rs hard-coded 512MiB, added to the hygiene
  list with schedule-schema MAX_CANDIDATE_BYTES). Root cause of W2c's gate failures was the
  3rd+4th stale 256MiB constants (smoke.rs recheck misclassifying the big debug binary as
  executable drift; fallback_plan.rs divergent pair) — base failed WORSE in-container; W2c
  innocent; both-topology green post-fix. Debug agent also pre-cleared the next gate layer
  in-container (all green except one load-correlated reaper-test spawn flake — passes solo +
  reruns; watch, don't fix). Branch now 7 commits ahead of 4ab7eb6, all reviewed, all gates
  green, UNPUSHED. Final state: W2a ✓ W2d ✓ W2a-2 ✓ W2c ✓ merged; W2b PARKED at convergence
  cap (owner item 0). Remaining owner items unchanged. Binary rebuilt post-merge.

- 2026-07-25 17:40 — W2c TERMINAL at bound (clone impl-38269, commit f45f667):
  fmt/clippy/build ✓, test gate ✗ with ~17 failures across two bin suites — ALL smoke/
  runtime-guard tests (generated_smoke_refuses_*, guarded_host_smoke_never_invokes_*);
  host-side bin suites PASS (spot-verified). Review: APPROVE with 3 MAJORs-as-followup
  (R3/R4 trailing-punctuation tokenizer gaps; run-workflow artifact write missing without
  --out). Pattern-matches a THIRD hermetic-topology latent batch — container repro +
  base-control (2456a1a) + fix delegated to the warm debug agent. On clean attribution +
  both-topology green: merge → queue COMPLETE (W2b parked separately). The 3 review MAJORs
  join the cleanup-commit list (OWNER ACTIONS 5).

- 2026-07-25 17:00 — W2b round-3 REJECT → HELD FOR OWNER per the declared convergence cap
  (details + my spec-authorship contribution to the default-semantics MAJOR: OWNER ACTIONS
  item 0). Round-3 fix's host gates were all green and its clone impl-441 is retained with
  two commits unmerged. **W2c LAUNCHED** (final queue item; log: w2-tasks/w2c-run.log) —
  dispatches from HEAD 2456a1a (no W2b overlap risk: W2b is parked, not merged). Two earlier
  review-launch stumbles recorded for honesty: a shell-`&` launch that lost tracking, and a
  review input missing `## Acceptance Criteria` (the task-spec validator requires it — the
  hard-won-facts section already said so; re-learned the hard way).

- 2026-07-25 15:10 — W2b v2 ALSO REJECTED (clone impl-441-b4b0g9do, commit 9a42990): verify
  FAIL at fmt; two-reviewer REJECT with two NEW detector MAJORs — v2 OVER-strips `I'll`
  deliverable content (violates never-truncate) while UNDER-stripping `I'm using <tool>`.
  Oscillation across two attempt-sets on the fuzzy heuristic boundary = the churn pathology;
  applying our own convergence contract: ROUND 3 IS THE CAP. Targeted TDD fix delegated on the
  v2 clone (reviewer cases as tests both directions + fmt + regression guards for the v1-round
  fixes), then full gates + fresh two-reviewer re-review. If round 3 fails → W2b HOLDS for
  owner with both REJECT records. W2c stays queued (sequential discipline) until W2b resolves.

- 2026-07-25 14:20 — W2b attempt-set 1 REJECTED → RE-DISPATCHED as v2. First run terminal at
  bound (clone impl-58028, commit ce81e22): verify FAIL at clippy AND two-reviewer REJECT with
  two correctness MAJORs (narration detector under-strips `I'm <verb>` forms; serde resume
  defaults sanitize_inputs=false on pre-commit snapshots — silently bypasses W2b on
  crash-resume). Decision per handoff fork: RE-DISPATCH (defects are design-level in the
  deliverable core — outside the operator-fix envelope; run unmergeable anyway on clippy).
  v2 spec = original + the review findings as explicit requirements with refute-with-evidence
  license (w2b-v2-harvest-sanitization.md); rejected clone RETAINED untouched (provenance;
  deliberately NOT referenced in the v2 spec to avoid anchoring). v2 launched from HEAD
  2456a1a: log w2-tasks/w2b-v2-run.log. DISK CLARIFICATION: host / has 461GiB free — the
  "11GiB" pressure was the Docker VM's disk image (owner action 6 still valid for container
  verifies; host gates unaffected).

- 2026-07-25 13:55 — W2a-2 MERGED (393a6a4 preflight-dispatcher + 2456a1a cap-authority fix,
  re-authored; clone impl-78181 retained). Container-only test failure root-caused by warm
  debug agent: DUPLICATE stale MAX_EXECUTABLE_BYTES (256MiB) in compatibility_resolution.rs
  rejected the 292MB Linux debug binary at resolution load pre-output (base fails identically
  in-container — latent since e159915, NOT a W2a-2 regression; eb91aaa's cap raise had fixed
  only the compatibility.rs-side manifestations). Fix: single pub(crate) authority + canary
  test asserting the build's own binary fits the cap; both topologies green; scoped codex
  light review APPROVE (fail-closed cross-profile, release cap unchanged; verdict
  w2a2-fix-review-verdict.md); host gates pass1 OVERALL:0 (w2a2-verify/). Binary rebuilt.
  **W2b LAUNCHED** (log: w2-tasks/w2b-run.log). Queue: W2b in flight → W2c. Branch UNPUSHED
  (all known gaps now closed — push is clean pending owner). NOTE disk ~11GiB free (OWNER
  ACTIONS #6) — W2c after W2b may want a volume reap first.

- 2026-07-25 13:30 — W2a-2 TERMINAL at bound: committed eb91aaa on clone impl-78181-jzbhbjky;
  fmt/clippy/build ✓, test gate ✗ with ONE failure — compatibility_cli integration test
  `resolved_run_revalidates_generated_config_before_any_provider_spawn` (CLI child dies
  in-container BEFORE writing the drift aggregate; host-side suite 25/25 GREEN, verified).
  Review: two-reviewer APPROVE (synth resolved the one MAJOR via Reviewer B's second-pass
  refutation). MERGE HELD (unlike W2d: this commit TOUCHED the failing subsystem — it raises
  MAX_EXECUTABLE_BYTES to 512MiB under debug_assertions, and earlier attempts show more
  compatibility_cli failures that the cap-raise fixed, leaving this one; Linux debug binaries
  embed DWARF so the container binary may exceed even 512MiB — OR it's the spawn-time strict
  path the validator fix intentionally kept). Container repro + base-control + minimal fix
  delegated BACK to the warm W2d debug agent (has the topology). Log: w2-tasks/w2a2-run.log.
  On clean attribution + fix + both-topology green: merge, then W2b.

- 2026-07-25 12:40 — W2d MERGED (both commits: `8cbff56` model-selection + `71a4245` validator
  fix, re-authored onto feature branch; clone impl-51238 retained) on a CLEAN TWO-REVIEWER
  **APPROVE** (first full two-lens review since codex auth fix; verdict
  w2-tasks/w2d-review-verdict.md; 5 MINORs, none gating — top: add WARN diagnostic for
  intentional mint-time effort drop in mixed catalogs). Reviewers confirmed the validator fix's
  security contract (no earlier-fail dependency lost) and ANSWERED the spec's open thread:
  gpt-5.5 "survived" the legacy container path because sol's death was the pre-session
  `authenticate("chat-gpt")` call in an already-authenticated container — the SAME auth-lane
  mechanism as today's host incident; note at docs/superpowers/2026-07-25-w2d-codex-acp-
  models-note.md in the clone/merge. Host gates pass1 all green (w2d-verify/pass1). Binary
  REBUILT post-merge. **W2a-2 LAUNCHED** (log: w2-tasks/w2a2-run.log). Queue: W2a-2 in flight
  → W2b → W2c. Branch still UNPUSHED (owner call; W2a-2 = the last gap before push is clean).
  sol-in-container can be smoke-tested any time (W2d's whole point) — suggest after W2a-2.

- 2026-07-25 12:15 — W2d ATTRIBUTION CORRECTED + FIX COMMITTED + RE-REVIEW PREP. The 8
  compatibility_schedule* failures are NOT a W2d regression — debug agent proved base e8ed61f
  fails IDENTICALLY inside the hermetic container (my 11:45 "green at e8ed61f ⇒ W2d broke it"
  inference was environment-confounded: that green was HOST-side). TRUE root cause: latent
  validator bug (landed 2026-07-18) — the identical-path verify mount FABRICATES the trusted
  cwd root inside the container, so resolve_trusted_session_cwd's root-absent hermetic hatch
  never engages and leaf canonicalize ENOENTs; W2d was simply the FIRST commit to reach the
  hermetic test gate (all earlier attempts died at clippy). Fix committed SEPARATELY on the
  clone (4678088, compatibility_schedule.rs +108/−5: absent-leaf → static-identity helper,
  existing-path strictness kept, pinning test; provenance = debug agent + operator, disclosed).
  Container-topology proof: pre-fix 8 fail / post-fix 784 pass / base control 8 fail. ONE
  behavioral delta for reviewers/owner: nonexistent declared cwd passes foundation LOAD
  statically, surfaces later at spawn/admission. Host gates pass1 running
  (w2-tasks/w2d-verify/). Next: gates green → two-reviewer implement-review (corrected codex
  config; input w2d-review-input.md, diff HEAD~2..HEAD) → merge both commits → launch W2a-2.
  GENERALIZABLE HARD-WON FACT: identical-path container mounts defeat "path-absent ⇒ hermetic"
  detection hatches; any hermetic verify of trees PREDATING 4678088 shows these same 8 failures.

- 2026-07-25 11:45 — W2d run TERMINAL at bound: committed fc5627e; fmt/clippy/build ✓, test ✗
  (8 compatibility_schedule* — attribution CORRECTED at 12:15, see above). Review APPROVE
  claude-only, 6 MINORs. Log: ~/Documents/w2-tasks/w2d-run.log.

- 2026-07-25 10:40 — W2a MERGED as `e8ed61f` (cherry-pick -n FETCH_HEAD 1a2dcef + commit -C
  --reset-author onto feat/m4-slice3a-ownership-finalization @ 4ab7eb6); clone RETAINED (not
  reaped) as provenance backup. Review basis: standalone implement-review VERDICT **APPROVE**
  (~/Documents/w2-tasks/w2a-review-verdict.md) — DISCLOSED DEGRADATION: reviewer_codex died at
  auth (host codex auth DOWN, see OWNER ACTIONS); synth = claude reviewer only, which verified
  all three post-hoc fixes correct and found 3 MINORs (listed in OWNER ACTIONS #5; non-gating
  per severity-aware convergence contract; review is ADVISORY per config — operator accepted).
  NOT pushed. Debug binary REBUILT post-merge (so the pipeline itself now runs with W2a's
  empty-final protections) and **W2d LAUNCHED** via implement (log:
  ~/Documents/w2-tasks/w2d-run.log). Queue: W2d in flight → W2b → W2c.

- 2026-07-25 09:55 — PHASE-4 PREP COMPLETE (uncommitted in ssot-agents): carrier
  instructions/always-on/INSTRUCTIONS.md (byte-copy of current ~/.claude/CLAUDE.md incl. H1 —
  flagged as owner decision), driver tools/emit-instructions.mjs (staging-only, refuses real
  global paths, --check diff mode), staged outputs under out/staging/ all byte-identical
  (sha 5a0b4438…), --check: claude SAME / codex DRIFT (extra rule) / kiro DRIFT (missing).
  Owner note: ~/Documents/PHASE4-SSOT-PREP-2026-07-25.md. Real emission = owner decision only.

- 2026-07-25 09:50 — W2a ROOT CAUSE FOUND + ALL GATES GREEN + REVIEW IN FLIGHT. Test hang root
  cause (debug subagent, probe-confirmed): the CheckpointOwner test stub returned a bare
  `Done{end_turn}` with no text — under the commit's new policy that IS an empty-final failure →
  fresh-session retry → stub's single Notify permit already consumed → parked → checkpoint write
  never attempted → no sink error → no cancel → sibling never drained. Fix: fixture-side
  (stub emits Text before Done), preserving both the feature semantics and the test's contract —
  the intended-behavior-change-bites-test case the spec predicted; original agent never saw it
  (no attempt survived past clippy). Pass3 host gates: fmt/clippy/build/test ALL EXIT 0 (70
  workspace suites ok; evidence pass3/). Three post-hoc fixes amended into single commit
  `1a2dcef` (was c9e27cf) atop 4ab7eb6. Standalone two-reviewer review RUNNING:
  `run-workflow implement-review --session-cwd <clone>` with provenance-disclosure input
  (~/Documents/w2-tasks/w2a-review-input.md), verdict → ~/Documents/w2-tasks/w2a-review-verdict.md.
  On APPROVE: manual merge (fetch + cherry-pick -n + commit -C FETCH_HEAD --reset-author, reap
  clone) then LAUNCH W2D. Note the clone-id in any merge now refers to commit 1a2dcef.

- 2026-07-25 09:45 — PHASE-4 ASSESSMENT DONE (read-only agent): @ssot/compiler is
  READY-WITH-SMALL-GAPS. Profile agent-instructions-portable-v1 already emits one carrier
  byte-exact to CLAUDE.md/AGENTS.md/.kiro/steering/ssot.md (user scope = exactly the three
  hand-duplicated files), tested cross-target. Missing: only a small driver (no CLI/materializer
  by design; dogfood test b3 is the template). CONSTRAINTS for owner: outputs byte-identical
  across targets (no per-target rule scoping — multi-day gap if needed); Kiro filename fixed
  ssot.md. DRIFT FOUND: ~/.codex/AGENTS.md has a third rule ("Verify before done") absent from
  CLAUDE.md; ~/.kiro/steering/ is EMPTY. Owner decisions: promote-or-drop the third rule; accept
  identical steering across targets. Prep agent now drafting carrier + staging-only driver +
  owner note (~/Documents/PHASE4-SSOT-PREP-2026-07-25.md); real-file emission stays owner-gated.

- 2026-07-25 09:35 — W2a gates pass2: fmt/clippy/build GREEN after the two operator fixes; test
  gate 1 failure: bridge-coordinator detached_checkpoint_failure_flushes_inflight_sibling_
  before_terminal_failure — DETERMINISTIC (5/5 isolated, parks forever: 30s timeout probe also
  fails; passes at base HEAD~1 in main repo 0.01s). Ruled out with evidence: flake, slow-path
  (no new time constants), cancel-turn-misclassified-EmptyFinal (executor.rs:1112 ok-guard),
  severed cancel token (no token-plumbing changes). Open: post-cancel cleanup-ownership awaits
  (canceled arm now awaits on_exit_observed before breaking) vs pre-stream await outside cancel
  select. Root-cause+minimal-fix DELEGATED to subagent (probe-milestone method; verification
  bar: single test + bridge-coordinator + bridge-workflow suites + clippy green; no commits).
  SECOND subagent concurrently execution-verifying tasksets/mechanism-claims-v0 (checklist
  boxes 1-2 + witnesses; exp-w3a stays un-run until that lands). Evidence dir:
  ~/Documents/w2-tasks/w2a-verify-attempt4/pass2/.

- 2026-07-25 09:20 — W2a RECOVERY VIA OPERATOR FIX (resume path DEAD: `--resume` refused —
  "run already handed off (terminal phase)"; it only serves stranded runs). Agent's commit c9e27cf
  had TWO defects: (1) dead `unreachable!()` at executor.rs:2033 (its new all-diverging EmptyFinal
  match arm made the old post-loop guard unreachable; -D warnings) — fixed by deleting the line,
  the `!`-typed attempt loop is now the labeled block's tail; (2) missed match site: test helper
  `table_key` in bridge-controller/src/resilient.rs lacked the new `BridgeError::EmptyFinal`
  variant (E0004, only surfaced once bridge-workflow compiled) — added `=> "EmptyFinal"` arm +
  explicit `(EmptyFinal, Death::Fatal)` test case (Fatal at controller layer BY DESIGN: executor
  owns the single fresh-session retry; ResilientWarm must not nest-retry). BOTH FIXES ARE
  OPERATOR-AUTHORED (provenance tier: operator, not agent) — flag to reviewers/owner. lib
  `classify_death` needed no change (wildcard → Fatal, correct). Host-side verify gates
  (identical cmds to hermetic [verify] profile) running in bg: evidence in
  `~/Documents/w2-tasks/w2a-verify-attempt4/` (pass1: fmt ✓, clippy ✗ at resilient.rs; pass2 in
  flight). Plan: gates green → amend into c9e27cf (pipeline convention) → standalone two-reviewer
  review via `run-workflow implement-review --session-cwd <clone>` → APPROVE → manual merge per
  the run's printed fetch/cherry-pick instructions (merge-subcommand gates on stored verdict).

- 2026-07-25 09:15 — W2a TRUTH CORRECTION + RESUME (attempt 4 in flight). Attempt 3 did NOT
  complete cleanly (a prior session line claimed it did — unverified self-claim, failure mode #1).
  Actual outcome per its stdout (`bm2bfffto.output`, finished ~03:49): committed c9e27cf on
  implement/impl-81776-qo3xg4zy, but hermetic verify FAILED at clippy (`unreachable!()` at
  crates/bridge-workflow/src/executor.rs:2033 unreachable because all match arms diverge; -D
  warnings), review incomplete, 3-attempt bound reached. NOTHING merged (repo top still 4ab7eb6).
  Clone confirmed clean on its branch; impl-87813/impl-80568 are the OTHER agent's r2f0a clones.
  Resumed 09:14 with the CORRECTED config (pre_authenticated=true):
  `a2a-bridge implement --resume impl-81776-qo3xg4zy --config ~/Documents/w2-tasks/w2-impl-gpt55.toml`,
  durable log: `~/Documents/w2-tasks/w2a-resume-attempt4.log`. On VERDICT: Approved → operator
  merge; REJECT → read review, decide. Queue unchanged: W2a → W2d → W2b → W2c.

- 2026-07-25 03:25 — WAVE-3 DRAFT COMPLETE (uncommitted in prompts-skills-steering): exp-w3a-cite-or-label.yaml + exp-w3a-negative-control.yaml (exp-d7 shape, loads clean), artifacts/elements/cite-or-label/steering.md (115 tokens), tasksets/mechanism-claims-v0/ (8 items mined from real incidents, 5 seeded/3 clean twins, base rate 0.62, check_taskset + pytest ci 3/3 PASS; labeled v0-seed-unverified with promotion checklist), experiments/exp-w3-queue.md (moves 2-5: w3c/w3e not harness-expressible — toolless single-turn executors; w3e proposed as observational/bench). Phase-3 next step: execution-verify mechanism-claims-v0 items, then run exp-w3a.

- 2026-07-25 03:00 — HANDOFF WRITTEN. W2a attempt 3 IN FLIGHT (see below). Wave-3 drafting agent
  still running. W2d/W2b/W2c queued. Phases 3-5 not started.

## State

**DONE and pushed (all four repos, main):** Wave 0 (failure-signature detector + triage queue +
daily 07:00 cron; prompts-skills-steering `87a744c`/`bc819b2`, merges `b0e70a1`), Wave 1 (a2acp
merge `9aa1c666`: 15 prompt-template edits + `prompts/dispatch-brief-contract.md`; quant-platform
`1723ec9`: CLAUDE.md hooks truthing + brief-lint PreToolUse hook; ssot-agents `cfe4cc8`: first
repo brief + hook). Main merged INTO both feature branches (a2a-bridge `4ab7eb6` — README
conflict resolved as union, cargo check green; stockTrading clean). Wave 2 validators live:
`~/code/prompts-skills-steering/validators/{brief_lint,cite_check,verification_schema_check}.py`
(all `--self-test` PASS), brief-lint mounted warn-only at PreToolUse[Task|Agent] in
stockTrading + ssot-agents `.claude/settings.json`.

**IN FLIGHT at handoff time:**
1. **W2a implement run (attempt 3)** — empty-final/preflight task via
   `a2a-bridge implement`, impl agent gpt-5.5 xhigh, temp config with `auth_method = "none"`.
   Launched ~02:50 MDT from repo `target/debug/a2a-bridge`; was past warm-deps + container up
   when last checked. Its stdout: session task file (old session dir)
   `/private/tmp/claude-501/-Users-wesleyjinks/a600bea5-932b-4df8-b776-9cc84581c26c/tasks/bm2bfffto.output`
   (path survives until tmp cleanup). Newest clones at check time:
   `~/code/.a2a-implement/impl-81776-qo3xg4zy` and `impl-80568-u7nvk9ey` — ONE is W2a, the other
   belongs to the owner's OTHER bridge agent (r2f0a closure work, tmp config
   `/private/tmp/a2a-bridge-r2f0a-integrated-closure-docs.toml`). Disambiguate by
   `cat <clone>/.git/A2A_TASK.md` (W2a's title: "Trust turn outcomes — empty-final…").
   If stranded: `a2a-bridge implement --resume <clone-dir-name> --config <cfg>`.
2. **Wave-3 drafting agent** (claude subagent) — drafting `experiments/exp-w3a-cite-or-label.yaml`,
   `tasksets/mechanism-claims-v0/`, `experiments/exp-w3-queue.md` as UNCOMMITTED DRAFTs in
   `~/code/prompts-skills-steering`. If it never reported, check `git -C
   ~/code/prompts-skills-steering status --short` for its files.

**QUEUE (strictly sequential — overlapping code areas):** W2a ✓merged → W2d (in flight) →
**W2a-2 (NEW: preflight on warm dispatcher path — spec w2a2-preflight-warm-dispatcher.md,
from the post-merge codex REJECT, operator-confirmed)** → W2b → W2c.
Codex post-merge verdict adjudication (2026-07-25 ~11:30): REJECT rests on ONE confirmed gap
(preflight absent on dispatcher branch; executor.rs:1351 is the only call site — now W2a-2),
one REFUTED claim (dispatcher branch HAS full empty-final handling, executor.rs:868,1204-1213),
one scope dispute for owner (unary/translator empty-final — W2a spec'd the NODE seam), plus the
already-known MINORs. W2a merge STANDS (strictly better than base, all-green, gap is in a
default-OFF feature no config enables); branch stays UNPUSHED until W2a-2 lands or owner says
push. Reviewer-accountability datum: 1 refuted / 1 confirmed / 1 scope-dependent from a single
codex REJECT — logged for the convergence-contract evidence base.
Durable task specs + config: `~/Documents/w2-tasks/`. Launch template:

```sh
cd ~/code/a2a-bridge && target/debug/a2a-bridge implement \
  --input ~/Documents/w2-tasks/<SPEC>.md \
  --repo /Users/wesleyjinks/code/a2a-bridge \
  --config ~/Documents/w2-tasks/w2-impl-gpt55.toml --lang rust
```

After each completes: read its hand-off output; the pipeline already ran hermetic verify +
two-reviewer diff review with a VERDICT. For an Approved run the operator merge is
`a2a-bridge merge <clone-id>` (or rerun with `--merge`). Verdict REJECT → read the review, decide
fix vs re-dispatch. Do NOT trust a completed run with empty output (that's failure mode #11 —
ironically what W2a fixes).

## Hard-won environment facts (do not re-derive)

- **Bridge lanes:** `~/bridge-usage.md` is the guide. The served process on 127.0.0.1:18080 is
  direct-routing ONLY (no workflows). `implement`/`run-workflow` use a repo/tmp binary + local
  config. Current dev binary: `~/code/a2a-bridge/target/debug/a2a-bridge` (post-merge).
- **Task specs need front-matter** (`task-type: implement`) + `## Description` + `## Acceptance
  Criteria` (`a2a-bridge task-spec template implement`). Repo needs `--lang rust` (multi-marker).
- **Auth for HOST codex agents (2026-07-25, owner-relayed):** same rule as containers —
  `pre_authenticated = true`, never `auth_method`, never the automatic lane. The automatic lane
  selects the advertised `chat-gpt` auth action and invokes it, which hangs headless →
  `acp.authenticate.timeout` at the Authenticate phase (looks like stale login; is not).
  Witnesses: codex-smoke.txt (automatic, timeout) vs codex-smoke2.txt (pre_authenticated,
  authenticate:skipped, PONG).
- **Auth in containers (CURRENT semantics, post-merge):** browserless codex containers use
  `pre_authenticated = true` with the mounted `~/.config/a2a-creds/codex/auth.json`. Do NOT use
  `auth_method` for them (it now invokes an advertised auth action; combining is prohibited —
  relay from owner's bridge agent). `~/Documents/w2-tasks/w2-impl-gpt55.toml` is already
  corrected to `pre_authenticated = true`. NOTE: the in-flight W2a attempt-3 predates the
  correction and runs with `auth_method = "none"` — if it failed, relaunch with the corrected
  config; if it succeeded, note that "none" happened to resolve harmlessly.
- **gpt-5.6-sol is BLOCKED in the containerized implement path** — bridge's in-session
  `set_config_option(model)` × codex-acp 1.1.2 `models` field (effort-suffixed ids) →
  AgentCrashed. Authoritative: `docs/superpowers/2026-07-10-HANDOFF-m4-slice3-and-sol.md` Part B.
  gpt-5.5 is the proven impl model. **W2d is the root-cause fix** (spec in w2-tasks).
- The m4 example config (`examples/a2a-bridge.m4-slice3a-impl.toml`) has TWO stale lines vs the
  current container image: `model = "gpt-5.6-sol"` and `auth_method = "chat-gpt"` — suggest the
  owner fix after W2d lands.
- `target/release/lsp-mcp` was missing and is now built (host reviewers reference it).
- **run-workflow input delivery (2026-07-25):** `--input` files must be valid task specs
  (front-matter `task-type: freeform` suffices for briefs), AND the input reaches a node
  ONLY via a `{{input}}` placeholder in that node's prompt_file — otherwise it is SILENTLY
  dropped (no warning; the node just never sees it). Witness: mine-sol/mine-luna round 1.
- **gpt-5.6-luna works on this login** via host codex-acp lane (model = "gpt-5.6-luna",
  effort = "high", pre_authenticated, read-only sandbox) — smoked 2026-07-25
  (success-mining/smoke-luna.txt). Same auth rule as all codex lanes.
- **Host claude ACP lanes inherit the user's global Claude Code hooks** (Stop verify-gate
  fires; SessionStart too when its cache exists) AND their "read-only" is prompt-contract
  only. Consequences (2026-07-25): every claude reviewer session writes VERIFICATION.md
  into its session-cwd (~85 clones confirmed); a smoke pointed at a real repo CLOBBERED
  that repo's VERIFICATION.md. RULES: instrument/smoke session-cwd = ~/code/.b2a-scratch
  ONLY; treat claude-lane cwds as writable regardless of prompt contract; export
  CLAUDE_INSTRUMENT_CHILD=1 for instrument children (guards SessionStart; the Stop gate
  is NOT guarded — owner decision pending).
- Owner's OTHER bridge agent works concurrently on this machine — do not touch its containers,
  sessions, or tmp configs; keep our pipeline sequential.
- Detector cron 07:00 daily is installed and semantically verified; outputs in
  `~/code/prompts-skills-steering/mining/out/` (baseline, signatures, triage queue).

## Phases 3-5 (owner's instruction, MY interpretation — confirm with owner when awake)

Owner said: "proceed to phase 3 implementation then phase 4 then phase 5" if capacity allows.
Interpreting as program phases beyond Wave 2:
- **Phase 3 = execute Wave 3**: finish taskset curation for `mechanism-claims-v0` (items must
  become execution-verified per harness discipline), then RUN `exp-w3a-cite-or-label` via the
  prompts-skills-steering harness (codex judge; budget per existing exp conventions), log to
  TRACKER as DRAFT results for owner review. Do not promote steering rules without owner sign-off
  (promotion = edit to global CLAUDE.md/AGENTS.md — owner-approval territory).
- **Phase 4 = SSOT compilation rollout**: author the validated/global rules once in ssot-agents
  and compile to CLAUDE.md/AGENTS.md/Kiro steering (closing hand-duplication + bare-Kiro gaps).
  BLOCKED until ssot-agents compiler supports it — assess `@ssot/compiler` readiness first;
  otherwise prep the source-of-truth files only.
- **Phase 5 = close the loop**: wire verification-schema-check warn-only into the stop hooks
  (OWNER DECISION flagged in TRACKER — prepare the one-line patch, do not enable), add the
  recurrence-after-admission weekly report to mining, and file the bridge submit-path mount
  (done if W2c lands).
If this interpretation is wrong, the cost is small: each phase's first step is a read/prep step.

## Resume protocol for a fresh session (updated 2026-07-25 ~23:55)

1. Read this file top to bottom — the NEXT PASS section at the top is the active mandate;
   the CHECKPOINT LOG (newest first) is the state of record.
2. IN FLIGHT at handoff: **Task P implement run** (attested-prefix wrapper; log
   `~/Documents/w2-tasks/w2b-taskP-run.log`; spec docs/design/attested-prefix-cut-v3.md
   incl. §18 errata). On completion apply the established drill: read the hand-off tail —
   NEVER trust exit codes or "completed cleanly" claims; on verify-FAIL/REJECT classify the
   findings (enumerable → targeted fix, separate provenance-marked commit, four host gates
   with per-gate logs, scoped implement-review-light, merge via fetch + cherry-pick -n +
   commit -C --reset-author; open-class → escalate, don't churn). Then Task F
   (spec WRITTEN: w2-tasks/w2b-taskF-sanitizer.md — dispatch only after P merges), then cleanup-2 (smoke
   subcommand: container-agent model-override config failure at prompt_start + the
   message-destroying smoke.config classifier).
3. Config: `~/Documents/w2-tasks/w2-impl-gpt55.toml` (host codex pre_authenticated=true —
   NEVER auth_method/automatic; container impl likewise). Binary: rebuild after merges so
   the pipeline runs with its own latest protections. Branch:
   feat/m4-slice3a-ownership-finalization, pushed through 1d94680.
4. Owner-interactive still pending: codex /hooks trust (hash pin deliberately stale); kiro
   `login --use-device-flow` + `agent set-default --name enforced`; exp-w3a citation-bar
   sign-off (then run it: configs ready, 7 items, base rate 0.714).
5. Checkpoint THIS FILE after every stage. Keep turns small; the bridge does the heavy
   lifting; delegate closed diagnosis to subagents with evidence bars; warm-specialist
   reuse via SendMessage when a prior agent holds the needed context.
