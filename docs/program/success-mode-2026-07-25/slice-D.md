# Slice D — claude ssot-agents + ~/code orchestrator + ssot dogfood (miner: opus)

slice-id: sliceD
Corpus: 31 claude session files (14d), listed in
`~/Documents/success-mining/sliceD-files.txt` (host paths, `~` = /Users/wesleyjinks):
17 in ~/code/ssot-agents, 7 in the ~/code orchestrator project dir (multi-agent ssot
orchestrator transcripts live here), 7 in the /private/tmp/ssotdogfood-* dogfood dir.

ALREADY MINED (go beyond, don't re-report; recurrence notes with citations welcome):
- 608a7a2a (~/code, the failure-forensics marathon): graded adjudication scorecard with
  self-error accounting (L965, L1120); gate-vacuity audit (L2980).

Focus questions:
1. Multi-agent orchestration successes: dispatch briefs that worked, fold/merge decisions
   done well, disagreement resolution between parallel agents, orchestrator-level
   verification of subagent claims. Cite enactments.
2. The ssot dogfood sessions: what did successful compiler-dogfooding look like —
   especially moves that caught spec/implementation drift early?
3. Handoff quality across sessions: which handoff/checkpoint practices demonstrably
   carried state losslessly (the reader session visibly resumed correctly), beyond the
   known checkpoint-discipline entry?
4. S11 watch (owner nomination, reader-grounds-reasoner): either shape — a strong reasoner
   (opus/sol/fable-class) asserting code behavior it never traced (failure shape) vs
   reader-model citations grounding/correcting a reasoner (success shape).
5. Both polarities welcome; success primary.

Method + report per `~/Documents/success-mining/miner-node-prompt.md`. You CAN write:
save the report to `~/Documents/success-mining/report-sliceD.md` AND return it as your
final message.
