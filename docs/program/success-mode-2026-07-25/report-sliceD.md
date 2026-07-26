# Slice D report — claude ssot-agents + ~/code orchestrator + ssot dogfood

[Provenance: mined and authored by the opus slice-D agent 2026-07-25; the agent's own
file-write was harness-blocked (subagents return text, not files), so the orchestrator
persisted this verbatim from the agent's final report.]

Miner: opus. slice-id `sliceD`. 31 files, all present, all indexed.

Method note: every file was streamed through a JSONL flattener into a line-numbered text index (`<lineno>\t<role>\t<kind>\t<text>`); no transcript was read whole. All citations are `file:line` into the **original** JSONL, with quotes read out of that line.

## 1. Coverage

**Deep-read (briefs, decision turns, verification chains, outcomes):** 5
- `~/.claude/projects/-Users-wesleyjinks-code/53d4f209-1835-47a2-81c6-58946e5d34ef.jsonl` (1,973 lines — opening resume, S0 probe region, review rounds 3-5, parallel-agent dispatch/steer/merge region, close-out)
- `~/.claude/projects/-Users-wesleyjinks-code/9aea8b01-4ba8-4372-bfe1-fd229c310b60.jsonl`
- `~/.claude/projects/-Users-wesleyjinks-code/608a7a2a-cff7-4ddf-bfe5-9cf650c457b0.jsonl` (7,949 lines — **targeted regions only**: dogfood 4340-4560, handoff 7860-7950)
- `~/.claude/projects/-Users-wesleyjinks-code-ssot-agents/f4ae7420-…jsonl` (brief + report)
- `~/.claude/projects/-Users-wesleyjinks-code-ssot-agents/7ead8e1c-…jsonl` (brief + close-out)

**Read end-to-end (they are tiny):** all 7 `/private/tmp/ssotdogfood-1784765168` sessions.

**Brief + final-output read (middles skimmed by keyword only):** 8 ssot-agents sessions — `0f414f95`, `752a8123`, `91b4ff13`, `1a17b6b6`, `973f29eb`, `a4f3bc72`, `8a2e260e`, `66466fe6`.

**Keyword-skim only:** `b554266e` (1,574 lines; characterized + spot-checked), `47cdebe1`, `d39b1dc8`, `e1b87ce6`, `d1ecae66`, `b50778ab`, `9b5ac476`, `354037e6`, `7dab96fb`, `9f54dd9a`, `febfcdaa`.

**What I did NOT cover (honest gaps):**
- ~93% of `608a7a2a` (the 7,949-line marathon). I mined two regions; its middle remains unmined beyond the two already-catalogued findings.
- Most of `b554266e` — the a2a-bridge roadmap / operator-UI / fable-design work, including several parallel fable dispatches and a PR fold I only characterized, did not audit.
- Lines ~60-1130 of `53d4f209` (review rounds 1-3 in detail) — sampled via keyword hits only.
- The interiors of the ssot-agents reviewer sessions: I read their dispatch briefs and final reports, not their tool-by-tool investigation paths.

## 2. Findings

### F1. Self-authored claim ledger dispatched as a falsification task, with ambiguity defaulting to REFUTED

**Pattern.** Before writing a rationale into a durable handoff, the orchestrator enumerated the three load-bearing claims *it had authored* and dispatched them as a narrow refutation task rather than a general review — fencing off the surface already covered by execution evidence, splitting one claim into independently-verdictable halves, requiring per-claim file:line evidence, and inverting the burden of proof. The review refuted 1 of 3. The refuted claim was one no test could ever have contradicted, and it was about to become permanent documentation. Repeatable because it converts "please review my change" into a finite list of falsifiable propositions with a pre-declared tie-break.

**Evidence.**
- `…/-Users-wesleyjinks-code/9aea8b01-4ba8-4372-bfe1-fd229c310b60.jsonl:214` — "**Yes, but a short read-only one — and for one specific reason, not as a ritual.**" … "What's *not* covered by any test is my emission-set reasoning." … "It's also written into the handoff now, so a wrong rationale becomes durable."
- `…9aea8b01…jsonl:234` (the brief) — "This is a **narrow falsification task, not a general review.**" / "Your job is to try to **refute** each one against the actual source. Default to `REFUTED` when the evidence is ambiguous." / "If a claim is `REFUTED`, state the narrower version that IS true, since the documentation must be corrected rather than deleted."
- `…9aea8b01…jsonl:289` (outcome) — "**Claim 1 — REFUTED,** and this is the one worth having asked for." … "**I'd have kept believing it, because nothing in the test suite disagrees.**"

**Proposed form.** Steering rule + dispatch template: *"Before a rationale enters a handoff, memory, or commit message, list it as a numbered claim and dispatch a refutation task. Ambiguous evidence = REFUTED. A refutation must supply the narrower true version."*

**Confidence.** High — brief and outcome both present; the mechanism produced a correction no gate in the repo could have produced.

### F2. Cheap pre-dispatch premise probe, with a positive control, before spending a long agent run

**Pattern.** The next queued slice (S0) was itself an evidence-capture task, so the orchestrator first probed whether the evidence was obtainable *at all* on the installed tooling — before writing the task spec. It wasn't: the target CLI had no Markdown agent loader and no singular-directory root, so the slice's gate could never close by observation. The slice was stopped and converted into an ADR instead of being dispatched. Crucially the probe carried a **positive control** proving the apparatus could produce the signal, so the negative result was attributable to the product, not the harness.

**Evidence.**
- `…/-Users-wesleyjinks-code/53d4f209-…jsonl:371` — "I stopped short of dispatching S0, because a cheap pre-dispatch probe turned up a blocker that would have burned a long Sol run." … "since S0 *is* evidence capture … I checked whether that evidence is obtainable before writing the task spec." … "**Positive control**: a JSON agent whose prompt says 'reply pineapple' → replies `pineapple` under `--agent-engine v2`. Same instruction as a Markdown carrier → `failed to set agent 'mdwitness': Internal error`."
- Independent second enactment of the same control discipline in the dogfood corpus: `…/-private-tmp-ssotdogfood-1784765168/78b1ebbc-…jsonl:5` prompt "reply with the single word plain" → `:11` "plain" — a transport control run alongside the real witness probes.

**Proposed form.** Steering rule: *"If a dispatch's deliverable is evidence, probe that the evidence is obtainable before writing the brief. Any negative observation reported as fact must be accompanied by a positive control on the same apparatus."* Also a bridge feature: require a `control:` field in evidence-capture task specs.

**Confidence.** High — two independent enactments; the first demonstrably avoided a long expensive run against an impossible gate.

### F3. Negatives that cannot lie: pinned counterexamples, one-variable witnesses, and a "check the finding that impeaches me first" triage

**Pattern.** Type-level counterexamples were pinned with `@ts-expect-error` so that a counterexample which *stops failing* becomes a hard compiler error (`TS2578: Unused '@ts-expect-error' directive`) — a negative test that cannot silently go vacuous. That harness caught a real false-pass: a witness had failed for an internal inconsistency rather than the property under test. When the external reviewer's round-4 verdict arrived, the orchestrator triaged the finding that impeached its *own* verification first, reproduced it, conceded, and **retracted the claim upward to the owner before continuing**. The lesson was then written into the next dispatch brief as a method clause carrying its own failure history.

**Evidence.**
- `…53d4f209…jsonl:1167` — "One finding says a negative I claimed to have verified still compiles — let me check that first, because it means my own verification was flawed."
- `…53d4f209…jsonl:1173` (probe result) — "error TS2578: Unused '@ts-expect-error' directive. === exit 2 ==="
- `…53d4f209…jsonl:1177` — "my witness passed for the wrong reason. Its scope was *internally* inconsistent … so it failed on that, not on the outer-layer disagreement I claimed to be testing."
- `…53d4f209…jsonl:1222` — "**I have not dispatched another review** … First, a correction to something I told you. Last turn I said I'd verified round 3's fixes by compiling counterexamples. **That verification was flawed.**"
- Propagated into the next brief, `…53d4f209…jsonl:1351` — "Put `@ts-expect-error` on every counterexample so an unused directive is itself an error — then `tsc` exiting 0 proves both that positives compile and that every negative genuinely fails." and "**Construct counterexamples so each isolates exactly the correlation it claims to test.** A previous attempt was rejected because its witness carried an internally inconsistent nested value and therefore failed for the wrong reason."

**Proposed form.** Detector signature (negative tests with no fail-closed pin) + template clause for any brief asking for counterexamples + steering rule: *"When a reviewer returns findings, adjudicate the one that contradicts your own verification before all others."*

**Confidence.** High — mechanism, the failure it caught, the retraction, and the propagation are all present.

### F4. Round-trip identity: verify the bytes that shipped, not the scratch copy — and review the artifact in the dimension your gate is blind to

**Pattern.** A subagent proved a type contract by compiling a scratch `.ts` file. The orchestrator did not accept that: it wrote a round-trip checker that re-extracts the appendix *out of the committed document*, re-attaches the witnesses, and recompiles — proving the shipped text is the verified text. It re-ran the same checker against the merged tree. Separately, while resolving the merge it noticed a text anomaly, disambiguated "merge artifact vs. real defect in the commit" with a targeted `git show`, and found a real prose splice defect — explicitly noting the compiler gate is blind to that dimension.

**Evidence.**
- `…53d4f209…jsonl:1789` (the checker's own docstring, in tool output) — "This proves the text that shipped is the text that was verified, not merely that a scratch file compiled." and its result "appendix in doc is byte-identical to the verified scratch file: True".
- `…53d4f209…jsonl:1793` — "Independently confirmed: the appendix in A's committed doc is **byte-identical** to the file that compiles, `tsc` exits 0 with 49 pinned negatives".
- `…53d4f209…jsonl:1818` — "Confirmed: a real text-splice defect in A's commit — the old fragment `Correlations are also normative and **total**:` was left prefixed to the new sentence. `tsc` can't catch prose."
- Verification artifacts were then promoted out of the ephemeral session scratchpad into the repo (`…53d4f209…jsonl:1875`, `docs/research/appendix-b-verification/`).

**Proposed form.** Bridge feature / verify-node: *"proof-to-artifact identity check — the verified bytes must be extracted from the committed artifact, not from a scratch copy."* Plus steering rule: name the dimension your gate cannot see and eyeball that one.

**Confidence.** High — decisive single case, mechanism reusable verbatim, reused on the merge result in the same session.

### F5. Steer running agents in place: flag the reversal, hand the peer artifact by commit-ref, partition the write surface

**Pattern.** The owner changed direction while two implementation agents were mid-run in separate worktrees. Instead of killing and re-dispatching, the orchestrator sent each a delta message that (a) named what was **unchanged**, (b) flagged in caps the single instruction that was **REVERSED**, (c) handed over the peer agent's artifact as an exact `git show <sha>:<path>` command runnable from the recipient's own worktree, and (d) partitioned the write surface between the two concurrent agents on the same 2,800-line file, with the orchestrator reserving the merge. Both agents landed; the merge produced exactly one conflict region and shipped.

**Evidence.**
- `…53d4f209…jsonl:1539` — "Both agents are still running, so let me steer them onto it rather than have them finish work we'd then rework."
- `…53d4f209…jsonl:1545` — "`git show e75d1a2:docs/research/2026-07-24-contract-ergonomics-analysis.md` will read it from your worktree".
- `…53d4f209…jsonl:1549` — "one instruction is reversed. REVERSED: the universal typing claim is NOT being abandoned…" and "IMPORTANT — avoid collision: another agent is editing Appendix B's types in a separate worktree right now. Keep your edits to the boundary table … Do not restructure the type declarations themselves. Report your table in full so I can merge it against their type changes."
- `…53d4f209…jsonl:1555` — "Both agents redirected onto the synthesis with their context intact — no restart, no rework."
- Outcome `…53d4f209…jsonl:1903` — "The synthesis is merged to `main` and pushed — `9c3b041`."

**Proposed form.** Template clause for `SendMessage` re-steers: *UNCHANGED / REVERSED / NEW context-by-commit-ref / write-surface boundary / who merges.*

**Confidence.** High — full loop from re-steer to merged-and-pushed in one session.

### F6. Dogfooding an auto-updating provider: observation-first version sealing with a before==after bookend, plus absence-gated writes into real user roots

**Pattern.** The dogfood harness drives real installed CLIs against the user's real config roots. Two mechanisms made that both safe and attributable: (1) **do not predeclare the version** — seal whatever the run observes and gate the whole attempt on a `before == after` version+binary bookend, so a mid-run auto-update discards the attempt rather than silently mixing versions; (2) materialize carriers only when the target path is verified **absent**, tear down only when the current bytes still match what was written, and finish with an explicit residue check. The bookend fired live, mid-session, on a *minor* version bump — the case where behavioral assumptions actually break.

**Evidence.**
- `…/-Users-wesleyjinks-code/608a7a2a-…jsonl:4377` — "The race recurred **live, mid-session**." … "The absence-gate did its job: the version check aborted **before any write**" … "my harness still had predeclared versions hard-coded (`EXPECT`), which is the anti-pattern the design warned against."
- `…608a7a2a…jsonl:4395` (harness summary) — "fatal: no anomalies: 0 bookendStable: true teardown …: removed-byte-matched".
- `…608a7a2a…jsonl:4470` — "Real roots verified … zero residue, byte-matched teardown. It ran observation-first on the live versions, bookend-stable (no mid-run drift)".
- Distilled to durable memory, read back a day later at `…/-Users-wesleyjinks-code/53d4f209-…jsonl:110` — "Do NOT predeclare the version. The CLIs auto-update constantly … Seal whatever the run observes; gate only on a before==after version+binary bookend, so a mid-run update discards the attempt."

**Proposed form.** Bridge feature / harness template: environment-bookend gate + absence-gated mutation + byte-matched teardown + residue assertion, for any probe touching real host state.

**Confidence.** High — enacted, fired on a real drift event, promoted to durable memory.

### F7. Exit 0 is not evidence; name the weakest claim your observation licenses

**Pattern.** Two coupled refusals to over-read a green result. First: with every probe at exit 0 and all safety gates clean, the agent declined to call the behavior proven and went to the actual stdout witnesses. Second, and stronger: challenged by a reviewer, it tested its own evidence for **observational equivalence** — asking whether a different mechanism would produce byte-identical output — found that it would, and downgraded its claim from "precedence proven" to "anchored discovery proven". It also partitioned the resulting verdict into *defects in the artifact* vs *defects in my own probes*.

**Evidence.**
- `…608a7a2a…jsonl:4403` — "All probes exited 0 … **But exit 0 doesn't prove the *selection* behavior** — I need the actual probe outputs to confirm project-over-user".
- `…608a7a2a…jsonl:4555` — "I told you the Kiro chat witness proved workspace-over-global precedence. **It doesn't.** … root→`selected-project` and sibling→default are equally consistent with `chat --agent` *never admitting the global carrier as a candidate at all*. That path yields identical outputs. So my evidence proves anchored discovery, not precedence. I over-claimed". Same turn splits "Real code defects" from "Evidence gaps — my dogfood used insufficient/wrong probes".
- Same turn pre-registers the decision rule for the *next* probe: "both candidates + warning → conservative model is fine …; Global not a candidate → the collision is vacuous and the **Kiro design must be revised, not just re-pinned**." The same habit appears mechanically at `…53d4f209…jsonl:1168`, where the probe command itself ends `echo "=== exit $? (nonzero here means the counterexample COMPILES, i.e. Sol is right) ==="`.

**Proposed form.** Steering rule: *"Before claiming an observation proves X, name another mechanism that would produce identical output. If you can name one, your evidence does not discriminate — report the weaker claim. Exit status is never behavioral evidence."* Plus: pre-register outcome→action mapping in the probe's own output string.

**Confidence.** High — two enactments of the pre-registration form; the equivalence check overturned a claim already reported to the owner.

### F8. Evidence-provenance partition: the brief labels what it hands over, the report labels what it re-ran

**Pattern.** The dispatch brief hands the reviewer the controller's test totals under an explicit heading declaring them *not* reviewer-verified, and instructs the reviewer to keep that boundary in its report. The reviewer complied precisely: it listed what it independently re-ran, listed what remained supplied evidence, and graded one of its own reconciliations as "not machine-verified". This stops a review from laundering the implementer's numbers into apparent independent confirmation.

**Evidence.**
- Brief: `…/-Users-wesleyjinks-code-ssot-agents/f4ae7420-…jsonl:8` — "## Supplied controller evidence, not reviewer-rerun evidence" … "distinguish anything you rerun from supplied evidence" … "Do not rely on prior review prose as proof." … "Trace, rather than sample".
- Enactment: `…f4ae7420…jsonl:258` — "Independently rerun (bounded probes, distinguished from supplied evidence): activation focused suite — **35/35 pass** … I did **not** rerun any mutation campaign … those totals (224/224, 50/50, 851/851, 1065/1065) remain supplied controller evidence. A hand count … reconciles to 224 … but was not machine-verified."
- Related brief-side clause for parallel independent lanes, `…/-Users-wesleyjinks-code-ssot-agents/7ead8e1c-…jsonl:8` — "Your design will be reconciled with a separately written controller design, so independence and repo-grounding matter more than agreement" and "Do not search for or read any controller draft of this workflow. None should exist when your turn begins."

**Proposed form.** Template clause (both directions) + report section: *Rerun / Supplied / Asserted-but-unverified*.

**Confidence.** High — dispatch clause and matching enactment, in different sessions.

### F9. Two-tier handoff (memory index → cold-start doc) with post-write reconciliation, verified lossless on the read side

**Pattern.** The writing session produced a small durable memory entry whose `description` is the state plus the next action and whose metadata carries `originSessionId`, plus a self-contained cold-start doc in the origin session's scratchpad, plus an index line in MEMORY.md. When the state changed *after* those were written (the commit got pushed), the agent went back and reconciled **all three** artifacts rather than leaving a stale claim. The next session, a day later, oriented from memory → handoff, then re-verified the named commit against live git before acting — and it matched exactly.

**Evidence (write side).**
- `…608a7a2a…jsonl:7872` — "I'll write a self-contained resume file and add a durable project memory so a cleared session recalls this."
- `…608a7a2a…jsonl:7923` — "Let me update the memory and handoff to reflect it's now on the remote (they said 'unpushed')."; `:7946` — "**Handoff + memory reconciled** to 'pushed.'"

**Evidence (read side, next session).**
- `…53d4f209…jsonl:15` — "I'll orient myself from the memory and handoff first."
- `…53d4f209…jsonl:17` — memory header "description: ssot-agents host-realization design READY + owner-signed-off + committed; next is implementation slice S0" / "originSessionId: 608a7a2a-cff7-4ddf-bfe5-9cf650c457b0".
- `…53d4f209…jsonl:43` — live `git log` returns "7e91fd8 docs: add READY host-realization discovery + C-1c design (owner signed off)" — the exact commit the handoff named; the session then proceeded to the handoff's next action.

**Proposed form.** Doc + steering rule: *"A handoff is not done when written; any state change before session end must be reconciled into every artifact that asserted the old state. Memory entry = state + next action + originSessionId; cold-start detail lives in the origin session scratchpad."*

**Confidence.** High — writer and reader are both in-slice and the carry is verifiable.

## 3. Recurrences of already-catalogued patterns (fresh citations, not re-reports)

- **Independent recomputation of peer findings**, in an *orchestrator→owner* position: `…53d4f209…jsonl:1506` "Let me verify its central quantitative claim before I repeat it." → `:1512` "Verified: **4 → 55** uses of `extends` in the design since your sign-off." The owner's decision was then made on the recomputed number. Also `:1758` "Verifying A independently before merging — its claims are strong enough to be worth checking myself."
- **Verify-first premise measurement**, in the dispatched-agent direction: the reviewer corrected its own brief before answering — `…/ssot-agents/973f29eb-…jsonl:351` "**One correction to the brief up front.** C-PORT-9A has *no* plan-observe-verify staging".
- **Dischargeable objections / regression ledger**: the round-N brief is derived from round N-1 and carries a cumulative table of *all* prior WRONG findings — `…53d4f209…jsonl:1137` "Regression table covering all fourteen prior `WRONG` findings (seven from round 1, four from round 2, three from round 3): resolved / partially resolved / not resolved, with evidence." The same brief solicits *endorsement* as a first-class deliverable ("an explicit endorsement is as useful here as a finding") and instructs the reviewer to distrust the dispatcher's own verification ("The round-4 author compiled five positives … **Re-derive that independently**"). Anti-recycling counterpart: `…/ssot-agents/752a8123-…jsonl:5` "Do not re-report resolved findings as new defects." Enacted at `…/ssot-agents/91b4ff13-…jsonl:35` — "All six inherited findings adjudicate RESOLVED", each with line citations from the revised document.
- **Honest-degraded-path / bounded-contract close-out**: a three-state verdict vocabulary including "blocked on owner decision" was actually used — `…/ssot-agents/7ead8e1c-…jsonl:276` — "**`CLEANROOM WORKFLOW DESIGN: READY WITH OWNER DECISIONS`**", with a constraint-by-constraint compliance attestation: "Nothing in the repository was touched, no artifacts were created outside the plan file, and no child agents were invoked."
- **Refutation propagated to durable memory**: `…9aea8b01…jsonl:289` "it's corrected in place with the refutation recorded rather than quietly deleted."

## 4. FAILURE nominations

### FAILURE-1 — Framework injection non-deterministically destroys terse-probe measurements

**Pattern.** The dogfood probes drive a real `claude` CLI with a one-word instruction and read a single-token witness. The operator's `SessionStart` hook injects the superpowers framework into that child session. In 3 of 7 probe runs the injected framework won: the model invoked a skill and answered with a paragraph instead of the witness token. Same agent, same prompt, same config, interleaved in time — the instrument was flaky at ~43%, and a missing witness could have been misread as a selection failure. The fix (isolate the child with `--settings <empty.json>`, use a small model) was recorded in memory ~6 minutes after the last polluted run.

**Evidence.**
- Polluted: `…/-private-tmp-ssotdogfood-1784765168/12860357-…jsonl:12` `tool_use Skill {"skill": "superpowers:using-superpowers"}` → `:21` "I've loaded the superpowers skill system. Now I need to understand what you want to accomplish…" (no witness token). Same shape in `5a8714ed-…jsonl:17` and `f91d1193-…jsonl:16`.
- Clean, same config: `…/bc3c6495-…jsonl:12` — "selected-project" (also `ee3fa89e`, `1c505143`).
- Rule recorded: `…53d4f209…jsonl:110` — "**Claude must be isolated** or the operator's superpowers SessionStart hook / plugins inject framework context and the model ignores the agent's terse instruction (nonce witness becomes noise)."

**Proposed form.** Detector signature: any probe whose expected output is a fixed token should assert the token and fail loudly on a prose reply; harness rule: child probe sessions run with empty settings.

**Confidence.** High — 7/7 runs inspected, 3 clean failures, fix recorded in-slice.

### FAILURE-2 — S11 shape confirmed: strong reasoner generalizes a mechanism claim from a narrow observation, never traced

**Pattern.** Two independent instances, both by an opus-class orchestrator, both about *system mechanism* rather than about code it had read: (a) "the chat witness proves workspace-over-global precedence" — untraced, and an alternative mechanism produces identical output; (b) "two independent marker instances would have changed behavior silently" — resting on an untraced assertion about `node --test` process topology. Both were refuted by an external reviewer who **ran the discriminating command**; the reader-grounds-reasoner success shape is exactly the mitigation. The agent itself named the signature.

**Evidence.**
- `…608a7a2a…jsonl:4555` — "So my evidence proves anchored discovery, not precedence. I over-claimed, and the WRONG/SMELL discipline says I should have caught that myself."
- `…9aea8b01…jsonl:214` — "That's exactly the shape of defect I produced repeatedly this session: **true in the narrow case, asserted generally**."
- `…9aea8b01…jsonl:289` — "`--test-isolation=none` co-loads the files; **the reviewer ran it and confirmed**. So 'they can never share a process' is false".

**Proposed form.** Detector signature: an assertion about runtime/process/precedence mechanism with no command output or file:line in the same turn. Mitigation already in-slice: route such claims to an executor with the discriminating command named (see F1).

**Confidence.** High — two instances, both self-documented, both externally refuted.

## 5. Anti-findings

### AF-1 — "I verified it by compiling counterexamples" looked rigorous and was false twice

Compiling counterexamples is a strong-looking verification claim, and in this slice it produced a **false** verification that survived a round of review before being caught. The practice only became trustworthy after two additions: pinning every negative with `@ts-expect-error` (so a negative that stops failing is a build error) and requiring each witness to be internally consistent so it varies exactly one field. Reported so the bare practice is not adopted without those two conditions.
**Evidence.** `…53d4f209…jsonl:1222` — "Last turn I said I'd verified round 3's fixes by compiling counterexamples. **That verification was flawed.** My 'outer layer disagrees with stamped Scope' witness carried an i[nternally inconsistent value]". Fix conditions at `…53d4f209…jsonl:1351`.

### AF-2 — Dispatching a review "as a ritual" was explicitly rejected, and the rejection was right

The same session that ran fifteen mutation campaigns declined to send those results to a reviewer and instead sent only the untested rationale — because the campaigns already dominated a static read. The one thing tests could not cover is exactly what the review refuted; ritual review of already-executed evidence would have returned nothing.
**Evidence.** `…9aea8b01…jsonl:214` — "The campaign run already covers the risk a reviewer would most likely look for … Fifteen campaigns and 29/29 on project activation is stronger evidence than a static read."
