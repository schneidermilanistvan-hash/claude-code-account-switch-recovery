#!/usr/bin/env python3
"""Self-contained tests for ccrecover.py. Builds fake stores/transcripts in a temp dir; touches nothing real."""
import contextlib
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ccrecover as cc  # noqa: E402

SID = "aaaaaaaa-0000-4000-8000-000000000001"
TARGET = "/work/page.html"


def use(i, name, inp, ts):
    return {"type": "assistant", "timestamp": ts, "message": {"content": [{"type": "tool_use", "id": "t%d" % i, "name": name, "input": inp}]}}


def res(i, ts, tur=None, err=False):
    b = {"type": "tool_result", "tool_use_id": "t%d" % i, "content": "x"}
    if err:
        b["is_error"] = True
    return {"type": "user", "timestamp": ts, "message": {"content": [b]}, "toolUseResult": tur if tur is not None else {}}


def run(argv):
    out, err = io.StringIO(), io.StringIO()
    code = 0
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            cc.main(argv)
        except SystemExit as e:
            code = e.code or 0
    return code, out.getvalue(), err.getvalue()


class Rebuild(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.projects = self.tmp / "projects"
        (self.projects / "slug").mkdir(parents=True)
        self.t = self.projects / "slug" / (SID + ".jsonl")
        (self.tmp / "file-history" / SID).mkdir(parents=True)

    def write(self, lines):
        self.t.write_text("".join(json.dumps(x) + "\n" for x in lines), encoding="utf-8")

    def rebuild(self, *extra):
        out = self.tmp / "out.html"
        if out.exists():
            out.unlink()
        code, _, err = run(["--projects", str(self.projects), "rebuild-file", "--transcript", str(self.t),
                            "--path", TARGET, "--out", str(out)] + list(extra))
        return code, (out.read_text(encoding="utf-8") if out.exists() else None), err

    def test_write_edit_multiedit_and_failed_call_skipped(self):
        self.write([
            use(1, "Write", {"file_path": TARGET, "content": "alpha beta gamma\n"}, "2026-01-01T00:00:01.000Z"), res(1, "x"),
            use(2, "Edit", {"file_path": TARGET, "old_string": "beta", "new_string": "BETA"}, "2026-01-01T00:00:02.000Z"), res(2, "x"),
            use(3, "Edit", {"file_path": TARGET, "old_string": "gamma", "new_string": "NOPE"}, "2026-01-01T00:00:03.000Z"), res(3, "x", err=True),
            use(4, "MultiEdit", {"file_path": TARGET, "edits": [{"old_string": "alpha", "new_string": "A"}, {"old_string": "BETA", "new_string": "B"}]}, "2026-01-01T00:00:04.000Z"), res(4, "x"),
            use(5, "Artifact", {"file_path": TARGET}, "2026-01-01T00:00:05.000Z"), res(5, "x", {"url": "https://example.invalid/artifact/1", "title": "T", "seq": 1}),
            use(6, "Edit", {"file_path": TARGET, "old_string": "gamma", "new_string": "AFTER"}, "2026-01-01T00:00:06.000Z"), res(6, "x"),
        ])
        code, text, err = self.rebuild()
        self.assertEqual(code, 0, err)
        self.assertEqual(text, "A B gamma\n")  # failed edit skipped, edit after the publish not applied
        code, text, _ = self.rebuild("--until", "2026-01-01T00:00:02.500Z")
        self.assertEqual(text, "alpha BETA gamma\n")

    def test_fallback_to_file_history_backup(self):
        (self.tmp / "file-history" / SID / "abc@v1").write_text("one two three\n", encoding="utf-8")
        snap = {"type": "file-history-snapshot", "snapshot": {"trackedFileBackups": {TARGET: {
            "backupFileName": "abc@v1", "version": 1, "backupTime": "2026-01-01T00:00:00.500Z"}}}}
        self.write([
            snap,
            use(1, "Edit", {"file_path": TARGET, "old_string": "two", "new_string": "2"}, "2026-01-01T00:00:01.000Z"), res(1, "x"),
            use(2, "Artifact", {"file_path": TARGET}, "2026-01-01T00:00:02.000Z"), res(2, "x", {"url": "https://example.invalid/artifact/1", "seq": 1}),
        ])
        code, text, err = self.rebuild()
        self.assertEqual(code, 0, err)
        self.assertEqual(text, "one 2 three\n")
        self.assertIn("file-history backup", err)

    def test_relative_backup_key_and_start_from_backup(self):
        # snapshot key relative to realParentDir; no Write in the transcript, only an Edit
        (self.tmp / "file-history" / SID / "rel@v2").write_text("red green blue\n", encoding="utf-8")
        snap = {"type": "file-history-snapshot", "snapshot": {"trackedFileBackups": {"page.html": {
            "backupFileName": "rel@v2", "version": 2, "backupTime": "2026-01-01T00:00:00.500Z", "realParentDir": "/work"}}}}
        self.write([
            snap,
            use(1, "Edit", {"file_path": TARGET, "old_string": "green", "new_string": "GREEN"}, "2026-01-01T00:00:01.000Z"), res(1, "x"),
            use(2, "Artifact", {"file_path": TARGET}, "2026-01-01T00:00:02.000Z"), res(2, "x", {"url": "https://example.invalid/artifact/1", "seq": 1}),
        ])
        code, text, err = self.rebuild()
        self.assertEqual(code, 0, err)
        self.assertEqual(text, "red GREEN blue\n")
        self.assertIn("started from file-history backup", err)
        # no edits at all: the backup alone is the result
        self.write([snap, use(2, "Artifact", {"file_path": TARGET}, "2026-01-01T00:00:02.000Z"),
                    res(2, "x", {"url": "https://example.invalid/artifact/1", "seq": 1})])
        code, text, err = self.rebuild()
        self.assertEqual(code, 0, err)
        self.assertEqual(text, "red green blue\n")

    def test_original_file_fallback_and_unrecoverable(self):
        self.write([
            use(1, "Edit", {"file_path": TARGET, "old_string": "x", "new_string": "y"}, "2026-01-01T00:00:01.000Z"),
            res(1, "x", {"originalFile": "x-file\n", "oldString": "x", "newString": "y"}),
        ])
        code, text, _ = self.rebuild()
        self.assertEqual(text, "y-file\n")
        self.write([use(1, "Edit", {"file_path": TARGET, "old_string": "zzz", "new_string": "y"}, "2026-01-01T00:00:01.000Z"), res(1, "x")])
        code, text, err = self.rebuild()
        self.assertEqual(code, 1)
        self.assertIsNone(text)

    def test_bash_commands_are_reported(self):
        self.write([
            use(1, "Write", {"file_path": TARGET, "content": "v1"}, "2026-01-01T00:00:01.000Z"), res(1, "x"),
            use(2, "Bash", {"command": "sed -i s/v1/v2/ /work/page.html"}, "2026-01-01T00:00:02.000Z"), res(2, "x"),
        ])
        _, text, err = self.rebuild()
        self.assertEqual(text, "v1")
        self.assertIn("re-run them manually", err)
        self.assertIn("sed -i", err)

    def test_artifacts_inventory(self):
        self.write([
            use(1, "Artifact", {"file_path": TARGET, "icon": "x"}, "2026-01-01T00:00:01.000Z"),
            res(1, "x", {"url": "https://example.invalid/artifact/1", "title": "T", "seq": 1, "capabilities": {"db": {}}}),
            use(2, "Artifact", {"action": "quickstart"}, "2026-01-01T00:00:02.000Z"), res(2, "x", {"quickstart": {}}),
            use(3, "Artifact", {"file_path": "/work/other.html"}, "2026-01-01T00:00:03.000Z"), res(3, "x", err=True),
        ])
        code, out, _ = run(["--projects", str(self.projects), "artifacts", "--json"])
        rows = json.loads(out)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["capabilities"], ["db"])
        self.assertFalse(rows[0]["sourceOnDisk"])


class Store(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.store = self.tmp / "Claude" / "claude-code-sessions"
        self.projects = self.tmp / "projects"
        (self.projects / "slug").mkdir(parents=True)
        self.old = self.store / "acc1" / "wsold"
        self.new = self.store / "acc1" / "wsnew"
        self.old.mkdir(parents=True)
        self.new.mkdir(parents=True)
        self.ids = ["bbbbbbbb-0000-4000-8000-00000000000%d" % i for i in range(1, 5)]
        for n, cid in enumerate(self.ids):
            rec = {"sessionId": "local_x%d" % n, "cliSessionId": cid, "title": "t%d" % n, "lastActivityAt": 1700000000000 + n * 1000}
            if n == 3:  # a /clear-ed session: only prior ids
                rec["cliSessionId"] = None
                rec["priorCliSessionIds"] = ["bbbbbbbb-0000-4000-8000-0000000000ff", cid]
            if n == 2:
                rec["scheduledTaskId"] = "job"
            (self.old / ("local_x%d.json" % n)).write_text(json.dumps(rec))
            if n != 1:  # session 1 has no transcript
                (self.projects / "slug" / (cid + ".jsonl")).write_text("{}\n")
        # session 0 is already imported into the new workspace
        (self.new / ("local_%s.json" % self.ids[0])).write_text(json.dumps({"sessionId": "local_" + self.ids[0], "cliSessionId": self.ids[0]}))
        (self.old / "scheduled-tasks.json").write_text(json.dumps({"scheduledTasks": [{"id": "job", "enabled": True, "cronExpression": "0 9 * * 1", "filePath": "/nonexistent/SKILL.md"}]}))
        (self.tmp / "Claude" / "claude_desktop_config.json").write_text(json.dumps({"preferences": {"epitaxyPrefs": {"dframe-group-scopes": {
            "acc1/wsold": {"groups": [{"id": "g1", "name": "Folder A"}], "assignments": {"code:local_x2": "g1", "code:local_x0": "g1"},
                           "order": {"g1": ["code:local_x2", "code:local_x0"]}}}}}}))

    def args(self, *a):
        return ["--store", str(self.store), "--projects", str(self.projects)] + list(a)

    def test_scan_flags(self):
        _, out, _ = run(self.args("scan", "--json"))
        row = [r for r in json.loads(out) if r["workspace"].endswith("wsold")][0]
        self.assertEqual((row["sessions"], row["with_transcript"], row["empty_cli_but_prior_ids"], row["scheduled_tasks"]), (4, 3, 1, 1))

    def test_plan_skips_present_and_missing_and_orders_oldest_first(self):
        out_file = self.tmp / "ids.txt"
        _, out, _ = run(self.args("plan", "--from", "acc1/wsold", "--to", "acc1/wsnew", "--all", "--out", str(out_file)))
        self.assertEqual(out_file.read_text().split(), [self.ids[3]])  # 0 present, 1 no transcript, 2 is a task run
        run(self.args("plan", "--from", "acc1/wsold", "--to", "acc1/wsnew", "--all", "--include-task-runs", "--out", str(out_file)))
        self.assertEqual(out_file.read_text().split(), [self.ids[2], self.ids[3]])
        run(self.args("plan", "--from", "acc1/wsold", "--to", "acc1/wsnew", "--folders", "--include-task-runs", "--out", str(out_file)))
        self.assertEqual(out_file.read_text().split(), [self.ids[2]])  # only the folder one not yet present

    def test_import_dry_run_opens_nothing_and_apply_refuses_missing_target(self):
        f = self.tmp / "ids.txt"
        f.write_text("\n".join(self.ids[:2]) + "\n")
        called = []
        real = cc.run_open
        cc.run_open = lambda cid: called.append(cid)
        try:
            code, out, _ = run(self.args("import", str(f), "--to", "acc1/wsnew"))
            self.assertEqual(code, 0)
            self.assertIn("DRY-RUN", out)
            self.assertEqual(called, [])
            code, _, err = run(self.args("import", str(f), "--to", "acc1/nothere", "--apply"))
            self.assertNotEqual(code, 0)
            self.assertEqual(called, [])
        finally:
            cc.run_open = real

    def test_folders_and_tasks(self):
        _, out, _ = run(self.args("folders", "--from", "acc1/wsold", "--json"))
        items = json.loads(out)[0]["sessions"]
        self.assertEqual([i["new"] for i in items], ["code:local_" + self.ids[2], "code:local_" + self.ids[0]])
        _, out, _ = run(self.args("tasks", "--from", "acc1/wsold", "--json"))
        self.assertFalse(json.loads(out)[0]["promptExists"])


if __name__ == "__main__":
    unittest.main()
