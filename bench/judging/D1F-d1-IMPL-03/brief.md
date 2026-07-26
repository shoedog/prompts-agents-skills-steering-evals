# Blind pairwise code-review judgment — D1F-d1-IMPL-03

Two different engineers (Arm A, Arm B) independently completed the SAME task
from the same starting commit. You see the task brief and both final diffs.
You do NOT know who the engineers are; judge only the work. Answer the JSON
schema exactly; a_materially_better/b_materially_better may not both be true;
both false = parity.

## Task brief (both arms received this; one may have received extra process guidance — judge the WORK, not the process)

You are IMPLEMENTING one task of the "E3 — Parallel Batch Dispatch" feature for the a2a-bridge (a Rust A2A↔ACP bridge
+ multi-agent workflow orchestrator). You have write access (danger-full-access). Work TDD.

BINDING DOCS (read the relevant task + the corrections):
- PLAN: `docs/superpowers/plans/2026-06-26-e3-batch.md` — the `## v3` (PR2-FIX-1..15) + `## v2` (PR-FIX-1..17)
  sections SUPERSEDE the v1 task snippets where they conflict. ALWAYS apply the v2/v3 corrections for your task.
- SPEC: `docs/superpowers/specs/2026-06-26-e3-batch.md` (`## v3` RR-FIX + `## v2` SR-FIX are binding).

RULES:
- Implement ONLY the task named in the input below. Write the code AND the tests from the plan (adapted per the
  v2/v3 corrections). Match the surrounding code's style.
- **VERIFICATION CAP (hard):** after writing, run AT MOST ONE targeted test command (≤120s) to sanity-check your
  task — e.g. `cargo test -p <crate> <filter>`. Do NOT run `cargo build --workspace`, `--all-targets`, clippy, or
  fmt — the CONTROLLER runs the real gates in a clean host env (your sandbox stalls `cargo` at rustc startup). If a
  test command runs >120s, KILL it and report "written, runtime-unverified".
- **DO NOT commit. DO NOT run any git-mutating command (`git add`/`commit`/`stash`/etc.).** The controller commits.
- Do NOT touch files outside your task. Do NOT modify the pre-existing untracked `examples/*.toml` / `prompts/*.md`
  or the modified `examples/a2a-bridge.slicing-analysis.toml`.
- REPORT at the end: the exact files you wrote/modified, a one-line summary of each, and the single test result
  (PASS / FAIL / runtime-unverified). Be concise. Then STOP.

## YOUR TASK: Task 4 — `SqliteStore` migration + batch methods (bridge-store)

Implement **Task 4** from `docs/superpowers/plans/2026-06-26-e3-batch.md` (the "## Task 4" section), applying these
BINDING v3 corrections:

- **PR-FIX-4:** `SqliteStore::open(path)` and `SqliteStore::open_in_memory()` are **SYNCHRONOUS** (crates/bridge-store/
  src/sqlite.rs:25/41) — call them WITHOUT `.await`, and the name is `open_in_memory()`. The store METHODS are async
  (`#[tokio::test]`), but `open*` is sync. `bridge-store` has **no `tempfile` dev-dep** — add `tempfile` to
  `[dev-dependencies]` in `crates/bridge-store/Cargo.toml` (OR write the temp db under `std::env::temp_dir()` with a
  unique name; prefer adding `tempfile`).
- **PR2-FIX-3:** also implement **`fail_batch_if_status(id, expect, error, ts)`** (CAS to `failed` writing
  `batch.error`), matching the trait method T3 added.

Implement the real `SqliteStore` impls of ALL 9 batch methods (override the T3 trait defaults):
`create_batch`, `get_batch`, `list_batches`, `active_batches` (WHERE status IN ('working','canceling')),
`batch_children` (WHERE batch_id=?), `claim_batch_child`, `cancel_batch_if_working`, `settle_batch_if_status`,
`fail_batch_if_status`.

**Migration** (idempotent, in the same place as `migrate_tasks_columns`, PRAGMA `table_info`-guarded like the existing
column adds):
- `CREATE TABLE IF NOT EXISTS batch (id TEXT PRIMARY KEY, workflow TEXT NOT NULL, concurrency INTEGER NOT NULL, total
  INTEGER NOT NULL, status TEXT NOT NULL, items_json TEXT NOT NULL, error TEXT, created_ms INTEGER NOT NULL,
  updated_ms INTEGER NOT NULL);`
- additive nullable cols on `tasks` (guarded): `ALTER TABLE tasks ADD COLUMN batch_id TEXT;` and `ADD COLUMN item_id
  TEXT;` — and READ/WRITE them in the existing task row mapper + `create`/insert + `get`/`list` SELECTs so
  `batch_id`/`item_id` round-trip.
- `CREATE UNIQUE INDEX IF NOT EXISTS idx_tasks_batch_item ON tasks(batch_id, item_id) WHERE batch_id IS NOT NULL;`

**`claim_batch_child`** — in ONE transaction, fully synchronous inside the `Mutex<Connection>` lock (NO `.await` held
across the lock): `BEGIN IMMEDIATE; SELECT id,status FROM tasks WHERE batch_id=?1 AND item_id=?2;` → if a row exists,
COMMIT and return `ExistingTerminal` if status!='working' else `ExistingWorking`; else INSERT the full child row
(status='working', batch_id, item_id, workflow_spec_json, …), COMMIT, return `Created`. Map `BatchStatus`⇄TEXT with the
same lowercase scheme as `TaskRecordStatus`. The CAS methods = `UPDATE batch SET status=?,updated_ms=? WHERE id=? AND
status=?expect` → `changes()>0`; `fail_batch_if_status` also sets `error=?`.

Tests (plan Task-4 Step 1, corrected): `sqlite_migration_idempotent_and_batch_roundtrip` (open → drop → RE-open same
path: migration idempotent; create_batch + get_batch round-trip) and `sqlite_claim_is_atomic_single_runner` (two
claims of the same item → (Created, ExistingWorking); 1 child row). Use SYNC `open`/`open_in_memory`.

VERIFICATION CAP: run ONLY `cargo test -p bridge-store sqlite_claim 2>&1 | tail -20` (≤120s; kill + report
runtime-unverified if it stalls). Report files + result. Do NOT build the workspace, do NOT commit.


## Probe question (answer in `probe_answer`, per arm)

Focus on TEST RIGOR: for each arm, would its tests FAIL on the pre-change code (regression-catching), do they cover negative/edge cases per new code path, and do they assert real behavior rather than trivially passing? Name the strongest and weakest test in each arm.

## Arm A diff

```diff
diff --git a/Cargo.lock b/Cargo.lock
index 9c0a49ad..f36dd264 100644
--- a/Cargo.lock
+++ b/Cargo.lock
@@ -607,6 +607,7 @@ dependencies = [
  "rusqlite",
  "serde",
  "serde_json",
+ "tempfile",
  "thiserror",
  "tokio",
  "tracing",
diff --git a/crates/bridge-store/Cargo.toml b/crates/bridge-store/Cargo.toml
index a10b526a..bd5d13da 100644
--- a/crates/bridge-store/Cargo.toml
+++ b/crates/bridge-store/Cargo.toml
@@ -14,3 +14,6 @@ serde_json.workspace = true
 tokio = { workspace = true }
 rusqlite.workspace = true
 fs2 = "0.4"
+
+[dev-dependencies]
+tempfile = "3"
diff --git a/crates/bridge-store/src/sqlite.rs b/crates/bridge-store/src/sqlite.rs
index e112e8d7..04dd2991 100644
--- a/crates/bridge-store/src/sqlite.rs
+++ b/crates/bridge-store/src/sqlite.rs
@@ -3,7 +3,7 @@
 use bridge_core::{
     domain::{PeerTaskId, PendingKind, PendingRequest},
     error::BridgeError,
-    ids::{NodeId, OperationId, SessionId, TaskId},
+    ids::{BatchId, NodeId, OperationId, SessionId, TaskId},
     ports::SessionStore,
 };
 use rusqlite::OptionalExtension;
@@ -138,6 +138,17 @@ impl SqliteStore {
                 event_json TEXT NOT NULL,
                 PRIMARY KEY (task_id, seq),
                 FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE CASCADE
+            );
+            CREATE TABLE IF NOT EXISTS batch (
+                id           TEXT PRIMARY KEY,
+                workflow     TEXT NOT NULL,
+                concurrency  INTEGER NOT NULL,
+                total        INTEGER NOT NULL,
+                status       TEXT NOT NULL,
+                items_json   TEXT NOT NULL,
+                error        TEXT,
+                created_ms   INTEGER NOT NULL,
+                updated_ms   INTEGER NOT NULL
             );",
         )
         .map_err(|_| BridgeError::StoreFailure)?;
@@ -164,12 +175,20 @@ fn migrate_tasks_columns(conn: &rusqlite::Connection) -> rusqlite::Result<()> {
         ("last_event_seq", "INTEGER NOT NULL DEFAULT 0"),
         ("terminal_seq", "INTEGER"),
         ("journal_complete_from_birth", "INTEGER NOT NULL DEFAULT 0"),
+        ("batch_id", "TEXT"),
+        ("item_id", "TEXT"),
     ];
     for (col, def) in additive {
         if !existing.contains(col) {
             conn.execute_batch(&format!("ALTER TABLE tasks ADD COLUMN {col} {def};"))?;
         }
     }
+    // Must run AFTER the additive loop above so `batch_id`/`item_id` exist on both
+    // fresh and migrated-from-old databases.
+    conn.execute_batch(
+        "CREATE UNIQUE INDEX IF NOT EXISTS idx_tasks_batch_item
+            ON tasks(batch_id, item_id) WHERE batch_id IS NOT NULL;",
+    )?;
 
     // Collect existing column names for `task_node_checkpoints`.
     let mut stmt2 = conn.prepare("PRAGMA table_info(task_node_checkpoints)")?;
@@ -384,8 +403,8 @@ impl bridge_core::task_store::TaskStore for SqliteStore {
         conn.execute(
             "INSERT INTO tasks(id, workflow, status, result, error, created_ms, updated_ms,
                                input, workflow_spec_json, resume_attempts, session_cwd,
-                               journal_complete_from_birth)
-             VALUES(?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9, ?10, ?11, 1)",
+                               journal_complete_from_birth, batch_id, item_id)
+             VALUES(?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9, ?10, ?11, 1, ?12, ?13)",
             rusqlite::params![
                 rec.id.as_str(),
                 rec.workflow,
@@ -397,7 +416,9 @@ impl bridge_core::task_store::TaskStore for SqliteStore {
                 rec.input,
                 rec.workflow_spec_json,
                 rec.resume_attempts as i64,
-                rec.session_cwd
+                rec.session_cwd,
+                rec.batch_id.as_ref().map(|b| b.as_str()),
+                rec.item_id
             ],
         )
         .map_err(|_| BridgeError::StoreFailure)?;
@@ -433,7 +454,8 @@ impl bridge_core::task_store::TaskStore for SqliteStore {
         let mut stmt = conn
             .prepare(
                 "SELECT id, workflow, status, result, error, created_ms, updated_ms,
-                        input, workflow_spec_json, resume_attempts, session_cwd
+                        input, workflow_spec_json, resume_attempts, session_cwd,
+                        batch_id, item_id
                  FROM tasks WHERE id=?1",
             )
             .map_err(|_| BridgeError::StoreFailure)?;
@@ -454,7 +476,8 @@ impl bridge_core::task_store::TaskStore for SqliteStore {
         let mut stmt = conn
             .prepare(
                 "SELECT id, workflow, status, result, error, created_ms, updated_ms,
-                        input, workflow_spec_json, resume_attempts, session_cwd
+                        input, workflow_spec_json, resume_attempts, session_cwd,
+                        batch_id, item_id
                  FROM tasks ORDER BY updated_ms DESC LIMIT ?1",
             )
             .map_err(|_| BridgeError::StoreFailure)?;
@@ -586,7 +609,8 @@ impl bridge_core::task_store::TaskStore for SqliteStore {
         let mut stmt = conn
             .prepare(
                 "SELECT id, workflow, status, result, error, created_ms, updated_ms,
-                        input, workflow_spec_json, resume_attempts, session_cwd
+                        input, workflow_spec_json, resume_attempts, session_cwd,
+                        batch_id, item_id
                  FROM tasks WHERE status='working'",
             )
             .map_err(|_| BridgeError::StoreFailure)?;
@@ -598,6 +622,223 @@ impl bridge_core::task_store::TaskStore for SqliteStore {
         Ok(out)
     }
 
+    async fn create_batch(
+        &self,
+        rec: &bridge_core::task_store::BatchRecord,
+    ) -> Result<(), BridgeError> {
+        let conn = self.conn.lock().unwrap();
+        conn.execute(
+            "INSERT INTO batch(id, workflow, concurrency, total, status, items_json, error,
+                                created_ms, updated_ms)
+             VALUES(?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9)",
+            rusqlite::params![
+                rec.id.as_str(),
+                rec.workflow,
+                rec.concurrency as i64,
+                rec.total as i64,
+                batch_status_str(rec.status),
+                rec.items_json,
+                rec.error,
+                rec.created_ms,
+                rec.updated_ms,
+            ],
+        )
+        .map_err(|_| BridgeError::StoreFailure)?;
+        Ok(())
+    }
+
+    async fn get_batch(
+        &self,
+        id: &BatchId,
+    ) -> Result<Option<bridge_core::task_store::BatchRecord>, BridgeError> {
+        let conn = self.conn.lock().unwrap();
+        let mut stmt = conn
+            .prepare(
+                "SELECT id, workflow, concurrency, total, status, items_json, error,
+                        created_ms, updated_ms
+                 FROM batch WHERE id=?1",
+            )
+            .map_err(|_| BridgeError::StoreFailure)?;
+        let mut rows = stmt
+            .query(rusqlite::params![id.as_str()])
+            .map_err(|_| BridgeError::StoreFailure)?;
+        match rows.next().map_err(|_| BridgeError::StoreFailure)? {
+            None => Ok(None),
+            Some(row) => Ok(Some(row_to_batch(row)?)),
+        }
+    }
+
+    async fn list_batches(
+        &self,
+        limit: usize,
+    ) -> Result<Vec<bridge_core::task_store::BatchRecord>, BridgeError> {
+        let conn = self.conn.lock().unwrap();
+        let mut stmt = conn
+            .prepare(
+                "SELECT id, workflow, concurrency, total, status, items_json, error,
+                        created_ms, updated_ms
+                 FROM batch ORDER BY updated_ms DESC LIMIT ?1",
+            )
+            .map_err(|_| BridgeError::StoreFailure)?;
+        let mut rows = stmt
+            .query(rusqlite::params![limit as i64])
+            .map_err(|_| BridgeError::StoreFailure)?;
+        let mut out = Vec::new();
+        while let Some(row) = rows.next().map_err(|_| BridgeError::StoreFailure)? {
+            out.push(row_to_batch(row)?);
+        }
+        Ok(out)
+    }
+
+    async fn active_batches(
+        &self,
+    ) -> Result<Vec<bridge_core::task_store::BatchRecord>, BridgeError> {
+        let conn = self.conn.lock().unwrap();
+        let mut stmt = conn
+            .prepare(
+                "SELECT id, workflow, concurrency, total, status, items_json, error,
+                        created_ms, updated_ms
+                 FROM batch WHERE status IN ('working','canceling')",
+            )
+            .map_err(|_| BridgeError::StoreFailure)?;
+        let mut rows = stmt.query([]).map_err(|_| BridgeError::StoreFailure)?;
+        let mut out = Vec::new();
+        while let Some(row) = rows.next().map_err(|_| BridgeError::StoreFailure)? {
+            out.push(row_to_batch(row)?);
+        }
+        Ok(out)
+    }
+
+    async fn batch_children(
+        &self,
+        id: &BatchId,
+    ) -> Result<Vec<bridge_core::task_store::TaskRecord>, BridgeError> {
+        let conn = self.conn.lock().unwrap();
+        let mut stmt = conn
+            .prepare(
+                "SELECT id, workflow, status, result, error, created_ms, updated_ms,
+                        input, workflow_spec_json, resume_attempts, session_cwd,
+                        batch_id, item_id
+                 FROM tasks WHERE batch_id=?1",
+            )
+            .map_err(|_| BridgeError::StoreFailure)?;
+        let mut rows = stmt
+            .query(rusqlite::params![id.as_str()])
+            .map_err(|_| BridgeError::StoreFailure)?;
+        let mut out = Vec::new();
+        while let Some(row) = rows.next().map_err(|_| BridgeError::StoreFailure)? {
+            out.push(row_to_task(row)?);
+        }
+        Ok(out)
+    }
+
+    async fn claim_batch_child(
+        &self,
+        batch: &BatchId,
+        item: &str,
+        rec: &bridge_core::task_store::TaskRecord,
+    ) -> Result<bridge_core::task_store::ChildClaim, BridgeError> {
+        use bridge_core::task_store::ChildClaim;
+        let conn = self.conn.lock().unwrap();
+        // BEGIN IMMEDIATE: acquire the write lock up front so the observe-then-insert
+        // below can't interleave with a concurrent claim on the same (batch, item).
+        let tx = rusqlite::Transaction::new_unchecked(
+            &conn,
+            rusqlite::TransactionBehavior::Immediate,
+        )
+        .map_err(|_| BridgeError::StoreFailure)?;
+        let existing: Option<String> = tx
+            .query_row(
+                "SELECT status FROM tasks WHERE batch_id=?1 AND item_id=?2",
+                rusqlite::params![batch.as_str(), item],
+                |row| row.get(0),
+            )
+            .optional()
+            .map_err(|_| BridgeError::StoreFailure)?;
+        if let Some(status_s) = existing {
+            tx.commit().map_err(|_| BridgeError::StoreFailure)?;
+            return Ok(if status_s == "working" {
+                ChildClaim::ExistingWorking
+            } else {
+                ChildClaim::ExistingTerminal
+            });
+        }
+        tx.execute(
+            "INSERT INTO tasks(id, workflow, status, result, error, created_ms, updated_ms,
+                                input, workflow_spec_json, resume_attempts, session_cwd,
+                                journal_complete_from_birth, batch_id, item_id)
+             VALUES(?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9, ?10, ?11, 1, ?12, ?13)",
+            rusqlite::params![
+                rec.id.as_str(),
+                rec.workflow,
+                rec.status.as_str(),
+                rec.result,
+                rec.error,
+                rec.created_ms,
+                rec.updated_ms,
+                rec.input,
+                rec.workflow_spec_json,
+                rec.resume_attempts as i64,
+                rec.session_cwd,
+                batch.as_str(),
+                item,
+            ],
+        )
+        .map_err(|_| BridgeError::StoreFailure)?;
+        tx.commit().map_err(|_| BridgeError::StoreFailure)?;
+        Ok(ChildClaim::Created)
+    }
+
+    async fn cancel_batch_if_working(&self, id: &BatchId, ts: i64) -> Result<bool, BridgeError> {
+        let conn = self.conn.lock().unwrap();
+        let n = conn
+            .execute(
+                "UPDATE batch SET status='canceling', updated_ms=?1 WHERE id=?2 AND status='working'",
+                rusqlite::params![ts, id.as_str()],
+            )
+            .map_err(|_| BridgeError::StoreFailure)?;
+        Ok(n > 0)
+    }
+
+    async fn settle_batch_if_status(
+        &self,
+        id: &BatchId,
+        expect: bridge_core::task_store::BatchStatus,
+        new: bridge_core::task_store::BatchStatus,
+        ts: i64,
+    ) -> Result<bool, BridgeError> {
+        let conn = self.conn.lock().unwrap();
+        let n = conn
+            .execute(
+                "UPDATE batch SET status=?1, updated_ms=?2 WHERE id=?3 AND status=?4",
+                rusqlite::params![
+                    batch_status_str(new),
+                    ts,
+                    id.as_str(),
+                    batch_status_str(expect)
+                ],
+            )
+            .map_err(|_| BridgeError::StoreFailure)?;
+        Ok(n > 0)
+    }
+
+    async fn fail_batch_if_status(
+        &self,
+        id: &BatchId,
+        expect: bridge_core::task_store::BatchStatus,
+        error: &str,
+        ts: i64,
+    ) -> Result<bool, BridgeError> {
+        let conn = self.conn.lock().unwrap();
+        let n = conn
+            .execute(
+                "UPDATE batch SET status='failed', error=?1, updated_ms=?2 WHERE id=?3 AND status=?4",
+                rusqlite::params![error, ts, id.as_str(), batch_status_str(expect)],
+            )
+            .map_err(|_| BridgeError::StoreFailure)?;
+        Ok(n > 0)
+    }
+
     async fn record_node_started(
         &self,
         task: &TaskId,
@@ -1011,6 +1252,54 @@ impl bridge_core::task_store::TaskStore for SqliteStore {
     }
 }
 
+/// Lowercase wire/storage token for `BatchStatus`, matching `TaskRecordStatus::as_str`'s scheme.
+fn batch_status_str(s: bridge_core::task_store::BatchStatus) -> &'static str {
+    use bridge_core::task_store::BatchStatus;
+    match s {
+        BatchStatus::Working => "working",
+        BatchStatus::Completed => "completed",
+        BatchStatus::Canceling => "canceling",
+        BatchStatus::Canceled => "canceled",
+        BatchStatus::Failed => "failed",
+    }
+}
+
+fn parse_batch_status(s: &str) -> Result<bridge_core::task_store::BatchStatus, BridgeError> {
+    use bridge_core::task_store::BatchStatus;
+    match s {
+        "working" => Ok(BatchStatus::Working),
+        "completed" => Ok(BatchStatus::Completed),
+        "canceling" => Ok(BatchStatus::Canceling),
+        "canceled" => Ok(BatchStatus::Canceled),
+        "failed" => Ok(BatchStatus::Failed),
+        _ => Err(BridgeError::StoreFailure),
+    }
+}
+
+fn row_to_batch(row: &rusqlite::Row) -> Result<bridge_core::task_store::BatchRecord, BridgeError> {
+    use bridge_core::task_store::BatchRecord;
+    let id: String = row.get(0).map_err(|_| BridgeError::StoreFailure)?;
+    let workflow: String = row.get(1).map_err(|_| BridgeError::StoreFailure)?;
+    let concurrency: i64 = row.get(2).map_err(|_| BridgeError::StoreFailure)?;
+    let total: i64 = row.get(3).map_err(|_| BridgeError::StoreFailure)?;
+    let status_s: String = row.get(4).map_err(|_| BridgeError::StoreFailure)?;
+    let items_json: String = row.get(5).map_err(|_| BridgeError::StoreFailure)?;
+    let error: Option<String> = row.get(6).map_err(|_| BridgeError::StoreFailure)?;
+    let created_ms: i64 = row.get(7).map_err(|_| BridgeError::StoreFailure)?;
+    let updated_ms: i64 = row.get(8).map_err(|_| BridgeError::StoreFailure)?;
+    Ok(BatchRecord {
+        id: BatchId::parse(id).map_err(|_| BridgeError::StoreFailure)?,
+        workflow,
+        concurrency: concurrency as u32,
+        total: total as u32,
+        status: parse_batch_status(&status_s)?,
+        items_json,
+        error,
+        created_ms,
+        updated_ms,
+    })
+}
+
 fn row_to_task(row: &rusqlite::Row) -> Result<bridge_core::task_store::TaskRecord, BridgeError> {
     use bridge_core::task_store::{TaskRecord, TaskRecordStatus};
     let id: String = row.get(0).map_err(|_| BridgeError::StoreFailure)?;
@@ -1024,6 +1313,8 @@ fn row_to_task(row: &rusqlite::Row) -> Result<bridge_core::task_store::TaskRecor
     let workflow_spec_json: Option<String> = row.get(8).map_err(|_| BridgeError::StoreFailure)?;
     let resume_attempts: Option<i64> = row.get(9).map_err(|_| BridgeError::StoreFailure)?;
     let session_cwd: Option<String> = row.get(10).map_err(|_| BridgeError::StoreFailure)?;
+    let batch_id: Option<String> = row.get(11).map_err(|_| BridgeError::StoreFailure)?;
+    let item_id: Option<String> = row.get(12).map_err(|_| BridgeError::StoreFailure)?;
     Ok(TaskRecord {
         id: TaskId::parse(id).map_err(|_| BridgeError::StoreFailure)?,
         workflow,
@@ -1036,8 +1327,11 @@ fn row_to_task(row: &rusqlite::Row) -> Result<bridge_core::task_store::TaskRecor
         workflow_spec_json,
         resume_attempts: resume_attempts.unwrap_or(0) as u32,
         session_cwd,
-        batch_id: None,
-        item_id: None,
+        batch_id: batch_id
+            .map(bridge_core::ids::BatchId::parse)
+            .transpose()
+            .map_err(|_| BridgeError::StoreFailure)?,
+        item_id,
     })
 }
 
@@ -1730,4 +2024,95 @@ mod tests {
             .unwrap();
         assert!(b > a, "seq continues across a resumed run, not reset");
     }
+
+    fn sample_batch(
+        bid: &BatchId,
+        status: bridge_core::task_store::BatchStatus,
+        total: u32,
+        ms: i64,
+    ) -> bridge_core::task_store::BatchRecord {
+        bridge_core::task_store::BatchRecord {
+            id: bid.clone(),
+            workflow: "code-review".into(),
+            concurrency: 2,
+            total,
+            status,
+            items_json: r#"{"v":1,"items":[]}"#.into(),
+            error: None,
+            created_ms: ms,
+            updated_ms: ms,
+        }
+    }
+
+    fn batch_child_record(tid: &TaskId, bid: &BatchId, item: &str) -> TaskRecord {
+        TaskRecord {
+            id: tid.clone(),
+            workflow: "code-review".into(),
+            status: TaskRecordStatus::Working,
+            result: None,
+            error: None,
+            created_ms: 0,
+            updated_ms: 0,
+            input: "DIFF".into(),
+            workflow_spec_json: Some(r#"{"v":1,"nodes":[]}"#.into()),
+            resume_attempts: 0,
+            session_cwd: None,
+            batch_id: Some(bid.clone()),
+            item_id: Some(item.to_string()),
+        }
+    }
+
+    #[tokio::test]
+    async fn sqlite_migration_idempotent_and_batch_roundtrip() {
+        let dir = tempfile::tempdir().unwrap();
+        let path = dir.path().join("t.db");
+        {
+            let s = SqliteStore::open(&path).unwrap(); // creates schema
+            drop(s);
+        }
+        let s = SqliteStore::open(&path).unwrap(); // RE-OPEN: migration must be idempotent
+        let bid = BatchId::parse("b1").unwrap();
+        s.create_batch(&sample_batch(
+            &bid,
+            bridge_core::task_store::BatchStatus::Working,
+            2,
+            0,
+        ))
+        .await
+        .unwrap();
+        assert_eq!(s.get_batch(&bid).await.unwrap().unwrap().total, 2);
+    }
+
+    #[tokio::test]
+    async fn sqlite_claim_is_atomic_single_runner() {
+        use bridge_core::task_store::ChildClaim;
+        let s = SqliteStore::open_in_memory().unwrap();
+        let bid = BatchId::parse("b1").unwrap();
+        s.create_batch(&sample_batch(
+            &bid,
+            bridge_core::task_store::BatchStatus::Working,
+            1,
+            0,
+        ))
+        .await
+        .unwrap();
+        let a = s
+            .claim_batch_child(
+                &bid,
+                "x",
+                &batch_child_record(&TaskId::parse("t1").unwrap(), &bid, "x"),
+            )
+            .await
+            .unwrap();
+        let b = s
+            .claim_batch_child(
+                &bid,
+                "x",
+                &batch_child_record(&TaskId::parse("t2").unwrap(), &bid, "x"),
+            )
+            .await
+            .unwrap();
+        assert_eq!((a, b), (ChildClaim::Created, ChildClaim::ExistingWorking));
+        assert_eq!(s.batch_children(&bid).await.unwrap().len(), 1); // unique index held
+    }
 }

```

## Arm B diff

```diff
diff --git a/Cargo.lock b/Cargo.lock
index 9c0a49ad..f36dd264 100644
--- a/Cargo.lock
+++ b/Cargo.lock
@@ -607,6 +607,7 @@ dependencies = [
  "rusqlite",
  "serde",
  "serde_json",
+ "tempfile",
  "thiserror",
  "tokio",
  "tracing",
diff --git a/crates/bridge-store/Cargo.toml b/crates/bridge-store/Cargo.toml
index a10b526a..bd5d13da 100644
--- a/crates/bridge-store/Cargo.toml
+++ b/crates/bridge-store/Cargo.toml
@@ -14,3 +14,6 @@ serde_json.workspace = true
 tokio = { workspace = true }
 rusqlite.workspace = true
 fs2 = "0.4"
+
+[dev-dependencies]
+tempfile = "3"
diff --git a/crates/bridge-store/src/sqlite.rs b/crates/bridge-store/src/sqlite.rs
index e112e8d7..1dad7815 100644
--- a/crates/bridge-store/src/sqlite.rs
+++ b/crates/bridge-store/src/sqlite.rs
@@ -3,7 +3,7 @@
 use bridge_core::{
     domain::{PeerTaskId, PendingKind, PendingRequest},
     error::BridgeError,
-    ids::{NodeId, OperationId, SessionId, TaskId},
+    ids::{BatchId, NodeId, OperationId, SessionId, TaskId},
     ports::SessionStore,
 };
 use rusqlite::OptionalExtension;
@@ -164,6 +164,8 @@ fn migrate_tasks_columns(conn: &rusqlite::Connection) -> rusqlite::Result<()> {
         ("last_event_seq", "INTEGER NOT NULL DEFAULT 0"),
         ("terminal_seq", "INTEGER"),
         ("journal_complete_from_birth", "INTEGER NOT NULL DEFAULT 0"),
+        ("batch_id", "TEXT"),
+        ("item_id", "TEXT"),
     ];
     for (col, def) in additive {
         if !existing.contains(col) {
@@ -183,6 +185,25 @@ fn migrate_tasks_columns(conn: &rusqlite::Connection) -> rusqlite::Result<()> {
         conn.execute_batch("ALTER TABLE task_node_checkpoints ADD COLUMN usage_json TEXT;")?;
     }
 
+    // E3 batch dispatch: the batch table plus the (batch_id, item_id) uniqueness
+    // guard on tasks. Partial index — non-batch rows have NULL batch_id and are
+    // exempt. Must run AFTER the batch_id/item_id column adds above.
+    conn.execute_batch(
+        "CREATE TABLE IF NOT EXISTS batch (
+            id TEXT PRIMARY KEY,
+            workflow TEXT NOT NULL,
+            concurrency INTEGER NOT NULL,
+            total INTEGER NOT NULL,
+            status TEXT NOT NULL,
+            items_json TEXT NOT NULL,
+            error TEXT,
+            created_ms INTEGER NOT NULL,
+            updated_ms INTEGER NOT NULL
+        );
+        CREATE UNIQUE INDEX IF NOT EXISTS idx_tasks_batch_item
+            ON tasks(batch_id, item_id) WHERE batch_id IS NOT NULL;",
+    )?;
+
     Ok(())
 }
 
@@ -384,8 +405,8 @@ impl bridge_core::task_store::TaskStore for SqliteStore {
         conn.execute(
             "INSERT INTO tasks(id, workflow, status, result, error, created_ms, updated_ms,
                                input, workflow_spec_json, resume_attempts, session_cwd,
-                               journal_complete_from_birth)
-             VALUES(?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9, ?10, ?11, 1)",
+                               journal_complete_from_birth, batch_id, item_id)
+             VALUES(?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9, ?10, ?11, 1, ?12, ?13)",
             rusqlite::params![
                 rec.id.as_str(),
                 rec.workflow,
@@ -397,7 +418,9 @@ impl bridge_core::task_store::TaskStore for SqliteStore {
                 rec.input,
                 rec.workflow_spec_json,
                 rec.resume_attempts as i64,
-                rec.session_cwd
+                rec.session_cwd,
+                rec.batch_id.as_ref().map(|b| b.as_str()),
+                rec.item_id
             ],
         )
         .map_err(|_| BridgeError::StoreFailure)?;
@@ -433,7 +456,8 @@ impl bridge_core::task_store::TaskStore for SqliteStore {
         let mut stmt = conn
             .prepare(
                 "SELECT id, workflow, status, result, error, created_ms, updated_ms,
-                        input, workflow_spec_json, resume_attempts, session_cwd
+                        input, workflow_spec_json, resume_attempts, session_cwd,
+                        batch_id, item_id
                  FROM tasks WHERE id=?1",
             )
             .map_err(|_| BridgeError::StoreFailure)?;
@@ -454,7 +478,8 @@ impl bridge_core::task_store::TaskStore for SqliteStore {
         let mut stmt = conn
             .prepare(
                 "SELECT id, workflow, status, result, error, created_ms, updated_ms,
-                        input, workflow_spec_json, resume_attempts, session_cwd
+                        input, workflow_spec_json, resume_attempts, session_cwd,
+                        batch_id, item_id
                  FROM tasks ORDER BY updated_ms DESC LIMIT ?1",
             )
             .map_err(|_| BridgeError::StoreFailure)?;
@@ -586,7 +611,8 @@ impl bridge_core::task_store::TaskStore for SqliteStore {
         let mut stmt = conn
             .prepare(
                 "SELECT id, workflow, status, result, error, created_ms, updated_ms,
-                        input, workflow_spec_json, resume_attempts, session_cwd
+                        input, workflow_spec_json, resume_attempts, session_cwd,
+                        batch_id, item_id
                  FROM tasks WHERE status='working'",
             )
             .map_err(|_| BridgeError::StoreFailure)?;
@@ -598,6 +624,225 @@ impl bridge_core::task_store::TaskStore for SqliteStore {
         Ok(out)
     }
 
+    async fn create_batch(
+        &self,
+        rec: &bridge_core::task_store::BatchRecord,
+    ) -> Result<(), BridgeError> {
+        let conn = self.conn.lock().unwrap();
+        conn.execute(
+            "INSERT INTO batch(id, workflow, concurrency, total, status, items_json,
+                               error, created_ms, updated_ms)
+             VALUES(?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9)",
+            rusqlite::params![
+                rec.id.as_str(),
+                rec.workflow,
+                rec.concurrency as i64,
+                rec.total as i64,
+                batch_status_str(rec.status),
+                rec.items_json,
+                rec.error,
+                rec.created_ms,
+                rec.updated_ms
+            ],
+        )
+        .map_err(|_| BridgeError::StoreFailure)?;
+        Ok(())
+    }
+
+    async fn get_batch(
+        &self,
+        id: &BatchId,
+    ) -> Result<Option<bridge_core::task_store::BatchRecord>, BridgeError> {
+        let conn = self.conn.lock().unwrap();
+        let mut stmt = conn
+            .prepare(
+                "SELECT id, workflow, concurrency, total, status, items_json,
+                        error, created_ms, updated_ms
+                 FROM batch WHERE id=?1",
+            )
+            .map_err(|_| BridgeError::StoreFailure)?;
+        let mut rows = stmt
+            .query(rusqlite::params![id.as_str()])
+            .map_err(|_| BridgeError::StoreFailure)?;
+        match rows.next().map_err(|_| BridgeError::StoreFailure)? {
+            None => Ok(None),
+            Some(row) => Ok(Some(row_to_batch(row)?)),
+        }
+    }
+
+    async fn list_batches(
+        &self,
+        limit: usize,
+    ) -> Result<Vec<bridge_core::task_store::BatchRecord>, BridgeError> {
+        let conn = self.conn.lock().unwrap();
+        let mut stmt = conn
+            .prepare(
+                "SELECT id, workflow, concurrency, total, status, items_json,
+                        error, created_ms, updated_ms
+                 FROM batch ORDER BY updated_ms DESC LIMIT ?1",
+            )
+            .map_err(|_| BridgeError::StoreFailure)?;
+        let mut rows = stmt
+            .query(rusqlite::params![limit as i64])
+            .map_err(|_| BridgeError::StoreFailure)?;
+        let mut out = Vec::new();
+        while let Some(row) = rows.next().map_err(|_| BridgeError::StoreFailure)? {
+            out.push(row_to_batch(row)?);
+        }
+        Ok(out)
+    }
+
+    async fn active_batches(
+        &self,
+    ) -> Result<Vec<bridge_core::task_store::BatchRecord>, BridgeError> {
+        let conn = self.conn.lock().unwrap();
+        let mut stmt = conn
+            .prepare(
+                "SELECT id, workflow, concurrency, total, status, items_json,
+                        error, created_ms, updated_ms
+                 FROM batch WHERE status IN ('working','canceling')",
+            )
+            .map_err(|_| BridgeError::StoreFailure)?;
+        let mut rows = stmt.query([]).map_err(|_| BridgeError::StoreFailure)?;
+        let mut out = Vec::new();
+        while let Some(row) = rows.next().map_err(|_| BridgeError::StoreFailure)? {
+            out.push(row_to_batch(row)?);
+        }
+        Ok(out)
+    }
+
+    async fn batch_children(
+        &self,
+        id: &BatchId,
+    ) -> Result<Vec<bridge_core::task_store::TaskRecord>, BridgeError> {
+        let conn = self.conn.lock().unwrap();
+        let mut stmt = conn
+            .prepare(
+                "SELECT id, workflow, status, result, error, created_ms, updated_ms,
+                        input, workflow_spec_json, resume_attempts, session_cwd,
+                        batch_id, item_id
+                 FROM tasks WHERE batch_id=?1",
+            )
+            .map_err(|_| BridgeError::StoreFailure)?;
+        let mut rows = stmt
+            .query(rusqlite::params![id.as_str()])
+            .map_err(|_| BridgeError::StoreFailure)?;
+        let mut out = Vec::new();
+        while let Some(row) = rows.next().map_err(|_| BridgeError::StoreFailure)? {
+            out.push(row_to_task(row)?);
+        }
+        Ok(out)
+    }
+
+    async fn claim_batch_child(
+        &self,
+        batch: &BatchId,
+        item: &str,
+        rec: &bridge_core::task_store::TaskRecord,
+    ) -> Result<bridge_core::task_store::ChildClaim, BridgeError> {
+        use bridge_core::task_store::ChildClaim;
+        // Fully synchronous inside the Mutex — the guard is never held across an
+        // `.await`. BEGIN IMMEDIATE takes the write lock up front so the
+        // SELECT-then-INSERT pair is one atomic claim.
+        let conn = self.conn.lock().unwrap();
+        let tx = rusqlite::Transaction::new_unchecked(
+            &conn,
+            rusqlite::TransactionBehavior::Immediate,
+        )
+        .map_err(|_| BridgeError::StoreFailure)?;
+        let existing: Option<String> = tx
+            .query_row(
+                "SELECT status FROM tasks WHERE batch_id=?1 AND item_id=?2",
+                rusqlite::params![batch.as_str(), item],
+                |row| row.get(0),
+            )
+            .optional()
+            .map_err(|_| BridgeError::StoreFailure)?;
+        if let Some(status) = existing {
+            tx.commit().map_err(|_| BridgeError::StoreFailure)?;
+            return Ok(if status == "working" {
+                ChildClaim::ExistingWorking
+            } else {
+                ChildClaim::ExistingTerminal
+            });
+        }
+        tx.execute(
+            "INSERT INTO tasks(id, workflow, status, result, error, created_ms, updated_ms,
+                               input, workflow_spec_json, resume_attempts, session_cwd,
+                               journal_complete_from_birth, batch_id, item_id)
+             VALUES(?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9, ?10, ?11, 1, ?12, ?13)",
+            rusqlite::params![
+                rec.id.as_str(),
+                rec.workflow,
+                rec.status.as_str(),
+                rec.result,
+                rec.error,
+                rec.created_ms,
+                rec.updated_ms,
+                rec.input,
+                rec.workflow_spec_json,
+                rec.resume_attempts as i64,
+                rec.session_cwd,
+                batch.as_str(),
+                item
+            ],
+        )
+        .map_err(|_| BridgeError::StoreFailure)?;
+        tx.commit().map_err(|_| BridgeError::StoreFailure)?;
+        Ok(ChildClaim::Created)
+    }
+
+    async fn cancel_batch_if_working(&self, id: &BatchId, ts: i64) -> Result<bool, BridgeError> {
+        let conn = self.conn.lock().unwrap();
+        let n = conn
+            .execute(
+                "UPDATE batch SET status='canceling', updated_ms=?1 WHERE id=?2 AND status='working'",
+                rusqlite::params![ts, id.as_str()],
+            )
+            .map_err(|_| BridgeError::StoreFailure)?;
+        Ok(n > 0)
+    }
+
+    async fn settle_batch_if_status(
+        &self,
+        id: &BatchId,
+        expect: bridge_core::task_store::BatchStatus,
+        new: bridge_core::task_store::BatchStatus,
+        ts: i64,
+    ) -> Result<bool, BridgeError> {
+        let conn = self.conn.lock().unwrap();
+        let n = conn
+            .execute(
+                "UPDATE batch SET status=?1, updated_ms=?2 WHERE id=?3 AND status=?4",
+                rusqlite::params![
+                    batch_status_str(new),
+                    ts,
+                    id.as_str(),
+                    batch_status_str(expect)
+                ],
+            )
+            .map_err(|_| BridgeError::StoreFailure)?;
+        Ok(n > 0)
+    }
+
+    async fn fail_batch_if_status(
+        &self,
+        id: &BatchId,
+        expect: bridge_core::task_store::BatchStatus,
+        error: &str,
+        ts: i64,
+    ) -> Result<bool, BridgeError> {
+        let conn = self.conn.lock().unwrap();
+        let n = conn
+            .execute(
+                "UPDATE batch SET status='failed', error=?1, updated_ms=?2
+                 WHERE id=?3 AND status=?4",
+                rusqlite::params![error, ts, id.as_str(), batch_status_str(expect)],
+            )
+            .map_err(|_| BridgeError::StoreFailure)?;
+        Ok(n > 0)
+    }
+
     async fn record_node_started(
         &self,
         task: &TaskId,
@@ -1011,6 +1256,55 @@ impl bridge_core::task_store::TaskStore for SqliteStore {
     }
 }
 
+/// Lowercase storage token for a batch status (same scheme as `TaskRecordStatus`).
+fn batch_status_str(s: bridge_core::task_store::BatchStatus) -> &'static str {
+    use bridge_core::task_store::BatchStatus;
+    match s {
+        BatchStatus::Working => "working",
+        BatchStatus::Completed => "completed",
+        BatchStatus::Canceling => "canceling",
+        BatchStatus::Canceled => "canceled",
+        BatchStatus::Failed => "failed",
+    }
+}
+
+/// Parse a stored batch-status token; unknown → None.
+fn parse_batch_status(s: &str) -> Option<bridge_core::task_store::BatchStatus> {
+    use bridge_core::task_store::BatchStatus;
+    match s {
+        "working" => Some(BatchStatus::Working),
+        "completed" => Some(BatchStatus::Completed),
+        "canceling" => Some(BatchStatus::Canceling),
+        "canceled" => Some(BatchStatus::Canceled),
+        "failed" => Some(BatchStatus::Failed),
+        _ => None,
+    }
+}
+
+fn row_to_batch(row: &rusqlite::Row) -> Result<bridge_core::task_store::BatchRecord, BridgeError> {
+    use bridge_core::task_store::BatchRecord;
+    let id: String = row.get(0).map_err(|_| BridgeError::StoreFailure)?;
+    let workflow: String = row.get(1).map_err(|_| BridgeError::StoreFailure)?;
+    let concurrency: i64 = row.get(2).map_err(|_| BridgeError::StoreFailure)?;
+    let total: i64 = row.get(3).map_err(|_| BridgeError::StoreFailure)?;
+    let status_s: String = row.get(4).map_err(|_| BridgeError::StoreFailure)?;
+    let items_json: String = row.get(5).map_err(|_| BridgeError::StoreFailure)?;
+    let error: Option<String> = row.get(6).map_err(|_| BridgeError::StoreFailure)?;
+    let created_ms: i64 = row.get(7).map_err(|_| BridgeError::StoreFailure)?;
+    let updated_ms: i64 = row.get(8).map_err(|_| BridgeError::StoreFailure)?;
+    Ok(BatchRecord {
+        id: BatchId::parse(id).map_err(|_| BridgeError::StoreFailure)?,
+        workflow,
+        concurrency: concurrency as u32,
+        total: total as u32,
+        status: parse_batch_status(&status_s).ok_or(BridgeError::StoreFailure)?,
+        items_json,
+        error,
+        created_ms,
+        updated_ms,
+    })
+}
+
 fn row_to_task(row: &rusqlite::Row) -> Result<bridge_core::task_store::TaskRecord, BridgeError> {
     use bridge_core::task_store::{TaskRecord, TaskRecordStatus};
     let id: String = row.get(0).map_err(|_| BridgeError::StoreFailure)?;
@@ -1024,6 +1318,8 @@ fn row_to_task(row: &rusqlite::Row) -> Result<bridge_core::task_store::TaskRecor
     let workflow_spec_json: Option<String> = row.get(8).map_err(|_| BridgeError::StoreFailure)?;
     let resume_attempts: Option<i64> = row.get(9).map_err(|_| BridgeError::StoreFailure)?;
     let session_cwd: Option<String> = row.get(10).map_err(|_| BridgeError::StoreFailure)?;
+    let batch_id: Option<String> = row.get(11).map_err(|_| BridgeError::StoreFailure)?;
+    let item_id: Option<String> = row.get(12).map_err(|_| BridgeError::StoreFailure)?;
     Ok(TaskRecord {
         id: TaskId::parse(id).map_err(|_| BridgeError::StoreFailure)?,
         workflow,
@@ -1036,8 +1332,11 @@ fn row_to_task(row: &rusqlite::Row) -> Result<bridge_core::task_store::TaskRecor
         workflow_spec_json,
         resume_attempts: resume_attempts.unwrap_or(0) as u32,
         session_cwd,
-        batch_id: None,
-        item_id: None,
+        batch_id: batch_id
+            .map(BatchId::parse)
+            .transpose()
+            .map_err(|_| BridgeError::StoreFailure)?,
+        item_id,
     })
 }
 
@@ -1047,7 +1346,9 @@ mod tests {
     use bridge_core::domain::{PeerTaskId, PendingKind, PendingRequest};
     use bridge_core::ids::{SessionId, TaskId};
     use bridge_core::ports::SessionStore;
-    use bridge_core::task_store::{TaskRecord, TaskRecordStatus, TaskStore};
+    use bridge_core::task_store::{
+        BatchRecord, BatchStatus, ChildClaim, TaskRecord, TaskRecordStatus, TaskStore,
+    };
 
     fn trec(id: &str, ms: i64) -> TaskRecord {
         TaskRecord {
@@ -1730,4 +2031,125 @@ mod tests {
             .unwrap();
         assert!(b > a, "seq continues across a resumed run, not reset");
     }
+
+    fn sample_batch(bid: &BatchId, status: BatchStatus, total: u32, ms: i64) -> BatchRecord {
+        BatchRecord {
+            id: bid.clone(),
+            workflow: "code-review".into(),
+            concurrency: 2,
+            total,
+            status,
+            items_json: r#"{"v":1,"items":[]}"#.into(),
+            error: None,
+            created_ms: ms,
+            updated_ms: ms,
+        }
+    }
+
+    fn batch_child_record(tid: &TaskId, bid: &BatchId, item: &str) -> TaskRecord {
+        TaskRecord {
+            id: tid.clone(),
+            workflow: "code-review".into(),
+            status: TaskRecordStatus::Working,
+            result: None,
+            error: None,
+            created_ms: 0,
+            updated_ms: 0,
+            input: "DIFF".into(),
+            workflow_spec_json: Some(r#"{"v":1,"nodes":[]}"#.into()),
+            resume_attempts: 0,
+            session_cwd: None,
+            batch_id: Some(bid.clone()),
+            item_id: Some(item.to_string()),
+        }
+    }
+
+    #[tokio::test]
+    async fn sqlite_migration_idempotent_and_batch_roundtrip() {
+        let dir = tempfile::tempdir().unwrap();
+        let path = dir.path().join("t.db");
+        {
+            let s = SqliteStore::open(&path).unwrap(); // creates schema
+            drop(s);
+        }
+        let s = SqliteStore::open(&path).unwrap(); // RE-OPEN: migration must be idempotent
+        let bid = BatchId::parse("b1").unwrap();
+        s.create_batch(&sample_batch(&bid, BatchStatus::Working, 2, 0))
+            .await
+            .unwrap();
+        let got = s.get_batch(&bid).await.unwrap().unwrap();
+        assert_eq!(got.total, 2);
+        assert_eq!(got.status, BatchStatus::Working);
+        assert_eq!(got.items_json, r#"{"v":1,"items":[]}"#);
+        // a duplicate batch id must not upsert
+        assert!(s
+            .create_batch(&sample_batch(&bid, BatchStatus::Working, 9, 1))
+            .await
+            .is_err());
+        // batch_id/item_id round-trip through the plain create→get task path too
+        let cid = TaskId::parse("c1").unwrap();
+        s.create(&batch_child_record(&cid, &bid, "i1")).await.unwrap();
+        let child = s.get(&cid).await.unwrap().unwrap();
+        assert_eq!(child.batch_id.as_ref().map(|b| b.as_str()), Some("b1"));
+        assert_eq!(child.item_id.as_deref(), Some("i1"));
+        // CAS chain: working → canceling (once) → canceled; canceling counts as active
+        assert!(s.cancel_batch_if_working(&bid, 5).await.unwrap());
+        assert!(!s.cancel_batch_if_working(&bid, 6).await.unwrap());
+        assert_eq!(s.active_batches().await.unwrap().len(), 1);
+        assert!(s
+            .settle_batch_if_status(&bid, BatchStatus::Canceling, BatchStatus::Canceled, 7)
+            .await
+            .unwrap());
+        assert!(s.active_batches().await.unwrap().is_empty());
+        // fail CAS records the error (and no-ops when the status differs)
+        let b2 = BatchId::parse("b2").unwrap();
+        s.create_batch(&sample_batch(&b2, BatchStatus::Working, 1, 1))
+            .await
+            .unwrap();
+        assert!(s
+            .fail_batch_if_status(&b2, BatchStatus::Working, "boom", 8)
+            .await
+            .unwrap());
+        assert!(!s
+            .fail_batch_if_status(&b2, BatchStatus::Working, "again", 9)
+            .await
+            .unwrap());
+        let failed = s.get_batch(&b2).await.unwrap().unwrap();
+        assert_eq!(failed.status, BatchStatus::Failed);
+        assert_eq!(failed.error.as_deref(), Some("boom"));
+        assert_eq!(s.list_batches(10).await.unwrap().len(), 2);
+    }
+
+    #[tokio::test]
+    async fn sqlite_claim_is_atomic_single_runner() {
+        let s = SqliteStore::open_in_memory().unwrap();
+        let bid = BatchId::parse("b1").unwrap();
+        s.create_batch(&sample_batch(&bid, BatchStatus::Working, 1, 0))
+            .await
+            .unwrap();
+        let t1 = TaskId::parse("t1").unwrap();
+        let t2 = TaskId::parse("t2").unwrap();
+        let a = s
+            .claim_batch_child(&bid, "x", &batch_child_record(&t1, &bid, "x"))
+            .await
+            .unwrap();
+        let b = s
+            .claim_batch_child(&bid, "x", &batch_child_record(&t2, &bid, "x"))
+            .await
+            .unwrap();
+        assert_eq!((a, b), (ChildClaim::Created, ChildClaim::ExistingWorking));
+        let children = s.batch_children(&bid).await.unwrap();
+        assert_eq!(children.len(), 1); // unique index held
+        assert_eq!(children[0].id.as_str(), "t1");
+        assert_eq!(children[0].item_id.as_deref(), Some("x"));
+        // a terminal child re-claims as ExistingTerminal (observe, don't respawn)
+        s.set_terminal(&t1, TaskRecordStatus::Completed, Some("R"), None, 3)
+            .await
+            .unwrap();
+        let c = s
+            .claim_batch_child(&bid, "x", &batch_child_record(&t2, &bid, "x"))
+            .await
+            .unwrap();
+        assert_eq!(c, ChildClaim::ExistingTerminal);
+    }
 }

```
