# Diagnose: where did my Claude Code sessions go after switching workspace?

Short answer: they are in another workspace's session list on the same computer, and the transcripts
are still in `~/.claude/projects/`. This page shows how to confirm that in two minutes.

Tested on macOS, desktop app build 2.31226.x, 2026-10-10. Windows and Linux paths are untested.
Unofficial; not affiliated with or endorsed by Anthropic. Everything on this page only reads.

## 1. One login, several workspaces

When the same login is a member of a personal workspace and a Team (or Enterprise) workspace, the
desktop app treats them as two separate places. The account menu switches between them. Each has its
own Code sidebar, folders, scheduled tasks, connectors and published artifacts.

Typical ways to end up here:

- You joined a Team plan with the same email and chose **Keep both accounts**.
- Your Pro or Max plan was bought through the Apple App Store. Then Keep both accounts is the only
  option the migration offers, unless you cancel the iOS subscription first
  ([support article 9267400](https://support.claude.com/en/articles/9267400)).
- Your Pro or Max plan lapsed, or you logged in with a second account.

## 2. Look at the session store

```bash
ls ~/Library/Application\ Support/Claude/claude-code-sessions/
ls ~/Library/Application\ Support/Claude/claude-code-sessions/*/
```

The layout is `<accountUuid>/<orgUuid>/`. Each workspace you ever opened in the Code tab has a folder.
Inside:

| File | Meaning |
|---|---|
| `local_<id>.json` | one sidebar session |
| `deleted_<id>` | a marker for a session deleted from the sidebar |
| `scheduled-tasks.json` | that workspace's scheduled tasks (Routines) |

Count sessions per workspace:

```bash
cd ~/Library/Application\ Support/Claude/claude-code-sessions
for d in */*/; do echo "$d  $(ls "$d" | grep -c '^local_') sessions  $(ls -t "$d" | head -1)"; done
```

Or with the toolkit, which also checks that each transcript exists:

```bash
python3 tools/ccrecover.py scan
python3 tools/ccrecover.py sessions --from <old> --limit 20
```

Which folder is which: the one the app writes to right now is the current workspace (its newest file
changes when you start a session). The one with your history is the old one.

## 3. Check the transcripts

A sidebar entry points to its transcript through `cliSessionId`:

```bash
python3 - <<'EOF'
import json, glob, os
store = os.path.expanduser("~/Library/Application Support/Claude/claude-code-sessions")
for f in sorted(glob.glob(store + "/*/*/local_*.json")):
    s = json.load(open(f))
    sid = s.get("cliSessionId") or (s.get("priorCliSessionIds") or [None])[-1]
    hit = glob.glob(os.path.expanduser(f"~/.claude/projects/*/{sid}.jsonl")) if sid else []
    print(f.split("/")[-3][:8], s.get("lastActivityAt"), "OK " if hit else "-- ", sid, s.get("title"))
EOF
```

`OK` means the conversation is on disk and can be imported. A session with an empty `cliSessionId`
was cleared with `/clear`; its conversation is under the last id in `priorCliSessionIds`.

The terminal also sees everything, regardless of workspace:

```bash
claude --resume        # lists past sessions whatever workspace created them; starts with this folder's, can widen to all projects
```

## 4. Read the app log

The app's import writes counters to its log:

```bash
ls -tr ~/Library/Logs/Claude/main*.log | while read -r f; do grep -h "CCD-SessionRecovery" "$f"; done | tail -5
```

You will see `scannedTranscripts`, `skippedFiltered`, `skippedNotLost`, `skippedUntrusted` and the
number it could recover. The log rotates into `main1.log`, `main2.log` and so on; the command reads them
oldest first, so the last lines are the newest scan. In the case study a scan on 2026-10-01 counted 893
transcripts and skipped 590 + 302 + 0.
What each counter means: [02-sessions.md](02-sessions.md#why-the-import-finds-nothing).

## 5. What to do next

- Sessions: [02-sessions.md](02-sessions.md)
- Folders: [03-folders.md](03-folders.md)
- Routines: [04-routines.md](04-routines.md)
- Artifacts: [05-artifacts.md](05-artifacts.md)
- `claude -p` 403, other machines, connectors: [06-auth-machines-connectors.md](06-auth-machines-connectors.md)

Do not delete anything in the old workspace. Since Claude Code 2.1.284, deleting a session from the
sidebar also deletes its transcript ([#98642](https://github.com/anthropics/claude-code/issues/98642)).
