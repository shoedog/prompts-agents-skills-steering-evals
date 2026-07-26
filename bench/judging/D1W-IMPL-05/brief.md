# Blind pairwise code-review judgment — D1W-IMPL-05

Two different engineers (Arm A, Arm B) independently completed the SAME task
from the same starting commit. You see the task brief and both final diffs.
You do NOT know who the engineers are; judge only the work. Answer the JSON
schema exactly; a_materially_better/b_materially_better may not both be true;
both false = parity.

## Task brief (both arms received this; one may have received extra process guidance — judge the WORK, not the process)

You are IMPLEMENTING one task of the "E7 — Typed Task-Spec Contract" feature for the a2a-bridge (a Rust A2A↔ACP
bridge + multi-agent workflow orchestrator). You have write access (danger-full-access). Work TDD.

BINDING DOCS (read the relevant task + the corrections):
- PLAN: `docs/superpowers/plans/2026-06-27-e7-typed-task-spec.md` — the `## v2` section (PR-FIX-1..10) SUPERSEDES the
  v1 task text where they conflict. ALWAYS apply the v2 corrections for your task.
- SPEC: `docs/superpowers/specs/2026-06-27-e7-typed-task-spec.md` (`## v2`/`## v3`/`## v4` folds are binding).

RULES:
- Implement ONLY the task named in the input below. Write the code AND the tests from the plan (adapted per v2).
- **VERIFICATION CAP (hard):** after writing, run AT MOST ONE targeted test command (≤120s) to sanity-check your
  task — e.g. `cargo test -p <crate> <filter>`. Do NOT run `cargo build --workspace`, `--all-targets`, clippy, or
  fmt — the CONTROLLER runs the real gates in a clean host env (your sandbox stalls `cargo` at rustc startup). If a
  test command runs >120s, KILL it and report "written, runtime-unverified".
- **DO NOT commit. DO NOT run any git-mutating command.** The controller commits.
- Do NOT touch files outside your task. Do NOT modify the pre-existing untracked `examples/*.toml` / `prompts/*.md`
  or the modified `examples/a2a-bridge.slicing-analysis.toml`.
- REPORT at the end: the exact files you wrote/modified, a one-line summary of each, and the single test result
  (PASS / FAIL / runtime-unverified). Be concise. Then STOP.

## YOUR TASK: Task 10 — implement `commit_message` precedence (typed > file > title > derived)

Implement **Task 10** from `docs/superpowers/plans/2026-06-27-e7-typed-task-spec.md`, applying **RR2-FIX-5** (comment-strip
+ fall back to title) + **PR-FIX-9** (the 4-arg signature RIPPLES: merge.rs + the existing tests + the `.1`/warning
re-spec; tweak.rs is NOT a caller). In `bin/a2a-bridge/src/implement.rs` (`commit_message`, ~:121) + the call sites.

### New signature
`pub fn commit_message(typed: Option<String>, file: Option<String>, title: &str, task: &str) -> (String, CommitSource)`
where `pub enum CommitSource { Typed, File, Title, Derived }` (replaces the current `bool` — re-spec, PR-FIX-9).
- For each candidate string (`typed`, then `file`): **strip HTML comments + trim + NUL-strip + bound to 64 KiB**
  (reuse/mirror `read_commit_msg_file`'s bounding, ~:136). A candidate that is empty/comment-only AFTER stripping is
  treated as ABSENT.
- Precedence: a non-empty stripped `typed` → `CommitSource::Typed`; else non-empty stripped `file` →
  `CommitSource::File`; else a non-empty `title` → `CommitSource::Title`; else the existing task-derived default →
  `CommitSource::Derived`.

### Call sites (PR-FIX-9 — ALL three)
- `bin/a2a-bridge/src/main.rs` (~:2133, currently `commit_message(read_commit_msg_file(&clone), &task)`): pass the
  parsed spec's `Commit Message` section as `typed` (`spec.section("Commit Message").map(|s| s.content.clone())`), the
  file channel as `file` (`read_commit_msg_file(&clone)`), the parsed `title` (`spec.title.as_deref().unwrap_or("")`),
  and `&task` (the body). The ONE resolved `message` threads to `host_commit` (~:2166) AND the checkpoint
  `original_message` (~:2189) — NO new persisted field.
- `bin/a2a-bridge/src/merge.rs` (~:465, currently `commit_message(ck.original_message.clone(), &ck.task_brief)`):
  the merge path has the PERSISTED `original_message` (already-resolved) → pass it as `typed` (highest precedence),
  `file = None`, `title = &ck.task_brief`, `task = &ck.task_brief`. (tweak.rs passes `original_message` into `decide`
  — it does NOT call `commit_message`; leave it.)
- **Re-spec the `.1`/warning** (main.rs:~2134-2135): the "no `.git/A2A_COMMIT_MSG` — using task-derived message"
  warning must fire ONLY when `source == CommitSource::Derived` — a `Typed`/`File`/`Title` source must NOT mis-warn
  "task-derived".

### Tests
- `bin/a2a-bridge/src/implement.rs` `commit_precedence_and_comment_only_falls_back_to_title`:
  - `commit_message(Some("feat: x".into()), None, "Add foo", "task body").0 == "feat: x"` (Typed wins).
  - `commit_message(Some("<!-- OPTIONAL -->".into()), None, "Add foo endpoint", "task body").0 == "Add foo endpoint"`
    (comment-only typed → absent → Title).
  - `commit_message(None, None, "Add foo endpoint", "task body").0 == "Add foo endpoint"` (no typed/file → Title).
  - `commit_message(None, Some("from file".into()), "T", "task").0 == "from file"` (File over Title).
- **Update the EXISTING `commit_message` tests** at implement.rs ~:698/:702/:708/:710 (currently 2-arg) to the new
  4-arg signature + the `CommitSource` return (PR-FIX-9). Keep their intent (file content wins / blank → fallback /
  bounding).

VERIFICATION CAP: run ONLY `cargo test -p a2a-bridge commit_precedence 2>&1 | tail -20` (≤120s; a2a-bridge is large —
kill + report "written, runtime-unverified" if it stalls). Report files + result. Do NOT build the whole workspace, do
NOT commit.


## Probe question (answer in `probe_answer`, per arm)

Focus on TEST RIGOR: for each arm, would its tests FAIL on the pre-change code (regression-catching), do they cover negative/edge cases per new code path, and do they assert real behavior rather than trivially passing? Name the strongest and weakest test in each arm.

## Arm A diff

```diff
diff --git a/bin/a2a-bridge/src/implement.rs b/bin/a2a-bridge/src/implement.rs
index b015d42e..243f87f3 100644
--- a/bin/a2a-bridge/src/implement.rs
+++ b/bin/a2a-bridge/src/implement.rs
@@ -115,22 +115,83 @@ pub fn compose_warm_fetch(
 
 // ─── Commit message ──────────────────────────────────────────────────────────
 
-/// Resolve the commit message: the agent-written `.git/A2A_COMMIT_MSG` content if non-blank, else a
-/// deterministic task-derived fallback `implement: <first line of task, truncated>`. Returns
-/// (message, used_fallback). `raw` is the file content (None if absent/unreadable/oversize/NUL/non-UTF-8).
-pub fn commit_message(raw: Option<String>, task: &str) -> (String, bool) {
-    if let Some(s) = raw {
-        let trimmed = s.trim();
-        if !trimmed.is_empty() {
-            return (trimmed.to_string(), false);
-        }
+/// Which precedence tier the resolved commit message came from (RR2-FIX-5 / PR-FIX-9).
+#[derive(Debug, Clone, Copy, PartialEq, Eq)]
+pub enum CommitSource {
+    Typed,
+    File,
+    Title,
+    Derived,
+}
+
+/// Strip HTML comments (mirrors `bridge_core::task_spec`'s stripper — kept local since that helper isn't
+/// `pub`). Used only to decide whether a candidate is comment-only, never to alter rendered content.
+fn strip_html_comments(s: &str) -> String {
+    let mut out = String::with_capacity(s.len());
+    let mut rest = s;
+    while let Some(start) = rest.find("<!--") {
+        out.push_str(&rest[..start]);
+        let after_start = &rest[start + "<!--".len()..];
+        let Some(end) = after_start.find("-->") else {
+            return out;
+        };
+        rest = &after_start[end + "-->".len()..];
+    }
+    out.push_str(rest);
+    out
+}
+
+/// Clean a `typed`/`file` commit-message candidate: strip HTML comments, trim, drop NUL bytes, bound to
+/// 64 KiB (mirrors `read_commit_msg_file`'s bounding). A candidate that is empty/comment-only afterward is
+/// treated as ABSENT (`None`), not as "present but blank".
+fn clean_commit_candidate(raw: Option<String>) -> Option<String> {
+    const MAX: usize = 64 * 1024;
+    let s = raw?;
+    let stripped = strip_html_comments(&s);
+    let trimmed = stripped.trim();
+    let no_nul: String = trimmed.chars().filter(|&c| c != '\0').collect();
+    let mut end = no_nul.len().min(MAX);
+    while !no_nul.is_char_boundary(end) {
+        end -= 1;
+    }
+    let bounded = no_nul[..end].trim();
+    if bounded.is_empty() {
+        None
+    } else {
+        Some(bounded.to_string())
+    }
+}
+
+/// Resolve the commit message with precedence **typed > file > title > task-derived**:
+/// - `typed`: the parsed task-spec's `Commit Message` section content.
+/// - `file`: the agent-written `.git/A2A_COMMIT_MSG` content (`read_commit_msg_file`).
+/// - `title`: the parsed task-spec title.
+/// - `task`: the task body, used only for the final derived fallback `implement: <first line, truncated>`.
+///
+/// `typed`/`file` are comment-stripped + trimmed + NUL-stripped + 64 KiB-bounded before the emptiness
+/// check, so a comment-only or blank candidate falls through instead of winning as an empty message.
+pub fn commit_message(
+    typed: Option<String>,
+    file: Option<String>,
+    title: &str,
+    task: &str,
+) -> (String, CommitSource) {
+    if let Some(s) = clean_commit_candidate(typed) {
+        return (s, CommitSource::Typed);
+    }
+    if let Some(s) = clean_commit_candidate(file) {
+        return (s, CommitSource::File);
+    }
+    let title = title.trim();
+    if !title.is_empty() {
+        return (title.to_string(), CommitSource::Title);
     }
     let first = task.lines().next().unwrap_or("").trim();
     let mut subj: String = first.chars().take(120).collect();
     if subj.is_empty() {
         subj = "changes".into();
     }
-    (format!("implement: {subj}"), true)
+    (format!("implement: {subj}"), CommitSource::Derived)
 }
 
 /// Read `<clone>/.git/A2A_COMMIT_MSG`, bounded to 64 KiB so an oversized/binary file can't blow memory.
@@ -500,7 +561,7 @@ pub fn decide(
     completed: bool,
     head_guard: Result<(), String>,
     stage: StageState,
-    msg: (String, bool),
+    msg: (String, CommitSource),
 ) -> Action {
     if !completed {
         return Action::Abort("workflow did not complete".into());
@@ -694,21 +755,71 @@ mod tests {
 
     #[test]
     fn commit_message_file_else_fallback() {
+        // file content wins (over a non-empty title, too).
         assert_eq!(
-            commit_message(Some("  Fix the widget\n\ndetails\n".into()), "task ignored"),
-            ("Fix the widget\n\ndetails".to_string(), false)
+            commit_message(
+                None,
+                Some("  Fix the widget\n\ndetails\n".into()),
+                "some title",
+                "task ignored"
+            ),
+            ("Fix the widget\n\ndetails".to_string(), CommitSource::File)
         );
+        // no typed/file/title → task-derived fallback.
         assert_eq!(
-            commit_message(None, "Add a FOO marker file to the repo root\nmore"),
+            commit_message(
+                None,
+                None,
+                "",
+                "Add a FOO marker file to the repo root\nmore"
+            ),
             (
                 "implement: Add a FOO marker file to the repo root".to_string(),
-                true
+                CommitSource::Derived
             )
         );
-        assert!(commit_message(Some("   \n  ".into()), "Tidy up").1);
+        // blank candidates (whitespace-only) → ABSENT → falls through to derived.
+        assert_eq!(
+            commit_message(Some("   \n  ".into()), None, "", "Tidy up").1,
+            CommitSource::Derived
+        );
         let long = "x".repeat(500);
-        let (m, fb) = commit_message(None, &long);
-        assert!(fb && m.starts_with("implement: ") && m.len() <= "implement: ".len() + 120);
+        let (m, source) = commit_message(None, None, "", &long);
+        assert!(
+            source == CommitSource::Derived
+                && m.starts_with("implement: ")
+                && m.len() <= "implement: ".len() + 120
+        );
+    }
+
+    #[test]
+    fn commit_precedence_and_comment_only_falls_back_to_title() {
+        // typed wins outright.
+        assert_eq!(
+            commit_message(Some("feat: x".into()), None, "title", "task").0,
+            "feat: x"
+        );
+        // comment-only typed → treated ABSENT → falls back to the title (not the raw comment, not the task).
+        assert_eq!(
+            commit_message(
+                Some("<!-- OPTIONAL -->".into()),
+                None,
+                "Add foo endpoint",
+                "task"
+            )
+            .0,
+            "Add foo endpoint"
+        );
+        // no typed, no file → title.
+        assert_eq!(
+            commit_message(None, None, "Add foo endpoint", "task").0,
+            "Add foo endpoint"
+        );
+        // file beats title when there's no typed commit message.
+        assert_eq!(
+            commit_message(None, Some("from file".into()), "T", "task").0,
+            "from file"
+        );
     }
 
     #[test]
@@ -762,7 +873,7 @@ mod tests {
 
     #[test]
     fn decide_matrix() {
-        let msg = ("m".to_string(), false);
+        let msg = ("m".to_string(), CommitSource::Derived);
         assert_eq!(
             decide(false, Ok(()), StageState::Staged, msg.clone()),
             Action::Abort("workflow did not complete".into())
diff --git a/bin/a2a-bridge/src/main.rs b/bin/a2a-bridge/src/main.rs
index 77cd7093..60feaa2f 100644
--- a/bin/a2a-bridge/src/main.rs
+++ b/bin/a2a-bridge/src/main.rs
@@ -2214,8 +2214,13 @@ async fn implement_cmd(args: &[String]) -> Result<(), BoxError> {
             return Err(format!("implement: stage check: {e}").into());
         }
     };
-    let msg = implement::commit_message(implement::read_commit_msg_file(&clone), &task);
-    if msg.1 {
+    let msg = implement::commit_message(
+        spec.section("Commit Message").map(|s| s.content.clone()),
+        implement::read_commit_msg_file(&clone),
+        spec.title.as_deref().unwrap_or(""),
+        &task,
+    );
+    if msg.1 == implement::CommitSource::Derived {
         eprintln!("[implement] no .git/A2A_COMMIT_MSG — using task-derived message");
     }
     match implement::decide(completed, guard, stage, msg) {
diff --git a/bin/a2a-bridge/src/merge.rs b/bin/a2a-bridge/src/merge.rs
index a4617e4a..fa62d832 100644
--- a/bin/a2a-bridge/src/merge.rs
+++ b/bin/a2a-bridge/src/merge.rs
@@ -462,7 +462,12 @@ pub fn merge_clone(
                 );
                 return MergeOutcome::Unlanded;
             }
-            let (msg, _) = commit_message(ck.original_message.clone(), &ck.task_brief);
+            let (msg, _) = commit_message(
+                ck.original_message.clone(),
+                None,
+                &ck.task_brief,
+                &ck.task_brief,
+            );
             let rt = match reauthor_commit(clone, cur, &ck.base_commit, &msg, &op) {
                 Ok(r) => r,
                 Err(e) => {
diff --git a/bin/a2a-bridge/src/tweak.rs b/bin/a2a-bridge/src/tweak.rs
index 7664d7c6..57d1de37 100644
--- a/bin/a2a-bridge/src/tweak.rs
+++ b/bin/a2a-bridge/src/tweak.rs
@@ -256,8 +256,15 @@ pub async fn run_tweak_loop(
                     }
                 };
                 // completed==true here, so `decide`'s only Abort cause is the head guard → Diverged.
-                let action =
-                    implement::decide(true, guard, stage, (original_message.to_string(), false));
+                let action = implement::decide(
+                    true,
+                    guard,
+                    stage,
+                    (
+                        original_message.to_string(),
+                        implement::CommitSource::Typed,
+                    ),
+                );
                 match fix_step(&action) {
                     FixDisposition::Amend => match implement::host_amend_commit(clone) {
                         Ok(s) => {

```

## Arm B diff

```diff
diff --git a/bin/a2a-bridge/src/implement.rs b/bin/a2a-bridge/src/implement.rs
index b015d42e..0a3373bb 100644
--- a/bin/a2a-bridge/src/implement.rs
+++ b/bin/a2a-bridge/src/implement.rs
@@ -115,22 +115,72 @@ pub fn compose_warm_fetch(
 
 // ─── Commit message ──────────────────────────────────────────────────────────
 
-/// Resolve the commit message: the agent-written `.git/A2A_COMMIT_MSG` content if non-blank, else a
-/// deterministic task-derived fallback `implement: <first line of task, truncated>`. Returns
-/// (message, used_fallback). `raw` is the file content (None if absent/unreadable/oversize/NUL/non-UTF-8).
-pub fn commit_message(raw: Option<String>, task: &str) -> (String, bool) {
-    if let Some(s) = raw {
-        let trimmed = s.trim();
-        if !trimmed.is_empty() {
-            return (trimmed.to_string(), false);
+/// Which candidate `commit_message` resolved to.
+#[derive(Debug, Clone, Copy, PartialEq, Eq)]
+pub enum CommitSource {
+    Typed,
+    File,
+    Title,
+    Derived,
+}
+
+/// Strip HTML comments (mirrors `bridge_core::task_spec`'s emptiness check), then NUL-strip + bound to
+/// 64 KiB + trim. Returns None if the candidate is empty/comment-only after stripping — an ABSENT candidate.
+fn sanitize_commit_candidate(raw: &str) -> Option<String> {
+    let mut out = String::with_capacity(raw.len());
+    let mut rest = raw;
+    while let Some(start) = rest.find("<!--") {
+        out.push_str(&rest[..start]);
+        let after_start = &rest[start + "<!--".len()..];
+        let Some(end) = after_start.find("-->") else {
+            rest = "";
+            break;
+        };
+        rest = &after_start[end + "-->".len()..];
+    }
+    out.push_str(rest);
+    out.retain(|c| c != '\0');
+    if out.len() > 64 * 1024 {
+        let mut cut = 64 * 1024;
+        while !out.is_char_boundary(cut) {
+            cut -= 1;
         }
+        out.truncate(cut);
+    }
+    let trimmed = out.trim();
+    if trimmed.is_empty() {
+        None
+    } else {
+        Some(trimmed.to_string())
+    }
+}
+
+/// Resolve the commit message with precedence: a typed `Commit Message` section, then the agent-written
+/// `.git/A2A_COMMIT_MSG` file, then the task-spec title, else a deterministic task-derived fallback
+/// `implement: <first line of task, truncated>`. Each of `typed`/`file` is comment-stripped + NUL-stripped +
+/// bounded to 64 KiB; a candidate that's empty/comment-only afterward is treated as absent.
+pub fn commit_message(
+    typed: Option<String>,
+    file: Option<String>,
+    title: &str,
+    task: &str,
+) -> (String, CommitSource) {
+    if let Some(s) = typed.as_deref().and_then(sanitize_commit_candidate) {
+        return (s, CommitSource::Typed);
+    }
+    if let Some(s) = file.as_deref().and_then(sanitize_commit_candidate) {
+        return (s, CommitSource::File);
+    }
+    let title = title.trim();
+    if !title.is_empty() {
+        return (title.to_string(), CommitSource::Title);
     }
     let first = task.lines().next().unwrap_or("").trim();
     let mut subj: String = first.chars().take(120).collect();
     if subj.is_empty() {
         subj = "changes".into();
     }
-    (format!("implement: {subj}"), true)
+    (format!("implement: {subj}"), CommitSource::Derived)
 }
 
 /// Read `<clone>/.git/A2A_COMMIT_MSG`, bounded to 64 KiB so an oversized/binary file can't blow memory.
@@ -695,20 +745,63 @@ mod tests {
     #[test]
     fn commit_message_file_else_fallback() {
         assert_eq!(
-            commit_message(Some("  Fix the widget\n\ndetails\n".into()), "task ignored"),
-            ("Fix the widget\n\ndetails".to_string(), false)
+            commit_message(
+                None,
+                Some("  Fix the widget\n\ndetails\n".into()),
+                "",
+                "task ignored"
+            ),
+            ("Fix the widget\n\ndetails".to_string(), CommitSource::File)
         );
         assert_eq!(
-            commit_message(None, "Add a FOO marker file to the repo root\nmore"),
+            commit_message(
+                None,
+                None,
+                "",
+                "Add a FOO marker file to the repo root\nmore"
+            ),
             (
                 "implement: Add a FOO marker file to the repo root".to_string(),
-                true
+                CommitSource::Derived
             )
         );
-        assert!(commit_message(Some("   \n  ".into()), "Tidy up").1);
+        assert_eq!(
+            commit_message(None, Some("   \n  ".into()), "", "Tidy up").1,
+            CommitSource::Derived
+        );
         let long = "x".repeat(500);
-        let (m, fb) = commit_message(None, &long);
-        assert!(fb && m.starts_with("implement: ") && m.len() <= "implement: ".len() + 120);
+        let (m, source) = commit_message(None, None, "", &long);
+        assert!(
+            source == CommitSource::Derived
+                && m.starts_with("implement: ")
+                && m.len() <= "implement: ".len() + 120
+        );
+    }
+
+    #[test]
+    fn commit_precedence_and_comment_only_falls_back_to_title() {
+        assert_eq!(
+            commit_message(Some("feat: x".into()), None, "Add foo", "task body").0,
+            "feat: x"
+        );
+        assert_eq!(
+            commit_message(
+                Some("<!-- OPTIONAL -->".into()),
+                None,
+                "Add foo endpoint",
+                "task body"
+            )
+            .0,
+            "Add foo endpoint"
+        );
+        assert_eq!(
+            commit_message(None, None, "Add foo endpoint", "task body").0,
+            "Add foo endpoint"
+        );
+        assert_eq!(
+            commit_message(None, Some("from file".into()), "T", "task").0,
+            "from file"
+        );
     }
 
     #[test]
diff --git a/bin/a2a-bridge/src/main.rs b/bin/a2a-bridge/src/main.rs
index 77cd7093..49c19117 100644
--- a/bin/a2a-bridge/src/main.rs
+++ b/bin/a2a-bridge/src/main.rs
@@ -2214,10 +2214,16 @@ async fn implement_cmd(args: &[String]) -> Result<(), BoxError> {
             return Err(format!("implement: stage check: {e}").into());
         }
     };
-    let msg = implement::commit_message(implement::read_commit_msg_file(&clone), &task);
-    if msg.1 {
+    let msg = implement::commit_message(
+        spec.section("Commit Message").map(|s| s.content.clone()),
+        implement::read_commit_msg_file(&clone),
+        spec.title.as_deref().unwrap_or(""),
+        &task,
+    );
+    if msg.1 == implement::CommitSource::Derived {
         eprintln!("[implement] no .git/A2A_COMMIT_MSG — using task-derived message");
     }
+    let msg = (msg.0, msg.1 == implement::CommitSource::Derived);
     match implement::decide(completed, guard, stage, msg) {
         implement::Action::Abort(reason) => {
             eprintln!(
diff --git a/bin/a2a-bridge/src/merge.rs b/bin/a2a-bridge/src/merge.rs
index a4617e4a..ed1e5aa6 100644
--- a/bin/a2a-bridge/src/merge.rs
+++ b/bin/a2a-bridge/src/merge.rs
@@ -462,7 +462,8 @@ pub fn merge_clone(
                 );
                 return MergeOutcome::Unlanded;
             }
-            let (msg, _) = commit_message(ck.original_message.clone(), &ck.task_brief);
+            let (msg, _) =
+                commit_message(ck.original_message.clone(), None, &ck.task_brief, &ck.task_brief);
             let rt = match reauthor_commit(clone, cur, &ck.base_commit, &msg, &op) {
                 Ok(r) => r,
                 Err(e) => {

```
