# Blind pairwise code-review judgment — task IMPL-13

Two different engineers (Arm A, Arm B) independently completed the SAME task
from the same starting commit. You see the task brief and both final diffs.
You do NOT know who the engineers are; judge only the work. Both arms passed
the repo's build and the task's mechanical test evidence (suite green in both cases).

Answer the JSON schema exactly. Binary verdicts: `a_materially_better` /
`b_materially_better` may not both be true; both false = parity. "Materially
better" = a reviewer would insist the other arm adopt the difference
(correctness, safety, coverage of the specified requirements) — NOT style.

## Task brief (verbatim, both arms received this)

{
  "agent_name": "codex",
  "base_ref": "HEAD",
  "base_sha": "231905de8301042bfc403c949ec00934a94dcc37",
  "branch": "a2a/a2a6f771ac72-implement-mailbox-loop-command-retry",
  "context_id": "9f500187-47d3-4644-8b58-26e2527d74e1",
  "follow_up_threads": [
    {
      "id": "task-thread-94a0199c-4bf5-5a69-a0d7-a53d68dfd3a0",
      "messages": [],
      "metadata": {
        "createdForTaskId": "a2a6f771-ac72-4c20-af75-ae2f7eb8fa6c",
        "purpose": "follow_up",
        "source": "task-thread",
        "taskId": "a2a6f771-ac72-4c20-af75-ae2f7eb8fa6c",
        "taskKind": "implementation"
      },
      "status": "open",
      "task_id": "a2a6f771-ac72-4c20-af75-ae2f7eb8fa6c",
      "title": "Follow Up: Implement mailbox loop command retry"
    }
  ],
  "kind": "implementation",
  "metadata": {
    "runner": {
      "host": "Wesleys-MacBook-Pro.local",
      "pid": 71437,
      "startedAt": 1777521000.739549
    }
  },
  "parent_task_id": null,
  "prompt": "Implement the next persistent-mailbox ergonomics slice: a CLI loop runner around the existing session/message mailbox APIs. Scope: add a2a-bridge message loop SESSION_ID with a handler command that repeatedly polls/claims one delivery at a time, passes the claimed delivery JSON to the handler on stdin, then applies a handler action. Keep the design small and testable. Suggested semantics: options should include --context-id, --wait-seconds or --idle-timeout, --interval, --heartbeat-interval, --heartbeat-status, --claim-status, --max-deliveries, and --handler. The handler should be invoked as a local subprocess with the claimed delivery JSON on stdin. Handler stdout should be parsed as JSON object with action values reply, ack, release, or none. reply requires body and should support ack true/false, role, metadata; ack/release use the current claimToken; none leaves the delivery claimed and exits nonzero or reports clearly. On handler nonzero or invalid JSON, release the claimed delivery by default and return failure so work is not lost. Add focused tests in tests/test_cli.py and update README/docs/tests README as executable documentation. Reuse existing CLI/store helpers and keep changes scoped. Run the relevant tests before finishing. Do not merge; return summary, changed files, and test results.",
  "repo_path": "/Users/wesleyjinks/code/a2a-local-bridge",
  "task_id": "a2a6f771-ac72-4c20-af75-ae2f7eb8fa6c",
  "title": "Implement mailbox loop command retry",
  "worktree_path": "/Users/wesleyjinks/.a2a-bridge/worktrees/9f500187-47d3-4644-8b58-26e2527d74e1/a2a6f771-ac72-4c20-af75-ae2f7eb8fa6c/a2a-local-bridge"
}


## Probe question (answer in `probe_answer`, per arm)

Does the loop runner implement the full flag surface and the safety default (release claim + nonzero exit on handler failure/invalid JSON so work is not lost)? Compare test breadth: which failure modes are covered (invalid JSON, handler nonzero, max-deliveries, idle timeout, heartbeat)?

## Arm A diff

```diff
diff --git a/README.md b/README.md
index e862fc3..f242951 100644
--- a/README.md
+++ b/README.md
@@ -90,6 +90,7 @@ uv run a2a-bridge message inbox SESSION_ID
 uv run a2a-bridge message claim SESSION_ID DELIVERY_ID
 uv run a2a-bridge message claim-next SESSION_ID
 uv run a2a-bridge message poll SESSION_ID --wait-seconds 30 --ack --json
+uv run a2a-bridge message loop SESSION_ID --handler 'my-handler --flag' --idle-timeout 30 --max-deliveries 10
 uv run a2a-bridge message reply SESSION_ID DELIVERY_ID --claim-token CLAIM_TOKEN --body "Done." --ack
 uv run a2a-bridge message release SESSION_ID DELIVERY_ID --claim-token CLAIM_TOKEN
 uv run a2a-bridge message ack SESSION_ID DELIVERY_ID --claim-token CLAIM_TOKEN
@@ -185,6 +186,32 @@ Already-running agents can use `message poll` or the localhost
 atomically claim the oldest pending delivery, optionally wait for work, and can
 acknowledge immediately for simple script consumers.
 
+`message loop` builds a full mailbox worker out of those primitives. It
+repeatedly heartbeats, claims one delivery at a time, and runs the `--handler`
+command as a local subprocess with the claimed delivery JSON on stdin. The
+handler prints one JSON object on stdout choosing what happens to the claim:
+
+```json
+{"action": "reply", "body": "Done.", "ack": true, "role": "agent", "metadata": {"k": "v"}}
+{"action": "ack"}
+{"action": "release"}
+{"action": "none"}
+```
+
+`reply` posts the body back into the source thread (optionally acknowledging in
+the same step) and `ack` acknowledges the delivery, both with the loop-held
+claim token; the loop then claims the next delivery. `release` requeues the
+delivery to `pending` and stops the loop — released deliveries stay addressed
+to the same session, so continuing would immediately re-claim the same
+delivery. `none` leaves the delivery claimed for out-of-band handling — the
+loop prints the delivery ID plus claim token and stops. If the handler exits
+nonzero or prints invalid action JSON, the loop releases the claimed delivery
+back to `pending` and returns failure so work is not lost.
+`--idle-timeout` bounds how long the loop waits for the next delivery (default
+0: exit when the inbox is empty), `--max-deliveries` caps how many deliveries
+are handled, and `--interval`, `--heartbeat-interval`, `--heartbeat-status`,
+`--claim-status`, and `--context-id` match `message poll` semantics.
+
 Managed sessions use the one-shot task runner by default unless a task sets
 `agentSessionId` and the session was started with the explicit `jsonl` protocol
 in the same long-running bridge server process. The session must belong to the
diff --git a/docs/roadmap.md b/docs/roadmap.md
index b90748a..96709d0 100644
--- a/docs/roadmap.md
+++ b/docs/roadmap.md
@@ -138,6 +138,13 @@
   store, CLI, and localhost API, with the reply routed into the source message
   thread, optionally acknowledging the source delivery in the same transaction,
   and protected by the same claim-token guard.
+- `message loop` runs a CLI mailbox worker around the existing poll/claim
+  primitives: it heartbeats, claims one delivery at a time, pipes the claimed
+  delivery JSON to a `--handler` subprocess on stdin, and applies the handler's
+  reply/ack/release/none action with the loop-held claim token. Release and
+  none stop the loop (requeued or still-claimed deliveries are reported), and
+  handler failures or invalid action JSON release the claim back to `pending`
+  and return failure so deliveries are never silently lost.
 
 ## Prioritized Backlog
 
diff --git a/src/a2a_bridge/cli.py b/src/a2a_bridge/cli.py
index 8a46652..64d28a0 100644
--- a/src/a2a_bridge/cli.py
+++ b/src/a2a_bridge/cli.py
@@ -7,6 +7,7 @@ import json
 import math
 import shlex
 import sqlite3
+import subprocess
 import sys
 import time
 
@@ -56,6 +57,13 @@ def _nonnegative_float(value: str) -> float:
     return parsed
 
 
+def _positive_int(value: str) -> int:
+    parsed = int(value)
+    if parsed <= 0:
+        raise argparse.ArgumentTypeError("must be a positive integer")
+    return parsed
+
+
 def _split_optional_command(value: Optional[str]) -> Optional[list[str]]:
     return shlex.split(value) if value else None
 
@@ -542,6 +550,165 @@ def cmd_message_poll(args: argparse.Namespace) -> int:
         time.sleep(_poll_sleep_seconds(args.interval, remaining, next_heartbeat_at, now))
 
 
+_HANDLER_ACTION_KEYS = {
+    "reply": {"action", "body", "ack", "role", "metadata"},
+    "ack": {"action"},
+    "release": {"action"},
+    "none": {"action"},
+}
+
+
+def _parse_handler_action(output: str) -> Dict[str, Any]:
+    try:
+        parsed = json.loads(output)
+    except json.JSONDecodeError as exc:
+        raise ValueError("handler stdout is not valid JSON: %s" % exc)
+    if not isinstance(parsed, dict):
+        raise ValueError("handler stdout must be a JSON object")
+    action = parsed.get("action")
+    if action not in _HANDLER_ACTION_KEYS:
+        raise ValueError("handler action must be one of: reply, ack, release, none")
+    unexpected = sorted(set(parsed) - _HANDLER_ACTION_KEYS[action])
+    if unexpected:
+        raise ValueError("unexpected handler keys for %s action: %s" % (action, ", ".join(unexpected)))
+    if action == "reply":
+        body = parsed.get("body")
+        if not isinstance(body, str) or not body.strip():
+            raise ValueError("reply action requires a nonempty string body")
+        if "ack" in parsed and not isinstance(parsed["ack"], bool):
+            raise ValueError("reply ack must be a boolean")
+        if "role" in parsed and (not isinstance(parsed["role"], str) or not parsed["role"].strip()):
+            raise ValueError("reply role must be a nonempty string")
+        if "metadata" in parsed and not isinstance(parsed["metadata"], dict):
+            raise ValueError("reply metadata must be a JSON object")
+    return parsed
+
+
+def _release_loop_claim(store: Store, session_id: str, delivery_id: str, claim_token: Optional[str]) -> str:
+    if store.release_message_delivery(session_id, delivery_id, claim_token=claim_token):
+        return "released claim"
+    return "release failed; claim may still be held"
+
+
+def _apply_loop_action(
+    store: Store,
+    session_id: str,
+    delivery_id: str,
+    claim_token: Optional[str],
+    action: Dict[str, Any],
+) -> Optional[str]:
+    name = str(action["action"])
+    if name == "reply":
+        reply = store.reply_to_message_delivery(
+            session_id,
+            delivery_id,
+            body=str(action["body"]),
+            claim_token=claim_token or "",
+            role=str(action.get("role", "agent")),
+            metadata=action.get("metadata") or {"source": "cli"},
+            acknowledge=bool(action.get("ack", False)),
+        )
+        if not reply:
+            return "Delivery not found or not replyable for session: %s" % delivery_id
+    elif name == "ack":
+        if not store.acknowledge_message_delivery(session_id, delivery_id, claim_token=claim_token):
+            return "Delivery not found or not acknowledgeable for session: %s" % delivery_id
+    return None
+
+
+def cmd_message_loop(args: argparse.Namespace) -> int:
+    store = _store(args)
+    store.init()
+    handler_command = shlex.split(args.handler)
+    if not handler_command:
+        print("Handler command must not be empty.", file=sys.stderr)
+        return 1
+    handled = 0
+    deadline = time.monotonic() + args.idle_timeout
+    next_heartbeat_at = 0.0
+    while True:
+        now = time.monotonic()
+        if now >= next_heartbeat_at:
+            try:
+                store.heartbeat_agent_session(
+                    args.session_id,
+                    status=args.heartbeat_status,
+                    context_id=args.context_id,
+                )
+            except KeyError:
+                print("Session not found: %s" % args.session_id, file=sys.stderr)
+                return 1
+            next_heartbeat_at = now + args.heartbeat_interval
+        delivery = store.claim_next_message_delivery(args.session_id, context_id=args.context_id)
+        if not delivery:
+            now = time.monotonic()
+            remaining = deadline - now
+            if remaining <= 0:
+                break
+            time.sleep(_poll_sleep_seconds(args.interval, remaining, next_heartbeat_at, now))
+            continue
+        delivery_id = str(delivery["delivery_id"])
+        claim_token = _claim_token(delivery)
+        if args.claim_status:
+            store.heartbeat_agent_session(
+                args.session_id,
+                status=args.claim_status,
+                context_id=str(delivery["context_id"]),
+                task_id=delivery.get("thread_task_id"),
+                clear_task=delivery.get("thread_task_id") is None,
+            )
+        try:
+            handler = subprocess.run(
+                handler_command,
+                input=json.dumps(delivery, sort_keys=True),
+                text=True,
+                stdout=subprocess.PIPE,
+                stderr=subprocess.PIPE,
+            )
+        except OSError as exc:
+            outcome = _release_loop_claim(store, args.session_id, delivery_id, claim_token)
+            print("Handler failed to start for delivery %s: %s; %s." % (delivery_id, exc, outcome), file=sys.stderr)
+            return 1
+        if handler.stderr:
+            sys.stderr.write(handler.stderr)
+        if handler.returncode != 0:
+            outcome = _release_loop_claim(store, args.session_id, delivery_id, claim_token)
+            print(
+                "Handler exited with exit code %d for delivery %s; %s."
+                % (handler.returncode, delivery_id, outcome),
+                file=sys.stderr,
+            )
+            return 1
+        try:
+            action = _parse_handler_action(handler.stdout)
+        except ValueError as exc:
+            outcome = _release_loop_claim(store, args.session_id, delivery_id, claim_token)
+            print("Invalid handler output for delivery %s: %s; %s." % (delivery_id, exc, outcome), file=sys.stderr)
+            return 1
+        if action["action"] == "none":
+            print("Handler kept delivery %s claimed%s" % (delivery_id, _claim_token_suffix(delivery)))
+            break
+        if action["action"] == "release":
+            # A released delivery is pending again for this same session, so
+            # continuing would immediately re-claim it and livelock the loop.
+            if not store.release_message_delivery(args.session_id, delivery_id, claim_token=claim_token):
+                print("Delivery not found or not releasable for session: %s" % delivery_id, file=sys.stderr)
+                return 1
+            print("Requeued delivery %s action=release" % delivery_id)
+            break
+        error = _apply_loop_action(store, args.session_id, delivery_id, claim_token, action)
+        if error:
+            print(error, file=sys.stderr)
+            return 1
+        handled += 1
+        print("Handled delivery %s action=%s" % (delivery_id, action["action"]))
+        deadline = time.monotonic() + args.idle_timeout
+        if args.max_deliveries is not None and handled >= args.max_deliveries:
+            break
+    print("Handled %d deliveries." % handled)
+    return 0
+
+
 def cmd_message_ack(args: argparse.Namespace) -> int:
     store = _store(args)
     store.init()
@@ -1126,6 +1293,17 @@ def build_parser() -> argparse.ArgumentParser:
     message_poll.add_argument("--ack", action="store_true")
     message_poll.add_argument("--json", action="store_true")
     message_poll.set_defaults(func=cmd_message_poll)
+    message_loop = message_sub.add_parser("loop")
+    message_loop.add_argument("session_id")
+    message_loop.add_argument("--context-id")
+    message_loop.add_argument("--handler", required=True)
+    message_loop.add_argument("--idle-timeout", type=_nonnegative_float, default=0.0)
+    message_loop.add_argument("--interval", type=_positive_float, default=2.0)
+    message_loop.add_argument("--heartbeat-interval", type=_positive_float, default=30.0)
+    message_loop.add_argument("--heartbeat-status", default="idle")
+    message_loop.add_argument("--claim-status", default="active")
+    message_loop.add_argument("--max-deliveries", type=_positive_int)
+    message_loop.set_defaults(func=cmd_message_loop)
     message_ack = message_sub.add_parser("ack")
     message_ack.add_argument("session_id")
     message_ack.add_argument("delivery_id")
diff --git a/tests/README.md b/tests/README.md
index 50e1f49..4f0cc04 100644
--- a/tests/README.md
+++ b/tests/README.md
@@ -263,5 +263,17 @@ unrun.
 - persistent session, thread, inbox, claim, claim-next, poll, release, and
   acknowledge command parsing
   and workflow behavior
+- `message loop` runs a handler subprocess per claimed delivery with the
+  claimed delivery JSON on stdin
+- `message loop` applies handler `reply` (with optional ack/role/metadata) and
+  `ack` actions using the loop-held claim token, then keeps claiming
+- `message loop` handler `release` actions requeue the delivery to `pending`
+  and stop the loop instead of re-claiming the same delivery
+- `message loop` handler `none` actions leave the delivery claimed, report the
+  claim token, and stop the loop
+- `message loop` releases the claimed delivery and returns failure when the
+  handler exits nonzero, prints invalid action JSON, or omits a reply body
+- `message loop` heartbeats the session while idle, exits after
+  `--idle-timeout` with no pending work, and honors `--max-deliveries`
 - managed session start, stop, and reconcile command parsing
 - workflow template and hosting gate option parsing
diff --git a/tests/test_cli.py b/tests/test_cli.py
index ef28e6e..39b37d7 100644
--- a/tests/test_cli.py
+++ b/tests/test_cli.py
@@ -1,6 +1,8 @@
 from pathlib import Path
 from contextlib import redirect_stderr
 from io import StringIO
+import json
+import shlex
 import sys
 
 sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
@@ -591,6 +593,261 @@ class CliTests(BridgeTestCase):
         self.assertEqual(code, 0)
         self.assertIn('"timedOut": true', stdout)
 
+    def _mailbox_pair(self):
+        store = Store(self.tmp)
+        store.init()
+        context_id = store.create_context("loop cli")
+        store.upsert_agent_session("codex", context_id=context_id, session_id="lead-session")
+        store.upsert_agent_session("claude", context_id=context_id, session_id="loop-session")
+        store.add_context_participant(context_id, "lead-session", role="lead")
+        store.add_context_participant(context_id, "loop-session", role="reviewer")
+        thread_id = store.create_message_thread(context_id, "Loop thread")
+        return store, context_id, thread_id
+
+    def _handler_command(self, script):
+        path = self.tmp / "handler.py"
+        path.write_text(script, encoding="utf-8")
+        return "%s %s" % (shlex.quote(sys.executable), shlex.quote(str(path)))
+
+    def test_message_loop_command_parses_options(self):
+        args = build_parser().parse_args(
+            [
+                "message",
+                "loop",
+                "session-2",
+                "--context-id",
+                "ctx-1",
+                "--handler",
+                "handle-delivery --flag",
+                "--idle-timeout",
+                "5",
+                "--interval",
+                "0.25",
+                "--heartbeat-interval",
+                "1",
+                "--heartbeat-status",
+                "waiting",
+                "--claim-status",
+                "busy",
+                "--max-deliveries",
+                "3",
+            ]
+        )
+
+        self.assertEqual(args.session_id, "session-2")
+        self.assertEqual(args.context_id, "ctx-1")
+        self.assertEqual(args.handler, "handle-delivery --flag")
+        self.assertEqual(args.idle_timeout, 5)
+        self.assertEqual(args.interval, 0.25)
+        self.assertEqual(args.heartbeat_interval, 1)
+        self.assertEqual(args.heartbeat_status, "waiting")
+        self.assertEqual(args.claim_status, "busy")
+        self.assertEqual(args.max_deliveries, 3)
+
+    def test_message_loop_requires_handler(self):
+        stderr = StringIO()
+
+        with redirect_stderr(stderr), self.assertRaises(SystemExit):
+            build_parser().parse_args(["message", "loop", "session-2"])
+
+        self.assertIn("--handler", stderr.getvalue())
+
+    def test_message_loop_rejects_nonpositive_max_deliveries(self):
+        stderr = StringIO()
+
+        with redirect_stderr(stderr), self.assertRaises(SystemExit):
+            build_parser().parse_args(
+                ["message", "loop", "session-2", "--handler", "handle-delivery", "--max-deliveries", "0"]
+            )
+
+        self.assertIn("positive integer", stderr.getvalue())
+
+    def test_message_loop_reports_unknown_session(self):
+        Store(self.tmp).init()
+
+        code, _, stderr = self.run_cli(
+            "message", "loop", "missing-session", "--handler", "handle-delivery"
+        )
+
+        self.assertEqual(code, 1)
+        self.assertIn("Session not found: missing-session", stderr)
+
+    def test_message_loop_exits_after_idle_timeout_with_no_messages(self):
+        store, _, _ = self._mailbox_pair()
+        handler = self._handler_command("import sys; sys.exit(1)\n")
+
+        code, stdout, _ = self.run_cli("message", "loop", "loop-session", "--handler", handler)
+
+        self.assertEqual(code, 0)
+        self.assertIn("Handled 0 deliveries.", stdout)
+        self.assertEqual(store.get_agent_session("loop-session")["status"], "idle")
+
+    def test_message_loop_replies_and_acks_deliveries(self):
+        store, _, thread_id = self._mailbox_pair()
+        store.add_thread_message(thread_id, "codex", "first request", sender_session_id="lead-session")
+        store.add_thread_message(thread_id, "codex", "second request", sender_session_id="lead-session")
+        handler = self._handler_command(
+            "import json, sys\n"
+            "delivery = json.load(sys.stdin)\n"
+            "print(json.dumps({\n"
+            "    'action': 'reply',\n"
+            "    'body': 'handled: ' + delivery['body'],\n"
+            "    'ack': True,\n"
+            "    'role': 'worker',\n"
+            "    'metadata': {'handler': 'loop-test'},\n"
+            "}))\n"
+        )
+
+        code, stdout, _ = self.run_cli(
+            "message", "loop", "loop-session", "--handler", handler, "--max-deliveries", "2"
+        )
+
+        self.assertEqual(code, 0)
+        self.assertIn("action=reply", stdout)
+        self.assertIn("Handled 2 deliveries.", stdout)
+        replies = [m for m in store.list_thread_messages(thread_id) if m["sender_session_id"] == "loop-session"]
+        self.assertEqual(
+            sorted(reply["body"] for reply in replies),
+            ["handled: first request", "handled: second request"],
+        )
+        self.assertEqual(replies[0]["role"], "worker")
+        self.assertEqual(replies[0]["metadata"], {"handler": "loop-test"})
+        self.assertEqual(store.list_agent_inbox("loop-session", status="pending"), [])
+        self.assertEqual(len(store.list_agent_inbox("loop-session", status="acknowledged")), 2)
+        self.assertEqual(store.get_agent_session("loop-session")["status"], "active")
+
+    def test_message_loop_ack_action_acknowledges_delivery(self):
+        store, _, thread_id = self._mailbox_pair()
+        store.add_thread_message(thread_id, "codex", "ack me", sender_session_id="lead-session")
+        handler = self._handler_command(
+            "import json, sys\n"
+            "sys.stdin.read()\n"
+            "print(json.dumps({'action': 'ack'}))\n"
+        )
+
+        code, stdout, _ = self.run_cli(
+            "message", "loop", "loop-session", "--handler", handler, "--max-deliveries", "1"
+        )
+
+        self.assertEqual(code, 0)
+        self.assertIn("action=ack", stdout)
+        self.assertIn("Handled 1 deliveries.", stdout)
+        self.assertEqual(len(store.list_agent_inbox("loop-session", status="acknowledged")), 1)
+
+    def test_message_loop_release_action_requeues_delivery_and_stops(self):
+        store, _, thread_id = self._mailbox_pair()
+        store.add_thread_message(thread_id, "codex", "release me", sender_session_id="lead-session")
+        handler = self._handler_command(
+            "import json, sys\n"
+            "sys.stdin.read()\n"
+            "print(json.dumps({'action': 'release'}))\n"
+        )
+
+        code, stdout, _ = self.run_cli(
+            "message", "loop", "loop-session", "--handler", handler, "--max-deliveries", "1"
+        )
+
+        self.assertEqual(code, 0)
+        self.assertIn("Requeued delivery", stdout)
+        self.assertIn("action=release", stdout)
+        self.assertIn("Handled 0 deliveries.", stdout)
+        pending = store.list_agent_inbox("loop-session", status="pending")
+        self.assertEqual(len(pending), 1)
+        self.assertEqual(pending[0]["body"], "release me")
+
+    def test_message_loop_none_action_keeps_claim_and_stops(self):
+        store, _, thread_id = self._mailbox_pair()
+        store.add_thread_message(thread_id, "codex", "defer me", sender_session_id="lead-session")
+        handler = self._handler_command(
+            "import json, sys\n"
+            "sys.stdin.read()\n"
+            "print(json.dumps({'action': 'none'}))\n"
+        )
+
+        code, stdout, _ = self.run_cli("message", "loop", "loop-session", "--handler", handler)
+
+        self.assertEqual(code, 0)
+        self.assertIn("kept delivery", stdout)
+        self.assertIn("claim_token=", stdout)
+        self.assertIn("Handled 0 deliveries.", stdout)
+        claimed = store.list_agent_inbox("loop-session", status="claimed")
+        self.assertEqual(len(claimed), 1)
+        self.assertEqual(claimed[0]["body"], "defer me")
+
+    def test_message_loop_releases_claim_when_handler_fails(self):
+        store, _, thread_id = self._mailbox_pair()
+        store.add_thread_message(thread_id, "codex", "will fail", sender_session_id="lead-session")
+        handler = self._handler_command(
+            "import sys\n"
+            "sys.stdin.read()\n"
+            "sys.stderr.write('boom\\n')\n"
+            "sys.exit(3)\n"
+        )
+
+        code, _, stderr = self.run_cli("message", "loop", "loop-session", "--handler", handler)
+
+        self.assertEqual(code, 1)
+        self.assertIn("boom", stderr)
+        self.assertIn("exit code 3", stderr)
+        self.assertIn("released claim", stderr)
+        pending = store.list_agent_inbox("loop-session", status="pending")
+        self.assertEqual(len(pending), 1)
+        self.assertEqual(pending[0]["body"], "will fail")
+
+    def test_message_loop_releases_claim_on_invalid_handler_output(self):
+        store, _, thread_id = self._mailbox_pair()
+        store.add_thread_message(thread_id, "codex", "bad output", sender_session_id="lead-session")
+        handler = self._handler_command(
+            "import sys\n"
+            "sys.stdin.read()\n"
+            "print('not json')\n"
+        )
+
+        code, _, stderr = self.run_cli("message", "loop", "loop-session", "--handler", handler)
+
+        self.assertEqual(code, 1)
+        self.assertIn("Invalid handler output", stderr)
+        self.assertIn("released claim", stderr)
+        self.assertEqual(len(store.list_agent_inbox("loop-session", status="pending")), 1)
+
+    def test_message_loop_releases_claim_when_reply_missing_body(self):
+        store, _, thread_id = self._mailbox_pair()
+        store.add_thread_message(thread_id, "codex", "empty reply", sender_session_id="lead-session")
+        handler = self._handler_command(
+            "import json, sys\n"
+            "sys.stdin.read()\n"
+            "print(json.dumps({'action': 'reply'}))\n"
+        )
+
+        code, _, stderr = self.run_cli("message", "loop", "loop-session", "--handler", handler)
+
+        self.assertEqual(code, 1)
+        self.assertIn("body", stderr)
+        self.assertIn("released claim", stderr)
+        self.assertEqual(len(store.list_agent_inbox("loop-session", status="pending")), 1)
+
+    def test_message_loop_passes_claimed_delivery_json_to_handler(self):
+        store, _, thread_id = self._mailbox_pair()
+        store.add_thread_message(thread_id, "codex", "inspect me", sender_session_id="lead-session")
+        capture_path = self.tmp / "delivery.json"
+        handler = self._handler_command(
+            "import json, sys\n"
+            "delivery = json.load(sys.stdin)\n"
+            "open(%r, 'w').write(json.dumps(delivery))\n"
+            "print(json.dumps({'action': 'ack'}))\n" % str(capture_path)
+        )
+
+        code, _, _ = self.run_cli(
+            "message", "loop", "loop-session", "--handler", handler, "--max-deliveries", "1"
+        )
+
+        self.assertEqual(code, 0)
+        delivery = json.loads(capture_path.read_text(encoding="utf-8"))
+        self.assertEqual(delivery["body"], "inspect me")
+        self.assertEqual(delivery["delivery_status"], "claimed")
+        self.assertEqual(delivery["recipient_session_id"], "loop-session")
+        self.assertTrue(delivery["delivery_metadata"]["claimToken"])
+
     def test_task_thread_commands_create_and_list_follow_up_thread(self):
         store = Store(self.tmp)
         store.init()

```

## Arm B diff

```diff
diff --git a/README.md b/README.md
index e862fc3..2790c27 100644
--- a/README.md
+++ b/README.md
@@ -90,6 +90,8 @@ uv run a2a-bridge message inbox SESSION_ID
 uv run a2a-bridge message claim SESSION_ID DELIVERY_ID
 uv run a2a-bridge message claim-next SESSION_ID
 uv run a2a-bridge message poll SESSION_ID --wait-seconds 30 --ack --json
+uv run a2a-bridge message loop SESSION_ID --handler 'python handler.py'
+uv run a2a-bridge message loop SESSION_ID --idle-timeout 30 --max-deliveries 10 --handler 'python handler.py'
 uv run a2a-bridge message reply SESSION_ID DELIVERY_ID --claim-token CLAIM_TOKEN --body "Done." --ack
 uv run a2a-bridge message release SESSION_ID DELIVERY_ID --claim-token CLAIM_TOKEN
 uv run a2a-bridge message ack SESSION_ID DELIVERY_ID --claim-token CLAIM_TOKEN
@@ -184,6 +186,23 @@ Already-running agents can use `message poll` or the localhost
 `deliveries:poll` API as loop-friendly wrappers: they heartbeat the session,
 atomically claim the oldest pending delivery, optionally wait for work, and can
 acknowledge immediately for simple script consumers.
+For local script workers, `message loop` runs as a persistent worker by default:
+it keeps heartbeating while waiting for work, repeatedly claims one delivery at
+a time, and keeps heartbeating while the `--handler` subprocess runs with the
+claimed delivery JSON on stdin. Use `--idle-timeout`, `--wait-seconds`, or
+`--max-deliveries` when a bounded run is needed. The handler must print one JSON
+object to stdout:
+
+```json
+{"action":"reply","body":"Done.","ack":true,"role":"agent","metadata":{"kind":"review"}}
+```
+
+Supported actions are `reply`, `ack`, `release`, and `none`. `reply` posts back
+to the source thread and can acknowledge the claim with `ack: true`; `ack` and
+`release` use the current claim token automatically. If the handler exits
+nonzero or prints invalid JSON, the loop releases the claimed delivery and
+fails so another worker can retry it. `none` leaves the delivery claimed and
+exits nonzero for manual follow-up.
 
 Managed sessions use the one-shot task runner by default unless a task sets
 `agentSessionId` and the session was started with the explicit `jsonl` protocol
diff --git a/docs/mvp-spec.md b/docs/mvp-spec.md
index 9a6e86e..6f8d6f6 100644
--- a/docs/mvp-spec.md
+++ b/docs/mvp-spec.md
@@ -156,6 +156,14 @@ Agents can also reply directly to a claimed delivery; the bridge posts the
 reply into the delivery's thread from the recipient session and requires the
 same current claim token. A reply can acknowledge the source delivery in the
 same transaction.
+For already-running local script workers, `message loop` runs persistently by
+default: it heartbeats while waiting, claims one delivery at a time, passes the
+claimed delivery JSON to a handler subprocess on stdin, keeps heartbeating while
+the handler runs, and applies a handler stdout action of `reply`, `ack`,
+`release`, or `none`. `--idle-timeout`, `--wait-seconds`, and
+`--max-deliveries` can bound test or batch runs. Handler failures or invalid
+JSON release the current claim by default so the delivery can be retried. `none`
+leaves the delivery claimed and exits nonzero for explicit manual follow-up.
 Broadcast messages are delivered to currently active participants in the context
 except the sender.
 
diff --git a/docs/roadmap.md b/docs/roadmap.md
index b90748a..a90b965 100644
--- a/docs/roadmap.md
+++ b/docs/roadmap.md
@@ -130,6 +130,9 @@
   `deliveries:poll` API, wrappers that heartbeat while waiting, atomically claim
   the next delivery, and can optionally acknowledge it for simple script
   consumers.
+- CLI `message loop` can run a local handler command over claimed delivery JSON,
+  apply `reply`, `ack`, `release`, or explicit `none` actions, and release the
+  claim on handler failure so work can be retried.
 - Claimed inbox deliveries can now be released back to `pending` or
   acknowledged through the store, CLI, and localhost API with a claim-token
   guard, giving long-running agents retry-safe ownership semantics for work
diff --git a/src/a2a_bridge/cli.py b/src/a2a_bridge/cli.py
index 8a46652..396e95b 100644
--- a/src/a2a_bridge/cli.py
+++ b/src/a2a_bridge/cli.py
@@ -7,6 +7,7 @@ import json
 import math
 import shlex
 import sqlite3
+import subprocess
 import sys
 import time
 
@@ -56,19 +57,89 @@ def _nonnegative_float(value: str) -> float:
     return parsed
 
 
+def _positive_int(value: str) -> int:
+    parsed = int(value)
+    if parsed <= 0:
+        raise argparse.ArgumentTypeError("must be a positive integer")
+    return parsed
+
+
 def _split_optional_command(value: Optional[str]) -> Optional[list[str]]:
     return shlex.split(value) if value else None
 
 
-def _poll_sleep_seconds(interval: float, remaining: float, next_heartbeat_at: float, now: float) -> float:
+def _poll_sleep_seconds(
+    interval: float,
+    remaining: Optional[float],
+    next_heartbeat_at: float,
+    now: float,
+) -> float:
     heartbeat_wait = next_heartbeat_at - now
     if heartbeat_wait <= 0:
         return 0.0
-    candidates = [interval, remaining]
+    candidates = [interval]
+    if remaining is not None:
+        candidates.append(remaining)
     candidates.append(heartbeat_wait)
     return max(0.0, min(candidates))
 
 
+def _heartbeat_claimed_message_delivery(
+    store: Store,
+    session_id: str,
+    delivery: Dict[str, Any],
+    *,
+    status: str,
+) -> None:
+    store.heartbeat_agent_session(
+        session_id,
+        status=status,
+        context_id=str(delivery["context_id"]),
+        task_id=delivery.get("thread_task_id"),
+        clear_task=delivery.get("thread_task_id") is None,
+    )
+
+
+def _poll_claim_next_delivery(
+    store: Store,
+    session_id: str,
+    *,
+    context_id: Optional[str],
+    wait_seconds: Optional[float],
+    interval: float,
+    heartbeat_interval: float,
+    heartbeat_status: str,
+    claim_status: Optional[str],
+    exclude_delivery_ids: Optional[set[str]] = None,
+) -> Optional[Dict[str, Any]]:
+    deadline = None if wait_seconds is None else time.monotonic() + wait_seconds
+    next_heartbeat_at = 0.0
+    while True:
+        now = time.monotonic()
+        if now >= next_heartbeat_at:
+            store.heartbeat_agent_session(
+                session_id,
+                status=heartbeat_status,
+                context_id=context_id,
+                clear_task=True,
+            )
+            next_heartbeat_at = now + heartbeat_interval
+        delivery = store.claim_next_message_delivery(
+            session_id,
+            context_id=context_id,
+            exclude_delivery_ids=exclude_delivery_ids,
+        )
+        if delivery:
+            if claim_status:
+                _heartbeat_claimed_message_delivery(store, session_id, delivery, status=claim_status)
+            return delivery
+        now = time.monotonic()
+        remaining = None if deadline is None else deadline - now
+        if remaining is not None and remaining <= 0:
+            return None
+        time.sleep(_poll_sleep_seconds(interval, remaining, next_heartbeat_at, now))
+
+
 def cmd_init(args: argparse.Namespace) -> int:
     store = _store(args)
     ensure_layout(store.state_dir)
@@ -486,60 +557,46 @@ def cmd_message_claim_next(args: argparse.Namespace) -> int:
 def cmd_message_poll(args: argparse.Namespace) -> int:
     store = _store(args)
     store.init()
-    deadline = time.monotonic() + args.wait_seconds
-    next_heartbeat_at = 0.0
-    while True:
-        now = time.monotonic()
-        if now >= next_heartbeat_at:
-            try:
-                store.heartbeat_agent_session(
-                    args.session_id,
-                    status=args.heartbeat_status,
-                    context_id=args.context_id,
-                )
-            except KeyError:
-                print("Session not found: %s" % args.session_id, file=sys.stderr)
-                return 1
-            next_heartbeat_at = now + args.heartbeat_interval
-        delivery = store.claim_next_message_delivery(args.session_id, context_id=args.context_id)
-        if delivery:
-            if args.claim_status:
-                store.heartbeat_agent_session(
-                    args.session_id,
-                    status=args.claim_status,
-                    context_id=str(delivery["context_id"]),
-                    task_id=delivery.get("thread_task_id"),
-                    clear_task=delivery.get("thread_task_id") is None,
-                )
-            if args.ack:
-                store.acknowledge_message_delivery(
-                    args.session_id,
-                    str(delivery["delivery_id"]),
-                    claim_token=_claim_token(delivery),
-                )
-                delivery = store.get_message_delivery(str(delivery["delivery_id"])) or delivery
-            if args.json:
-                print(json.dumps({"delivery": delivery, "timedOut": False}, indent=2, sort_keys=True))
-            else:
-                print(
-                    "Claimed delivery %s message=%s%s %s"
-                    % (
-                        delivery["delivery_id"],
-                        delivery["message_id"],
-                        _claim_token_suffix(delivery),
-                        _first_line(delivery["body"]),
-                    )
+    try:
+        delivery = _poll_claim_next_delivery(
+            store,
+            args.session_id,
+            context_id=args.context_id,
+            wait_seconds=args.wait_seconds,
+            interval=args.interval,
+            heartbeat_interval=args.heartbeat_interval,
+            heartbeat_status=args.heartbeat_status,
+            claim_status=args.claim_status,
+        )
+    except KeyError:
+        print("Session not found: %s" % args.session_id, file=sys.stderr)
+        return 1
+    if delivery:
+        if args.ack:
+            store.acknowledge_message_delivery(
+                args.session_id,
+                str(delivery["delivery_id"]),
+                claim_token=_claim_token(delivery),
+            )
+            delivery = store.get_message_delivery(str(delivery["delivery_id"])) or delivery
+        if args.json:
+            print(json.dumps({"delivery": delivery, "timedOut": False}, indent=2, sort_keys=True))
+        else:
+            print(
+                "Claimed delivery %s message=%s%s %s"
+                % (
+                    delivery["delivery_id"],
+                    delivery["message_id"],
+                    _claim_token_suffix(delivery),
+                    _first_line(delivery["body"]),
                 )
-            return 0
-        now = time.monotonic()
-        remaining = deadline - now
-        if remaining <= 0:
-            if args.json:
-                print(json.dumps({"delivery": None, "timedOut": True}, indent=2, sort_keys=True))
-            else:
-                print("No pending messages.")
-            return 0
-        time.sleep(_poll_sleep_seconds(args.interval, remaining, next_heartbeat_at, now))
+            )
+        return 0
+    if args.json:
+        print(json.dumps({"delivery": None, "timedOut": True}, indent=2, sort_keys=True))
+    else:
+        print("No pending messages.")
+    return 0
 
 
 def cmd_message_ack(args: argparse.Namespace) -> int:
@@ -586,6 +643,259 @@ def cmd_message_release(args: argparse.Namespace) -> int:
     return 0
 
 
+def _message_loop_wait_seconds(args: argparse.Namespace) -> Optional[float]:
+    if args.idle_timeout is not None:
+        return args.idle_timeout
+    if args.wait_seconds is not None:
+        return args.wait_seconds
+    return None
+
+
+def _message_loop_handler_command(value: str) -> list[str]:
+    try:
+        return shlex.split(value)
+    except ValueError as exc:
+        raise ValueError("invalid handler command: %s" % exc) from exc
+
+
+def _message_loop_handler_input(delivery: Dict[str, Any]) -> str:
+    return json.dumps(delivery, sort_keys=True) + "\n"
+
+
+def _run_message_loop_handler(
+    store: Store,
+    session_id: str,
+    delivery: Dict[str, Any],
+    handler_command: list[str],
+    *,
+    handler_input: str,
+    heartbeat_interval: float,
+    heartbeat_status: Optional[str],
+) -> subprocess.CompletedProcess:
+    process = subprocess.Popen(
+        handler_command,
+        stdin=subprocess.PIPE,
+        stdout=subprocess.PIPE,
+        stderr=subprocess.PIPE,
+        text=True,
+    )
+    next_heartbeat_at = time.monotonic() + heartbeat_interval
+    communicate_input: Optional[str] = handler_input
+    while True:
+        timeout = max(0.0, next_heartbeat_at - time.monotonic())
+        try:
+            stdout, stderr = process.communicate(input=communicate_input, timeout=timeout)
+            return subprocess.CompletedProcess(handler_command, process.returncode, stdout, stderr)
+        except subprocess.TimeoutExpired:
+            communicate_input = None
+            if heartbeat_status:
+                _heartbeat_claimed_message_delivery(store, session_id, delivery, status=heartbeat_status)
+            next_heartbeat_at = time.monotonic() + heartbeat_interval
+
+
+def _parse_message_loop_action(stdout: str) -> Dict[str, Any]:
+    try:
+        payload = json.loads(stdout)
+    except json.JSONDecodeError as exc:
+        raise ValueError("handler stdout must be a JSON object: %s" % exc) from exc
+    if not isinstance(payload, dict):
+        raise ValueError("handler stdout must be a JSON object")
+    action = payload.get("action")
+    if not isinstance(action, str):
+        raise ValueError("handler action must be one of: reply, ack, release, none")
+    if action not in {"reply", "ack", "release", "none"}:
+        raise ValueError("handler action must be one of: reply, ack, release, none")
+    payload["action"] = action
+    if action == "reply":
+        if "body" not in payload or not isinstance(payload["body"], str):
+            raise ValueError("reply action requires string body")
+        role = payload.get("role", "agent")
+        if not isinstance(role, str):
+            raise ValueError("reply action role must be a string")
+        ack = payload.get("ack", payload.get("acknowledge", False))
+        if not isinstance(ack, bool):
+            raise ValueError("reply action ack must be a boolean")
+        metadata = payload.get("metadata")
+        if metadata is not None and not isinstance(metadata, dict):
+            raise ValueError("reply action metadata must be a JSON object")
+        payload["role"] = role
+        payload["ack"] = ack
+    return payload
+
+
+def _release_message_loop_delivery(store: Store, session_id: str, delivery: Dict[str, Any]) -> bool:
+    claim_token = _claim_token(delivery)
+    if not claim_token:
+        return False
+    return store.release_message_delivery(
+        session_id,
+        str(delivery["delivery_id"]),
+        claim_token=claim_token,
+    )
+
+
+def _fail_message_loop_delivery(
+    store: Store,
+    session_id: str,
+    delivery: Dict[str, Any],
+    message: str,
+    *,
+    handler_stderr: str = "",
+) -> int:
+    delivery_id = str(delivery["delivery_id"])
+    print(message, file=sys.stderr)
+    if handler_stderr.strip():
+        print("Handler stderr: %s" % handler_stderr.strip(), file=sys.stderr)
+    if _release_message_loop_delivery(store, session_id, delivery):
+        print("Released delivery %s after handler failure." % delivery_id, file=sys.stderr)
+    else:
+        print("Could not release delivery %s after handler failure." % delivery_id, file=sys.stderr)
+    return 1
+
+
+def _apply_message_loop_action(
+    store: Store,
+    session_id: str,
+    delivery: Dict[str, Any],
+    payload: Dict[str, Any],
+) -> Optional[Dict[str, Any]]:
+    action = str(payload["action"])
+    delivery_id = str(delivery["delivery_id"])
+    claim_token = _claim_token(delivery)
+    if not claim_token:
+        raise ValueError("claimed delivery has no claimToken")
+    if action == "ack":
+        if not store.acknowledge_message_delivery(session_id, delivery_id, claim_token=claim_token):
+            return None
+        return {"action": action}
+    if action == "release":
+        if not store.release_message_delivery(session_id, delivery_id, claim_token=claim_token):
+            return None
+        return {"action": action}
+    if action == "reply":
+        metadata = {"source": "cli-loop"}
+        metadata.update(payload.get("metadata") or {})
+        reply = store.reply_to_message_delivery(
+            session_id,
+            delivery_id,
+            body=str(payload["body"]),
+            claim_token=claim_token,
+            role=str(payload.get("role") or "agent"),
+            metadata=metadata,
+            acknowledge=bool(payload.get("ack")),
+        )
+        if not reply:
+            return None
+        return {"action": action, "reply": reply}
+    raise ValueError("unsupported handler action: %s" % action)
+
+
+def cmd_message_loop(args: argparse.Namespace) -> int:
+    store = _store(args)
+    store.init()
+    try:
+        handler_command = _message_loop_handler_command(args.handler)
+    except ValueError as exc:
+        print(str(exc), file=sys.stderr)
+        return 1
+    if not handler_command:
+        print("handler command is required", file=sys.stderr)
+        return 1
+    handled = 0
+    wait_seconds = _message_loop_wait_seconds(args)
+    released_delivery_ids: set[str] = set()
+    while args.max_deliveries is None or handled < args.max_deliveries:
+        poll_wait_seconds = wait_seconds
+        if poll_wait_seconds is None and args.max_deliveries is not None and released_delivery_ids:
+            poll_wait_seconds = 0.0
+        try:
+            delivery = _poll_claim_next_delivery(
+                store,
+                args.session_id,
+                context_id=args.context_id,
+                wait_seconds=poll_wait_seconds,
+                interval=args.interval,
+                heartbeat_interval=args.heartbeat_interval,
+                heartbeat_status=args.heartbeat_status,
+                claim_status=args.claim_status,
+                exclude_delivery_ids=released_delivery_ids,
+            )
+        except KeyError:
+            print("Session not found: %s" % args.session_id, file=sys.stderr)
+            return 1
+        if not delivery:
+            suffix = " handled=%d" % handled if handled else ""
+            print("No pending messages.%s" % suffix)
+            return 0
+        delivery_id = str(delivery["delivery_id"])
+        try:
+            result = _run_message_loop_handler(
+                store,
+                args.session_id,
+                delivery,
+                handler_command,
+                handler_input=_message_loop_handler_input(delivery),
+                heartbeat_interval=args.heartbeat_interval,
+                heartbeat_status=args.claim_status,
+            )
+        except OSError as exc:
+            return _fail_message_loop_delivery(
+                store,
+                args.session_id,
+                delivery,
+                "Handler could not start for delivery %s: %s" % (delivery_id, exc),
+            )
+        if result.returncode != 0:
+            return _fail_message_loop_delivery(
+                store,
+                args.session_id,
+                delivery,
+                "Handler failed for delivery %s with exit code %s." % (delivery_id, result.returncode),
+                handler_stderr=result.stderr,
+            )
+        try:
+            payload = _parse_message_loop_action(result.stdout)
+        except ValueError as exc:
+            return _fail_message_loop_delivery(
+                store,
+                args.session_id,
+                delivery,
+                "Handler returned invalid JSON action for delivery %s: %s" % (delivery_id, exc),
+                handler_stderr=result.stderr,
+            )
+        action = str(payload["action"])
+        if action == "none":
+            print(
+                "Handler returned action none for delivery %s; leaving delivery claimed." % delivery_id,
+                file=sys.stderr,
+            )
+            return 2
+        try:
+            applied = _apply_message_loop_action(store, args.session_id, delivery, payload)
+        except ValueError as exc:
+            return _fail_message_loop_delivery(
+                store,
+                args.session_id,
+                delivery,
+                "Handler action %s failed for delivery %s: %s" % (action, delivery_id, exc),
+            )
+        if not applied:
+            if action != "release":
+                _release_message_loop_delivery(store, args.session_id, delivery)
+            print("Handler action %s failed for delivery %s." % (action, delivery_id), file=sys.stderr)
+            return 1
+        handled += 1
+        if action == "release":
+            released_delivery_ids.add(delivery_id)
+        detail = ""
+        if action == "reply":
+            reply = applied["reply"]
+            detail = " reply_message=%s ack=%s" % (reply["message_id"], reply["acknowledged"])
+        print("Handled delivery %s action=%s%s" % (delivery_id, action, detail))
+    print("Handled %d deliver%s." % (handled, "y" if handled == 1 else "ies"))
+    return 0
+
+
 def cmd_submit(args: argparse.Namespace) -> int:
     store = _store(args)
     store.init()
@@ -1126,6 +1436,23 @@ def build_parser() -> argparse.ArgumentParser:
     message_poll.add_argument("--ack", action="store_true")
     message_poll.add_argument("--json", action="store_true")
     message_poll.set_defaults(func=cmd_message_poll)
+    message_loop = message_sub.add_parser("loop")
+    message_loop.add_argument("session_id")
+    message_loop.add_argument("--context-id")
+    loop_wait = message_loop.add_mutually_exclusive_group()
+    loop_wait.add_argument("--wait-seconds", type=_nonnegative_float)
+    loop_wait.add_argument("--idle-timeout", type=_nonnegative_float)
+    message_loop.add_argument("--interval", type=_positive_float, default=2.0)
+    message_loop.add_argument("--heartbeat-interval", type=_positive_float, default=30.0)
+    message_loop.add_argument("--heartbeat-status", default="idle")
+    message_loop.add_argument("--claim-status", default="active")
+    message_loop.add_argument("--max-deliveries", type=_positive_int)
+    message_loop.add_argument(
+        "--handler",
+        required=True,
+        help="Local command to run for each claimed delivery; stdout must be a JSON action object.",
+    )
+    message_loop.set_defaults(func=cmd_message_loop)
     message_ack = message_sub.add_parser("ack")
     message_ack.add_argument("session_id")
     message_ack.add_argument("delivery_id")
diff --git a/src/a2a_bridge/coordination_api.py b/src/a2a_bridge/coordination_api.py
index 7b7f6c3..c09a68b 100644
--- a/src/a2a_bridge/coordination_api.py
+++ b/src/a2a_bridge/coordination_api.py
@@ -353,6 +353,7 @@ def create_coordination_routes(store: Store) -> list[Route]:
                         session_id,
                         status=heartbeat_status,
                         context_id=context_id,
+                        clear_task=True,
                     )
                 except KeyError:
                     return _not_found("Session not found: %s" % session_id)
diff --git a/src/a2a_bridge/store.py b/src/a2a_bridge/store.py
index cb97071..67b4ef8 100644
--- a/src/a2a_bridge/store.py
+++ b/src/a2a_bridge/store.py
@@ -1580,6 +1580,7 @@ class Store:
         self,
         session_id: str,
         context_id: Optional[str] = None,
+        exclude_delivery_ids: Optional[Iterable[str]] = None,
     ) -> Optional[Dict[str, Any]]:
         now = _now()
         params: List[Any] = [session_id]
@@ -1587,6 +1588,11 @@ class Store:
         if context_id:
             context_clause = " AND context_id = ?"
             params.append(context_id)
+        excluded = list(dict.fromkeys(str(delivery_id) for delivery_id in (exclude_delivery_ids or [])))
+        exclude_clause = ""
+        if excluded:
+            exclude_clause = " AND id NOT IN (%s)" % ", ".join("?" for _ in excluded)
+            params.extend(excluded)
         with self.connection() as conn:
             try:
                 conn.execute("BEGIN IMMEDIATE")
@@ -1597,6 +1603,7 @@ class Store:
                       AND status = 'pending'
                     """
                     + context_clause
+                    + exclude_clause
                     + """
                     ORDER BY created_at ASC
                     LIMIT 1
diff --git a/tests/README.md b/tests/README.md
index 50e1f49..ec492db 100644
--- a/tests/README.md
+++ b/tests/README.md
@@ -260,8 +260,10 @@ unrun.
 - task PR command parsing
 - task PR/MR sync command parsing
 - task worktree lifecycle command parsing
-- persistent session, thread, inbox, claim, claim-next, poll, release, and
+- persistent session, thread, inbox, claim, claim-next, poll, loop, release, and
   acknowledge command parsing
-  and workflow behavior
+- message loop handler actions can reply and acknowledge, release claims on
+  handler failure or invalid JSON, and leave deliveries claimed for explicit
+  `none` actions
 - managed session start, stop, and reconcile command parsing
 - workflow template and hosting gate option parsing
diff --git a/tests/test_cli.py b/tests/test_cli.py
index ef28e6e..0f8a61e 100644
--- a/tests/test_cli.py
+++ b/tests/test_cli.py
@@ -1,7 +1,11 @@
 from pathlib import Path
 from contextlib import redirect_stderr
 from io import StringIO
+import os
+import subprocess
+import shlex
 import sys
+import time
 
 sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
 
@@ -10,7 +14,49 @@ from a2a_bridge.store import Store
 from support import BridgeTestCase
 
 
+def handler_command(script: str) -> str:
+    return "%s -c %s" % (shlex.quote(sys.executable), shlex.quote(script))
+
+
+def cli_subprocess_args(state_dir: Path, *args: str) -> list[str]:
+    return [
+        sys.executable,
+        "-c",
+        "from a2a_bridge.cli import main; import sys; raise SystemExit(main(sys.argv[1:]))",
+        "--state-dir",
+        str(state_dir),
+        *args,
+    ]
+
+
+def cli_subprocess_env() -> dict[str, str]:
+    env = os.environ.copy()
+    source_path = str(Path(__file__).resolve().parents[1] / "src")
+    pythonpath = env.get("PYTHONPATH")
+    env["PYTHONPATH"] = source_path if not pythonpath else source_path + os.pathsep + pythonpath
+    return env
+
+
 class CliTests(BridgeTestCase):
+    def seed_loop_delivery(self, body="Please handle this delivery."):
+        store = Store(self.tmp)
+        store.init()
+        context_id = store.create_context("message loop cli")
+        lead_session = store.upsert_agent_session("codex", context_id=context_id, session_id="lead-session")
+        review_session = store.upsert_agent_session("claude", context_id=context_id, session_id="review-session")
+        store.add_context_participant(context_id, lead_session, role="lead")
+        store.add_context_participant(context_id, review_session, role="reviewer")
+        thread_id = store.create_message_thread(context_id, "Loop")
+        store.add_thread_message(
+            thread_id,
+            sender_name="codex",
+            sender_session_id=lead_session,
+            role="agent",
+            body=body,
+        )
+        delivery = store.list_agent_inbox(review_session)[0]
+        return store, context_id, thread_id, review_session, str(delivery["delivery_id"])
+
     def test_serve_accepts_output_publish_timeout(self):
         args = build_parser().parse_args(["serve", "--output-publish-timeout", "0.25"])
 
@@ -317,6 +363,29 @@ class CliTests(BridgeTestCase):
                 "--ack",
             ]
         )
+        loop = build_parser().parse_args(
+            [
+                "message",
+                "loop",
+                "session-2",
+                "--context-id",
+                "ctx-1",
+                "--idle-timeout",
+                "5",
+                "--interval",
+                "0.25",
+                "--heartbeat-interval",
+                "1",
+                "--heartbeat-status",
+                "waiting",
+                "--claim-status",
+                "handling",
+                "--max-deliveries",
+                "2",
+                "--handler",
+                "python handler.py",
+            ]
+        )
 
         self.assertEqual(start.agent, "codex")
         self.assertEqual(start.role, "lead")
@@ -345,6 +414,14 @@ class CliTests(BridgeTestCase):
         self.assertEqual(poll.interval, 0.25)
         self.assertEqual(poll.heartbeat_interval, 1)
         self.assertTrue(poll.ack)
+        self.assertEqual(loop.context_id, "ctx-1")
+        self.assertEqual(loop.idle_timeout, 5)
+        self.assertEqual(loop.interval, 0.25)
+        self.assertEqual(loop.heartbeat_interval, 1)
+        self.assertEqual(loop.heartbeat_status, "waiting")
+        self.assertEqual(loop.claim_status, "handling")
+        self.assertEqual(loop.max_deliveries, 2)
+        self.assertEqual(loop.handler, "python handler.py")
 
     def test_workflow_scaffold_template_command_parses_hosting_gate_options(self):
         args = build_parser().parse_args(
@@ -591,6 +668,240 @@ class CliTests(BridgeTestCase):
         self.assertEqual(code, 0)
         self.assertIn('"timedOut": true', stdout)
 
+    def test_message_loop_handler_can_reply_and_ack_delivery(self):
+        store, _, thread_id, session_id, delivery_id = self.seed_loop_delivery("Please summarize.")
+        command = handler_command(
+            "import json, sys; "
+            "delivery = json.load(sys.stdin); "
+            "print(json.dumps({"
+            "'action': 'reply', "
+            "'body': 'handled: ' + delivery['body'], "
+            "'ack': True, "
+            "'role': 'agent', "
+            "'metadata': {'handledBy': 'loop'}"
+            "}))"
+        )
+
+        code, stdout, stderr = self.run_cli(
+            "message",
+            "loop",
+            session_id,
+            "--max-deliveries",
+            "1",
+            "--handler",
+            command,
+        )
+
+        self.assertEqual(code, 0, stderr)
+        self.assertIn("Handled delivery", stdout)
+        self.assertIn("action=reply", stdout)
+        self.assertEqual(store.get_message_delivery(delivery_id)["delivery_status"], "acknowledged")
+        messages = store.list_thread_messages(thread_id)
+        self.assertEqual(messages[-1]["body"], "handled: Please summarize.")
+        self.assertEqual(messages[-1]["metadata"]["handledBy"], "loop")
+
+    def test_message_loop_release_does_not_reclaim_same_delivery_in_same_run(self):
+        store, _, _, session_id, delivery_id = self.seed_loop_delivery("Cannot handle this.")
+        command = handler_command(
+            "import json, sys; "
+            "sys.stdin.read(); "
+            "print(json.dumps({'action': 'release'}))"
+        )
+
+        code, stdout, stderr = self.run_cli(
+            "message",
+            "loop",
+            session_id,
+            "--max-deliveries",
+            "2",
+            "--handler",
+            command,
+        )
+
+        self.assertEqual(code, 0, stderr)
+        self.assertEqual(stdout.count("Handled delivery %s action=release" % delivery_id), 1)
+        self.assertIn("No pending messages. handled=1", stdout)
+        self.assertEqual(store.get_message_delivery(delivery_id)["delivery_status"], "pending")
+
+    def test_message_loop_idle_heartbeat_clears_task_after_task_delivery(self):
+        store = Store(self.tmp)
+        store.init()
+        context_id = store.create_context("message loop task context")
+        task_id = store.create_task(context_id, "task-linked delivery")
+        lead_session = store.upsert_agent_session("codex", context_id=context_id, session_id="lead-session")
+        review_session = store.upsert_agent_session("claude", context_id=context_id, session_id="review-session")
+        store.add_context_participant(context_id, lead_session, role="lead")
+        store.add_context_participant(context_id, review_session, role="reviewer")
+        thread_id = store.create_message_thread(context_id, "Task loop", task_id=task_id)
+        store.add_thread_message(
+            thread_id,
+            sender_name="codex",
+            sender_session_id=lead_session,
+            role="agent",
+            body="Task-scoped message.",
+        )
+        delivery_id = str(store.list_agent_inbox(review_session)[0]["delivery_id"])
+        command = handler_command(
+            "import json, sys; "
+            "sys.stdin.read(); "
+            "print(json.dumps({'action': 'ack'}))"
+        )
+
+        code, stdout, stderr = self.run_cli(
+            "message",
+            "loop",
+            review_session,
+            "--max-deliveries",
+            "2",
+            "--idle-timeout",
+            "0",
+            "--handler",
+            command,
+        )
+
+        self.assertEqual(code, 0, stderr)
+        self.assertIn("No pending messages. handled=1", stdout)
+        self.assertEqual(store.get_message_delivery(delivery_id)["delivery_status"], "acknowledged")
+        session = store.get_agent_session(review_session)
+        self.assertEqual(session["status"], "idle")
+        self.assertIsNone(session["task_id"])
+
+    def test_message_loop_defaults_to_persistent_worker(self):
+        store = Store(self.tmp)
+        store.init()
+        context_id = store.create_context("message loop cli")
+        lead_session = store.upsert_agent_session("codex", context_id=context_id, session_id="lead-session")
+        review_session = store.upsert_agent_session("claude", context_id=context_id, session_id="review-session")
+        store.add_context_participant(context_id, lead_session, role="lead")
+        store.add_context_participant(context_id, review_session, role="reviewer")
+        thread_id = store.create_message_thread(context_id, "Loop")
+        command = handler_command("import json, sys; sys.stdin.read(); print(json.dumps({'action': 'ack'}))")
+        proc = subprocess.Popen(
+            cli_subprocess_args(
+                self.tmp,
+                "message",
+                "loop",
+                review_session,
+                "--max-deliveries",
+                "1",
+                "--interval",
+                "0.05",
+                "--heartbeat-interval",
+                "0.05",
+                "--handler",
+                command,
+            ),
+            env=cli_subprocess_env(),
+            stdout=subprocess.PIPE,
+            stderr=subprocess.PIPE,
+            text=True,
+        )
+        try:
+            waiting = False
+            for _ in range(50):
+                if proc.poll() is not None:
+                    break
+                session = store.get_agent_session(review_session)
+                if session and session["status"] == "idle":
+                    waiting = True
+                    break
+                time.sleep(0.02)
+            self.assertTrue(waiting)
+            self.assertIsNone(proc.poll())
+
+            message_id = store.add_thread_message(
+                thread_id,
+                sender_name="codex",
+                sender_session_id=lead_session,
+                role="agent",
+                body="arrived after loop start",
+            )
+            stdout, stderr = proc.communicate(timeout=5)
+        finally:
+            if proc.poll() is None:
+                proc.kill()
+                proc.communicate()
+
+        self.assertEqual(proc.returncode, 0, stderr)
+        self.assertIn("Handled delivery", stdout)
+        deliveries = store.list_agent_inbox(review_session, status="acknowledged")
+        self.assertTrue(any(delivery["message_id"] == message_id for delivery in deliveries))
+
+    def test_message_loop_heartbeats_while_handler_runs(self):
+        store, _, _, session_id, delivery_id = self.seed_loop_delivery()
+        command = handler_command(
+            "import json, sys, time; "
+            "sys.stdin.read(); "
+            "time.sleep(0.3); "
+            "print(json.dumps({'action': 'ack'}))"
+        )
+
+        code, _, stderr = self.run_cli(
+            "message",
+            "loop",
+            session_id,
+            "--max-deliveries",
+            "1",
+            "--heartbeat-interval",
+            "0.05",
+            "--handler",
+            command,
+        )
+
+        self.assertEqual(code, 0, stderr)
+        self.assertEqual(store.get_message_delivery(delivery_id)["delivery_status"], "acknowledged")
+        active_heartbeats = [
+            event
+            for event in store.list_events(limit=100)
+            if event["type"] == "agent.session.heartbeat"
+            and event["message"] == session_id
+            and event["metadata"]["status"] == "active"
+        ]
+        self.assertGreaterEqual(len(active_heartbeats), 2)
+
+    def test_message_loop_releases_delivery_when_handler_exits_nonzero(self):
+        store, _, _, session_id, delivery_id = self.seed_loop_delivery()
+        command = handler_command(
+            "import sys; "
+            "sys.stdin.read(); "
+            "print('handler failed intentionally', file=sys.stderr); "
+            "sys.exit(7)"
+        )
+
+        code, _, stderr = self.run_cli("message", "loop", session_id, "--handler", command)
+
+        self.assertEqual(code, 1)
+        self.assertIn("exit code 7", stderr)
+        self.assertIn("Released delivery", stderr)
+        self.assertEqual(store.get_message_delivery(delivery_id)["delivery_status"], "pending")
+
+    def test_message_loop_releases_delivery_when_handler_stdout_is_invalid_json(self):
+        store, _, _, session_id, delivery_id = self.seed_loop_delivery()
+        command = handler_command("import sys; sys.stdin.read(); print('not json')")
+
+        code, _, stderr = self.run_cli("message", "loop", session_id, "--handler", command)
+
+        self.assertEqual(code, 1)
+        self.assertIn("invalid JSON action", stderr)
+        self.assertIn("Released delivery", stderr)
+        self.assertEqual(store.get_message_delivery(delivery_id)["delivery_status"], "pending")
+
+    def test_message_loop_none_action_leaves_delivery_claimed_and_fails_clearly(self):
+        store, _, _, session_id, delivery_id = self.seed_loop_delivery()
+        command = handler_command(
+            "import json, sys; "
+            "sys.stdin.read(); "
+            "print(json.dumps({'action': 'none'}))"
+        )
+
+        code, _, stderr = self.run_cli("message", "loop", session_id, "--handler", command)
+
+        self.assertEqual(code, 2)
+        self.assertIn("leaving delivery claimed", stderr)
+        delivery = store.get_message_delivery(delivery_id)
+        self.assertEqual(delivery["delivery_status"], "claimed")
+        self.assertIn("claimToken", delivery["delivery_metadata"])
+
     def test_task_thread_commands_create_and_list_follow_up_thread(self):
         store = Store(self.tmp)
         store.init()

```
