# ccrecover

Unofficial; not affiliated with or endorsed by Anthropic.

A dependency-free helper (Python 3.9+, standard library only) for one situation: you switched
Claude plan or workspace (personal to Team, subscription lapsed, second login) and the Claude
desktop app's **Code** tab is now empty, scheduled tasks stopped, and published artifacts live in a
workspace you can no longer see. Your conversations are still on disk. `ccrecover` finds them, shows
what is missing and re-attaches them.

Tested on macOS with the Claude desktop app 2.31226.x (bundled Claude Code 2.1.29x) and Claude Code
CLI 2.1.284. Windows and Linux paths are guesses: pass `--store` and `--projects` yourself. Read
`../README.md` for the full story of what happened and why the app's own "Import sessions" button
said there was nothing to import.

Everything is **read-only** except three things, all opt-in:
`plan --out` writes an id list, `rebuild-file --out` writes a file, and `import --apply` asks the
desktop app to import sessions. `import` is a **dry run unless you pass `--apply`**. Back up first
(`../README.md`, Step 0) and read the dry run before `--apply`. `rebuild-file` refuses to overwrite
an existing `--out` file unless you pass `--force`.

```
python3 ccrecover.py scan
python3 ccrecover.py sessions --from <account>/<workspace> [--limit N] [--json]
python3 ccrecover.py plan     --from <old> --to <new> [--folders] [--recent N] [--all] [--out ids.txt]
python3 ccrecover.py import ids.txt --to <new> [--batch 10] [--pause 20] [--apply]
python3 ccrecover.py folders  --from <old> [--to <new>] [--json]
python3 ccrecover.py tasks    --from <old> [--json]
python3 ccrecover.py artifacts [--json]
python3 ccrecover.py rebuild-file --transcript T.jsonl --path /abs/path/file.html [--until ISO] [--out F] [--force]
python3 test_ccrecover.py            # self-tests on fake data, touches nothing real
```

A workspace is written `<accountUuid>/<orgUuid>`; any unique prefix works (`ab12/cd34`). Global
options `--store DIR` and `--projects DIR` come before the subcommand.

## Where things live (macOS)

| What | Where |
|---|---|
| Sidebar sessions | `~/Library/Application Support/Claude/claude-code-sessions/<accountUuid>/<orgUuid>/local_<id>.json` |
| Deleted markers, scheduled tasks | `deleted_<id>`, `scheduled-tasks.json` in the same folder |
| Transcripts | `~/.claude/projects/<cwd-slug>/<cliSessionId>.jsonl` |
| Sidebar folders | `~/Library/Application Support/Claude/claude_desktop_config.json`, key `preferences.epitaxyPrefs["dframe-group-scopes"]["<accountUuid>/<orgUuid>"]` |
| Scheduled-task prompts | `~/.claude/scheduled-tasks/<id>/SKILL.md` (shared by all workspaces) |
| File backups before edits | `~/.claude/file-history/<sessionId>/<hash>@v<N>` |

## Recovery order

1. `scan`: every workspace folder with session counts, how many have a transcript, deleted markers,
   scheduled tasks. A session with an empty `cliSessionId` but `priorCliSessionIds` was `/clear`-ed;
   its conversation is under the last prior id and every command uses that automatically.
2. `sessions --from <old>`: newest first, with date, title, conversation id, folder.
3. `plan --from <old> --to <new> --folders --recent 10`: writes `ids.txt` oldest first (so the newest
   ends up on top), skipping archived sessions, sessions without a transcript, runs of scheduled tasks
   (`--include-task-runs` to keep them) and ones the target already has. Prints an estimate of RAM.
4. `import ids.txt --to <new>`: dry run. Then, with the desktop app **showing the target workspace**,
   `--apply` runs `open "claude://resume?session=<id>"` per id (macOS), waits up to 30 s for
   `local_<id>.json` to appear in the target folder and reports OK or FAIL, pausing between batches.
   Refuses if the target folder does not exist. On Windows and Linux it prints the command instead.
5. `folders --from <old>`: the old folder layout with the new sidebar keys (`code:local_<id>`), so you
   (or Claude, through the desktop app's sidebar tools) can recreate the folders in the same order.
6. `tasks --from <old>`: schedule, enabled state, prompt path, whether the prompt file still exists.
7. `artifacts`: inventory of every published artifact found in your transcripts (URL, title, last
   publish, source path, source still on disk, declared files and capabilities, session of the first
   publish). `rebuild-file` then rebuilds sources that are gone.

## Side effects of the resume deep link

Each `claude://resume?session=<id>` opens/focuses that session in the app, prewarms a background
Claude Code process (about 330 MB resident, 30 minute idle timeout) and brings a
`bypassPermissions` session back as `acceptEdits`. Importing 55 sessions in one go means gigabytes of
RAM and a window that keeps jumping, hence the batches and the pause. Do not touch the app while it
runs.

## rebuild-file

Replays `Write` / `Edit` / `MultiEdit` calls on one path in transcript order, up to the last
successful `Artifact` publish of that path (or `--until`). Calls whose tool result was an error are
skipped. When an edit does not apply, it first tries the `originalFile` stored in that edit's tool
result, then the newest `~/.claude/file-history` backup (named by `file-history-snapshot` lines in
the transcript) taken before the edit and containing the text, re-applies the later edits and
continues. Every edit is reported as applied or failed on stderr; the file goes to `--out` (or stdout).

It also lists every `Bash` command that mentions the file. If one of them modified it (a `sed`, a
build script), `rebuild-file` cannot know the result: re-run them in order, using their recorded
output as the oracle. Test on the author's machine: a page written once and published rebuilt byte-for-byte; of 12
on-disk pages with Write/Edit history in their first-publish session, 3 matched the file on disk
exactly and 9 differed. Each of the 9 had Bash commands touching the file (flagged by the tool); I did
not verify that they account for every difference.

## Limits you should know

- **Retention decides what is recoverable.** Per the current Claude Code docs, local transcripts
  under `~/.claude/projects` are deleted once older than `cleanupPeriodDays` (default 30, minimum 1),
  with these exceptions: a session started or last continued in Claude Desktop is kept at any age
  (Claude Code v2.1.248 or later; earlier versions delete it after `cleanupPeriodDays`), unless
  managed settings set `cleanupPeriodDays` or a HIPAA configuration applies, in which case
  `cleanupPeriodDays` applies to them too. `desktopSessionCleanupPeriodDays` gives them an age limit.
  Pre-edit snapshots in `file-history/` are swept the same way. Not verified on disk: the test machine's
  oldest transcript was 29 days old with no setting changed, but its oldest sidebar session is about as
  old, so that says nothing about cleanup. Before changing plan: copy `~/.claude/projects` and
  `~/.claude/file-history` somewhere safe, and raise `cleanupPeriodDays` if your sessions are CLI-started.
- The importer only brings transcripts back as sidebar sessions; connectors, cloud sessions, and
  the Chrome extension's sign-in stay per workspace.
- Artifacts are new URLs when re-published; old ones live in the old workspace.
- `artifacts` only sees artifacts published from a Claude Code session whose transcript still exists.
  Sources written by Bash scripts have no Write history to replay.
- The on-disk format is private to the desktop app and changes between versions. Treat the field
  names (`cliSessionId`, `priorCliSessionIds`, `dframe-group-scopes`) as observed, not promised.
- Transcripts, file backups and every output of this tool (`ids.txt`, `artifacts.json`, rebuilt
  files) can contain API keys, tokens, passwords, private messages and your username. Never upload,
  post or commit them; redact before sharing anything.
