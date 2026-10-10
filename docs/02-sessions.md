# Import Claude Code sessions into another workspace with `claude://resume`

How to get Code-tab sessions back into the desktop app's sidebar after a workspace, plan or account
switch, why the app's own import finds nothing, and what the resume link does.

Tested on macOS, desktop app build 2.31226.x (bundled Claude Code 2.1.295), 2026-10-10. The internals
below come from the app's own code and log; they are not documented by Anthropic and can change.

Unofficial; not affiliated with or endorsed by Anthropic. **Back up first** ([README Step 0](../README.md#step-0-back-up-and-stop-the-clock)) and run the import as a dry run
before `--apply`.

## The short version

With the desktop app open and showing the workspace you want the session in:

```bash
open "claude://resume?session=<cliSessionId>"
```

or the documented command, Claude Code 2.1.285 or newer (macOS and x64 Windows, a subscription
sign-in in the CLI, see [the desktop docs](https://code.claude.com/docs/en/desktop)):

```bash
claude --desktop --resume <cliSessionId>
```

The second command builds and opens exactly the first link. The new entry appears as
`local_<cliSessionId>.json` in the current workspace's folder, with the transcript's title.
The old workspace keeps its own entry.

`claude --desktop --resume` adds its own checks: it refuses a session that is open in another terminal
or still running in the background, and it takes only an id, not a name. I did not test it across
workspaces, or while the CLI's own workspace returns the `oauth_org_not_allowed` 403. The raw link
was used for every import in the case study.

## Which id to use

The id is the transcript's file name, `~/.claude/projects/<cwd-slug>/<id>.jsonl`. In a sidebar entry
it is `cliSessionId`. If that is empty (the session was cleared with `/clear`), use the last id in
`priorCliSessionIds`. The link accepts only a UUID.

```bash
python3 tools/ccrecover.py sessions --from <old>      # date, title, id, folder
```

## Bulk import with the toolkit

```bash
python3 tools/ccrecover.py plan --from <old> --to <new> --folders --recent 10 --out ids.txt
python3 tools/ccrecover.py import ids.txt --to <new>                 # dry run
python3 tools/ccrecover.py import ids.txt --to <new> --apply --batch 10 --pause 20
```

- `plan` options: `--folders` (sessions in a sidebar folder), `--recent N` (plus the N newest loose
  ones), `--all`, `--include-archived`, `--include-task-runs` (sessions created by scheduled-task
  runs are skipped by default).
- The list is oldest first, so the newest sessions end up on top of the sidebar.
- `import --apply` opens one link per id, waits up to 30 seconds for `local_<id>.json` to appear in
  the target folder, and reports OK or FAIL. It refuses if the target folder does not exist.
- Do not use the app while it runs. Each import opens the session and focuses the window.

Manual loop, if you prefer:

```bash
while read -r id; do
  open "claude://resume?session=$id"
  for i in $(seq 30); do
    ls ~/Library/Application\ Support/Claude/claude-code-sessions/<accountUuid>/<orgUuid>/local_"$id".json \
      >/dev/null 2>&1 && { echo "OK $id"; break; }
    sleep 1
  done
done < ids.txt
```

## Preconditions

Found in the app's code, build 2.31226.x:

- The app must be running and signed in. Without a current account and workspace the import fails
  with "account information is unavailable".
- Do not switch workspace during the import. It then fails with "the account changed during the
  import". Switching workspace also stops every running local session
  ([#89966](https://github.com/anthropics/claude-code/issues/89966)).
- `claude://` links must not be disabled by an admin setting (`disableDeepLinkRegistration`). If your
  organization disabled them, ask the admin; do not work around the policy.
- The transcript must be a file under `~/.claude/projects`, and the folder it recorded as its working
  directory must be an absolute path.
- Very large transcripts import with a warning in the log that resuming may fail.

## Side effects

- The session opens and the window takes focus.
- A background Claude Code process starts for it: about 330 MB of memory, stopped after 30 idle
  minutes. Fifty imports in a row can use several GB. Import in batches with pauses.
- A session in `bypassPermissions` mode comes back as `acceptEdits`.
- The link trusts the session's project folder **without asking** (the app's code calls the import
  without `autoTrust: false`; the in-app resume picker passes it and refuses folders that are not
  trusted yet). Import only transcripts you know you created.
- The transcript's modification time is set to now.
- If the current workspace already has `local_<id>.json`, the app reuses it (and unarchives it). Running
  the import twice is safe.
- Permission grants and archive state are not carried over.

## Why the import finds nothing

**Help → Import Claude Code CLI Sessions…** answers `No CLI sessions to import` after a workspace
switch. From the app's code (`scanRecoverableCliSessions`) and its log line `[CCD-SessionRecovery]`:

1. It first collects every session id that **any** workspace on this computer knows: each
   `local_*.json` file name, its `cliSessionId`, `unarchivedCliSessionId` and `priorCliSessionIds`,
   plus the ids in `deleted_<id>` markers (at least those of the signed-in account). Records from all
   account and workspace folders count, not only the current one.
2. For each transcript in `~/.claude/projects`:
   - **`skippedFiltered`**: the id is already known (step 1), or it is not a UUID, or the transcript
     has no working directory, is only a subagent transcript, or came from an excluded entry point
     (SDK, `claude -p`-style automation, MCP, GitHub Action, Slack and others).
   - **`skippedNotLost`**: a transcript stamped by the desktop app itself that started at or after
     the earliest timestamp in the session index. The app assumes such a session is not lost.
   - **`skippedUntrusted`**: its folder is not trusted in the app yet.
3. Whatever is left is offered for import.

So a session listed in your old workspace never shows up, archived or not. Deleting it in the old
workspace writes a `deleted_<id>` marker, which the code also counts as known (the import dialog's
own text mentions deleted sessions, so there may be cases it handles differently), and since 2.1.284
deletes the transcript too ([#98642](https://github.com/anthropics/claude-code/issues/98642)). There is no
non-destructive way to make the built-in import pick these sessions up. The resume link skips this
scan and imports the one id you give it.

The counters in your log:

```bash
ls -tr ~/Library/Logs/Claude/main*.log | while read -r f; do grep -h "CCD-SessionRecovery" "$f"; done | tail -5
```

A scan in the case study's log on 2026-10-01: 893 transcripts scanned, 590 `skippedFiltered`,
302 `skippedNotLost`, 0 `skippedUntrusted`, 1 importable. Scans on the recovery day offered 3. None of
the sidebar sessions can appear there, because every workspace's records count as known.

## Alternatives that move files instead

- [claude-transplant](https://github.com/vitaliyhayda/claude-transplant) (macOS, MIT) moves
  `local_*.json` records and scheduled-task registries between workspace folders, with undo. The
  sessions leave the old workspace.
- The manual version of that, from the
  [dev.to post](https://dev.to/vitaliyhayda/claude-desktop-history-missing-after-switching-accounts-and-how-to-get-it-back-4a26):
  quit the app, move `local_<id>.json` into the other workspace's folder, start the app. Not tested
  here: it changes the app's private files and removes the session from the old workspace. Back up
  the session store first and never do it while the app runs.
- [claude-code-export-import](https://github.com/Dangelo123/claude-code-export-import) and
  [BasedGPT/claude-code-session-recovery](https://github.com/BasedGPT/claude-code-session-recovery)
  write `local_*.json` records themselves.

The resume link differs in one way: the app's own importer writes the record, so you do not depend on
the record format staying the same.
