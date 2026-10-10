# Claude Code sessions, folders, routines and artifacts missing after switching account, plan or workspace (Pro/Max to Team): how to get them back

You switched your Claude plan, account or organization. Now the **Code** tab in the Claude desktop
app is empty, the app's import finds nothing, scheduled tasks stopped, old artifact links point to a
workspace you no longer see, and `claude -p` returns a 403. This guide shows how to get it all back,
step by step, with a small read-only toolkit and the manual commands behind it.

> Unofficial. Not affiliated with Anthropic. Tested on macOS with the Claude desktop app build
> 2.31226.x (bundled Claude Code 2.1.295) and Claude Code CLI 2.1.284. Last verified 2026-10-10.
> The app's on-disk format is private and can change in any release.

## TL;DR

- **Your conversations are most likely still on your disk**, in `~/.claude/projects/`. Only the
  desktop app's per-workspace session list changed. One login with a personal and a Team workspace
  has two separate Code sidebars.
- **To bring one session into the workspace you are looking at:** back up first
  ([Step 0](#step-0-back-up-and-stop-the-clock)), keep the desktop app open on that
  workspace and run `open "claude://resume?session=<session-id>"` (tested). The documented command
  `claude --desktop --resume <session-id>` (Claude Code 2.1.285+) opens the same link, but needs a
  working CLI subscription login and was not tested across workspaces. Unlike the app's own import,
  the link works even when another workspace already lists the session.
- **For many sessions:** `python3 tools/ccrecover.py scan`, then `plan`, then `import` (dry run
  first). See [Step-by-step recovery](#step-by-step-recovery).
- **Sidebar folders, routines and connectors do not follow.** Recreate them. Published artifacts get
  new URLs; their sources can be rebuilt from the transcripts.
- **Do not delete sessions in the old workspace.** Since Claude Code 2.1.284, deleting a session from
  the sidebar also deletes its transcript ([#98642](https://github.com/anthropics/claude-code/issues/98642)).
- **How long you have:** transcripts of sessions started or last continued in Claude Desktop are kept
  at any age (Claude Code 2.1.248+), unless an organization policy limits it. Terminal and `claude -p`
  transcripts are deleted after 30 days by default. Raise `cleanupPeriodDays` now
  ([Before you switch](#before-you-switch-checklist)).
- **Do not delete the old account while its login is also your Team seat.** Keep it at least until
  sessions, routines and artifacts are recovered and links rewritten: the old workspace is the only
  place the old session list and artifact URLs live. The official "Use your organization account only"
  migration also closes the personal account and is one-way: choose it, if at all, only after
  Step 0 and the recovery.
- **Transcripts and backups can contain secrets** (API keys, tokens, passwords, private messages,
  file contents). Never post them, or this toolkit's output, in a public issue, gist or chat.
- **For AI agents:** review the skill file, then paste this into Claude Code or any coding agent:
  `Read https://raw.githubusercontent.com/schneidermilanistvan-hash/claude-code-account-switch-recovery/main/skills/workspace-switch-recovery/SKILL.md and follow it.`

## Symptoms

Each heading is the exact text you see, so search engines and agents can match it.

### The Code tab sidebar is empty after switching to a Team workspace

The Code tab shows no history after you joined a Team or Enterprise organization, switched account,
or your Pro/Max plan lapsed. Others report the same after a plan lapse alone
([#72541](https://github.com/anthropics/claude-code/issues/72541)). `claude --resume` in a terminal
still lists them (its picker starts with the current folder and can widen to all projects). The
sessions are listed in the *other* workspace's sidebar, not lost.
Go to [Step 2](#step-2-import-the-sessions).

### `No CLI sessions to import`

The full dialog from **Help → Import Claude Code CLI Sessions…** (wording from the app bundle; the
in-app dialog may phrase it differently):

```text
No CLI sessions to import
All importable Claude Code sessions on this computer, whether started in the Code tab or the
terminal, are already in your session list, were previously deleted, or are in folders you haven't
trusted in Claude yet.
```

"Already in your session list" includes the session lists of **every** workspace on this computer.
The importer skips any session that any workspace has recorded, including archived ones and, per
the app's code, deleted ones.
It also skips Code-tab sessions that started after the app began keeping records. So after a
workspace switch it finds none of the sessions the old workspace lists, by design (at most a few that
no workspace recorded). Archiving the sessions in the old workspace does not
change that, and deleting them destroys their transcripts (see the TL;DR). Details: [docs/02-sessions.md](docs/02-sessions.md#why-the-import-finds-nothing).

### `Your organization has disabled Claude subscription access for Claude Code · Use an Anthropic API key instead, or ask your admin to enable access`

Headless runs (`claude -p`, the Agent SDK, scripts, cron or launchd jobs) fail with this 403. In `-p`
mode and the SDK the error code is `oauth_org_not_allowed`. Check the cheap cause first: the CLI
keeps its own login token, and after a switch it can still hold the OLD workspace's token. If that
workspace's plan no longer includes Claude Code (a personal plan that lapsed to Free), every headless
run gets this 403, even while `claude auth status` already names the new workspace. `claude auth
login` fixes that case. Only if the 403 survives a fresh login is it the organization's server-side
setting. Go to [Step 6](#step-6-headless-runs-and-the-403).

### Scheduled tasks (Routines) stopped running

Each workspace has its own list of scheduled tasks and its own scheduler. A task fires only while the
app shows its workspace, the app is open and the computer is awake. Go to [Step 4](#step-4-recreate-scheduled-tasks-routines).

### Sidebar folders (groups) are gone

Folders and the order of sessions in them are stored per workspace. Imported sessions arrive loose.
Go to [Step 3](#step-3-recreate-sidebar-folders).

### Old artifact links do not open from the new workspace

A published artifact belongs to the workspace that published it. You cannot move it. You can
re-publish it from the new workspace, which gives a new URL. Go to [Step 5](#step-5-recover-published-artifacts).

### Another Mac still uses the old workspace

Every machine has its own transcripts, its own session store and its own CLI login. Go to
[Step 7](#step-7-other-machines-connectors-and-the-chrome-extension).

## Why it happens

One login can belong to several workspaces (organizations): for example your personal one and a Team
one. The desktop app keeps a separate session list per workspace. The transcripts are shared.

| What | Where (macOS) | Per workspace? |
|---|---|---|
| Code tab sessions (sidebar entries) | `~/Library/Application Support/Claude/claude-code-sessions/<accountUuid>/<orgUuid>/local_<id>.json` | yes |
| Conversation transcripts | `~/.claude/projects/<cwd-slug>/<cliSessionId>.jsonl` | no, shared |
| File backups taken before edits | `~/.claude/file-history/<sessionId>/<hash>@v<N>` | no, shared |
| Sidebar folders | `~/Library/Application Support/Claude/claude_desktop_config.json`, key `preferences.epitaxyPrefs["dframe-group-scopes"]["<accountUuid>/<orgUuid>"]` | yes |
| Scheduled task schedule and on/off | `scheduled-tasks.json` next to the `local_*.json` files | yes |
| Scheduled task prompt | `~/.claude/scheduled-tasks/<id>/SKILL.md` | no, shared |
| Connectors | your Claude account settings | yes |
| Published artifacts | Anthropic's servers | yes, and the URL never moves |
| CLI login used by `claude -p` | per machine (and per `CLAUDE_CONFIG_DIR`) | one workspace at a time |

Each `local_<id>.json` holds the sidebar entry: `title`, `cwd`, `lastActivityAt`, `permissionMode`,
`isArchived`, `scheduledTaskId`, and `cliSessionId`, the id of the transcript file. After `/clear`,
`cliSessionId` can be empty and the conversation is under the last id in `priorCliSessionIds`.

## Step-by-step recovery

The toolkit is one standard-library Python file: [tools/ccrecover.py](tools/ccrecover.py)
([tools/README.md](tools/README.md)). It is read-only except `plan --out`, `rebuild-file --out` and
`import --apply`.

Ground rules:

1. **Back up first** (Step 0) and check that no copy failed.
2. **Dry-run first.** Run `import` without `--apply` and read what it would do.
3. **Delete nothing:** no sessions, `local_*.json`, `deleted_*` markers or transcripts, and not the
   old account while its login is also your Team seat.
4. **Do not edit the app's own files** (`claude_desktop_config.json`, the session store) while the
   app runs. This guide never needs you to.
5. **Keep transcripts, backups and toolkit output private.** They can contain secrets.
6. **Follow your organization's policies.** If an admin disabled deep links, subscription access or
   a connector, ask the admin; do not work around it. If either workspace belongs to an employer or
   school, check its rules before you copy sessions or re-publish pages across workspaces.

```bash
git clone https://github.com/schneidermilanistvan-hash/claude-code-account-switch-recovery
cd claude-code-account-switch-recovery
python3 tools/test_ccrecover.py      # self-tests on fake data, touches nothing real
```

A workspace is written `<accountUuid>/<orgUuid>`. Any unique prefix works, for example `ab12/cd34`.

### Step 0: Back up and stop the clock

Quit nothing yet. Copy everything first.

```bash
B=~/claude-backup-$(date +%Y%m%d-%H%M%S); mkdir "$B" && echo "backup: $B"
for p in ~/.claude/projects ~/.claude/file-history ~/.claude/scheduled-tasks ~/.claude/settings.json \
    ~/Library/Application\ Support/Claude/claude-code-sessions \
    ~/Library/Application\ Support/Claude/claude_desktop_config.json; do
  if [ -e "$p" ]; then cp -Rp "$p" "$B"/ || echo "COPY FAILED: $p"; else echo "not present: $p"; fi
done
du -sh "$B"/*
```

Every `COPY FAILED` line means the backup is incomplete: fix it before you go on (`not present` is
fine for a folder you never had). The backup holds your full transcripts, which can contain API keys,
tokens, passwords, private messages and file contents. Keep it private: never upload it, attach it to
an issue or commit it.

Then raise the cleanup period so terminal-started transcripts are not swept while you work. Add this
to `~/.claude/settings.json` (merge it into the existing JSON; the backup above has a copy):

```json
{ "cleanupPeriodDays": 3650 }
```

An organization's managed settings override this; if yours do, ask the admin rather than working
around them. Details: [docs/07-before-you-switch.md](docs/07-before-you-switch.md).

### Step 1: Find the workspaces

```bash
python3 tools/ccrecover.py scan
```

It lists every `<accountUuid>/<orgUuid>` folder with its session count, how many have a transcript,
deleted markers and scheduled tasks. The old workspace is the one with your sessions. The current one
is usually new and nearly empty. Manual equivalent:

```bash
cd ~/Library/Application\ Support/Claude/claude-code-sessions
for d in */*/; do echo "$d  $(ls "$d" | grep -c '^local_') sessions"; done
```

Details: [docs/01-diagnose.md](docs/01-diagnose.md).

### Step 2: Import the sessions

Pick what to bring over. The old workspace keeps its list; this makes a second entry, it does not
move the old one.

```bash
python3 tools/ccrecover.py sessions --from <old>                 # newest first
python3 tools/ccrecover.py plan --from <old> --to <new> --folders --recent 10 --out ids.txt
python3 tools/ccrecover.py import ids.txt --to <new>             # dry run: prints what it would open
```

`plan` writes ids oldest first, so the newest end up on top. It skips archived sessions, sessions
without a transcript, runs of scheduled tasks and sessions the target already has.

Only after the Step 0 backup and the dry run above: **show the target workspace in the desktop
app**, leave it alone, and run:

```bash
python3 tools/ccrecover.py import ids.txt --to <new> --apply --batch 10 --pause 20
```

For each id it runs `open "claude://resume?session=<id>"`, waits for `local_<id>.json` to appear in
the target folder and reports OK or FAIL. Manual equivalent, one session:

```bash
open "claude://resume?session=<cliSessionId>"
# documented alternative that opens the same link: needs Claude Code 2.1.285+, a working CLI
# subscription login, macOS or x64 Windows; not tested across workspaces
claude --desktop --resume <cliSessionId>
```

What to expect:

- The session opens in the app with its title and full history.
- A background Claude Code process starts for it (about 330 MB of memory, stops after 30 idle minutes).
  Import in batches.
- `bypassPermissions` comes back as `acceptEdits`.
- The app trusts the session's project folder without asking. Only import transcripts you know are yours.
- The transcript's modification time is set to now.
- Running it twice is safe: an existing entry is reused.
- Do not switch workspace during an import: the import fails, and switching also stops running
  sessions ([#89966](https://github.com/anthropics/claude-code/issues/89966)).

Details, preconditions and the importer internals: [docs/02-sessions.md](docs/02-sessions.md).

### Step 3: Recreate sidebar folders

```bash
python3 tools/ccrecover.py folders --from <old> --to <new>
```

It prints each old folder in order with the sidebar keys of the sessions you imported. Recreate the
folders in the app by hand, or ask Claude inside a Code session to do it: the desktop app gives
Claude sidebar tools to create a folder and move sessions into it. Details:
[docs/03-folders.md](docs/03-folders.md).

### Step 4: Recreate scheduled tasks (Routines)

```bash
python3 tools/ccrecover.py tasks --from <old>
```

It prints each task's schedule, on/off state and prompt file. The prompt is still on disk in
`~/.claude/scheduled-tasks/<id>/SKILL.md`. Create the task again in the new workspace with the same
schedule (in the app, or by asking Claude in a Code session to create the scheduled task). Skip
finished one-off tasks. If you replaced a task with a cron or launchd job in the meantime, keep only
one of them. Details: [docs/04-routines.md](docs/04-routines.md).

### Step 5: Recover published artifacts

You cannot move an artifact or keep its URL. You can re-publish it from the new workspace.

```bash
python3 tools/ccrecover.py artifacts --json > artifacts.json
```

This lists every artifact your transcripts published: URL, title, source path, whether the source is
still on disk, declared files and the session that first published it. Then:

1. **Source still on disk:** re-publish it from the new workspace.
2. **Source gone** (scratchpads under `/private/tmp` are temporary): rebuild it from the transcript.
   ```bash
   python3 tools/ccrecover.py rebuild-file --transcript <first-publish>.jsonl \
     --path /abs/path/page.html --out page.html
   ```
   It starts from the newest `~/.claude/file-history` backup taken before the last successful
   publish (if any), replays the recorded `Write` and `Edit` calls after it, and lists the `Bash`
   commands that touched the file; re-run those yourself and compare with their recorded output.
   In the case study it rebuilt 9 of 23 lost pages exactly on its own; the rest needed the recorded
   shell steps re-run ([details](docs/05-artifacts.md)).
3. **Other places a copy may hide:** an earlier artifact `read` result in a transcript holds the
   full HTML; another machine's transcripts (search by the page title, the id may never appear there);
   multi-file pages can be rebuilt by re-running their build script.
4. **Read every page before you publish it again.** Old pages can contain other people's data.
5. **Rewrite every link** to the old URLs: your files, generated pages (fix the generator), routine
   prompts. Publish pages that link each other, then update the links and publish again. Copy each
   file before you change it and review the diff.

Details and the method behind the rebuild: [docs/05-artifacts.md](docs/05-artifacts.md).

### Step 6: Headless runs and the 403

```bash
claude -p "say ok"        # does it return the oauth_org_not_allowed 403?
claude auth login         # sign in again in a real terminal; pick the new workspace if asked
claude auth status        # orgName and subscriptionType should now name the new workspace
claude -p "say ok"        # re-test: this, not auth status, is the proof
```

Fixes, in order:

1. Sign the CLI in again with `claude auth login` and re-test `claude -p`. Do this even if
   `claude auth status` or `/status` already shows the new workspace: in the case study one Mac's
   status named the new workspace (with the old plan type, `max`) while every run still failed, and
   the 403 went away only after a fresh login. The second Mac's status showed the old workspace. A
   fresh login fixed both.
2. If the 403 survives a fresh login into the right workspace, an Owner of that organization has to
   allow Claude Code with a subscription login. No local setting can override it.
3. Or use a Console API key instead of the subscription (billed separately).

Check every script, cron job and launchd job that calls `claude -p`; they fail quietly. Details:
[docs/06-auth-machines-connectors.md](docs/06-auth-machines-connectors.md).

### Step 7: Other machines, connectors and the Chrome extension

- **Other machines:** repeat Steps 0 to 5 on each one. Run `claude auth login` there too, then re-test `claude -p "say ok"`.
- **Connectors** are per workspace. Reconnect each one you use in the new workspace.
- **The Chrome extension** is signed in to one workspace. Sign it in to the one you use now.

## What cannot be recovered

- **Transcripts that are already gone**: swept by `cleanupPeriodDays`, deleted with their sidebar
  entry, or never on this machine. Without the transcript there is nothing to import or replay.
- **The same artifact URLs.** Re-publishing gives new URLs. The old ones stay with the old workspace.
  Whether a workspace that dropped to Free still serves them is not verified.
- **Cloud sessions** (Claude Code on the web) are not local transcripts. This method does not touch
  them.
- **Permission grants and archive state** of imported sessions.
- **Edits made only through shell commands** whose effect was not recorded, and file backups older
  than the last 100 checkpoints of a session.
- **Promotional credit and an unused limit reset** on a plan that drops to Free. Anthropic's
  [promotion credit terms](https://www.anthropic.com/legal/promotion-credit-terms) say credit is
  forfeited on a downgrade to a free plan and not reinstated; the
  [limit reset article](https://support.claude.com/en/articles/17007452) says an unused reset is gone
  after a downgrade. Use them before you switch.

## Official options

From Anthropic's current docs and help center, read 2026-10-10.

| Option | What it does | What it does not do |
|---|---|---|
| **Keep both accounts** (the account-menu switcher) | Personal and Team workspaces coexist; you switch between them. | Each keeps its own Code sidebar, folders, routines and connectors. |
| **Use your organization account only → Bring your data with you** ([support article 9267400](https://support.claude.com/en/articles/9267400), updated 2026-10-07) | One-way, same email only. Moves chats, artifacts inside chats, projects, files, memory, Claude Code memory and personal settings. Closes the personal account: back up and recover first, because the old artifact URLs live only there. | Does not move custom skills, connector sign-ins, custom connectors, published artifacts, public share links, Cowork desktop sessions (they stay on your computer), or Claude Code cloud sessions (web, scheduled tasks, mobile). Code-tab local sessions are not mentioned. Not offered to Enterprise organizations with HIPAA readiness or customer-managed keys. |
| **Pro or Max bought through the Apple App Store** | Per the same article, Keep both accounts is the only option unless you first cancel the iOS subscription in your Apple ID settings. | This is exactly the case where you end up with two workspaces on one login. |
| **Export data** (Settings → Privacy → Export data) | An emailed download link, valid for 24 hours. | Your Code-tab transcripts are already on your disk; the export does not restore a sidebar. |
| **`claude --desktop --resume <id>`** and Desktop's `/resume` ([docs](https://code.claude.com/docs/en/desktop)) | Moves a CLI session into the desktop app. Needs Claude Code 2.1.285+. | Documented for CLI sessions; the docs do not say it imports across workspaces. It opens the same `claude://resume` link this guide uses. |

Two official sources disagree on publishing in Team. The help article says "Publishing isn't
available on Team and Enterprise plans". The [Claude Code artifacts docs](https://code.claude.com/docs/en/artifacts)
describe sharing inside a Team organization. In the case below, 51 artifacts were re-published from
Claude Code in a Team workspace on 2026-10-10. The help article most likely means chat publishing on
claude.ai. Check your own plan.

## Before you switch: checklist

1. Set `"cleanupPeriodDays": 3650` in `~/.claude/settings.json`.
2. Copy `~/.claude/projects`, `~/.claude/file-history`, `~/.claude/scheduled-tasks`, the folder
   `~/Library/Application Support/Claude/claude-code-sessions` and `claude_desktop_config.json`.
3. Write down your sidebar folders and routines (`ccrecover.py folders`, `ccrecover.py tasks`).
4. Run `ccrecover.py artifacts` and save the list. Move artifact sources out of temporary folders.
5. List your connectors and anything that runs `claude -p` on a schedule.
6. Ask the Team Owner whether Claude Code subscription access is enabled for the organization.
7. Note every machine where you use Claude Code.
8. Finish or stop running sessions. Switching workspace stops them.
9. Do not delete the old account while its login is also your Team seat, and do not delete old
   sessions. Choose the one-way "Use your organization account only" migration, if at all, only after
   the recovery.
10. Keep the backup private. Transcripts can contain API keys, tokens and passwords.

Full list: [docs/07-before-you-switch.md](docs/07-before-you-switch.md).

## Do I need notes or a "second brain" for this?

No. Everything above runs on what Claude Code already leaves on disk: the transcripts in
`~/.claude/projects`, the file backups in `~/.claude/file-history`, and the desktop app's session
store. In the case below, a large personal note collection existed. It helped only to remember that a
second Mac existed and how to reach it, and with task context. None of the recovery steps used it.

What you do need:

- The transcripts still on disk (same machine, or access to the other machines where you worked).
- A desktop app version with the `claude://resume` handler (the build above has it; Claude Code
  2.1.285+ documents `claude --desktop --resume`).
- The desktop app signed in and showing the target workspace, with deep links not disabled by policy.
- For artifacts: the transcript of the session that published each one.

## Case study (anonymized)

A personal Max subscription bought through the App Store lapsed to Free. The same login joined a new
Team plan. Result: two workspaces on one login.

| Item | Old workspace | Recovered |
|---|---|---|
| Code tab sessions | 161 (160 with a transcript, 1 found through its prior id after `/clear`) | 55 imported (45 in folders + 10 most recent), 0 failures |
| Sidebar folders | 9 | 9, same order |
| Scheduled tasks | 6 (2 finished one-offs) | 4 recreated with the same schedule |
| Published artifacts | 51 | 51: 21 from sources on disk, 24 rebuilt from file backups and replayed edits, 1 from a saved copy in a transcript, 3 from another Mac's transcripts, 1 by re-running its build script, 1 kept private after the owner reviewed it |
| `claude -p` | 403 `oauth_org_not_allowed` | fixed by a fresh `claude auth login` on both Macs (one still visibly held the old workspace's token) |

An import scan in the app's log on 2026-10-01 counted 893 transcripts and found 1 importable; scans on
the recovery day found 3. None of the sidebar sessions can appear there. Full write-up:
[CASE-STUDY.md](CASE-STUDY.md).

## Platform support

| | macOS | Windows | Linux |
|---|---|---|---|
| Session store | `~/Library/Application Support/Claude/claude-code-sessions/` (tested) | `%APPDATA%\Claude\claude-code-sessions\` (untested) | `~/.config/Claude/claude-code-sessions/` (untested; desktop app is beta) |
| Transcripts | `~/.claude/projects/` (tested) | `%USERPROFILE%\.claude\projects\` (untested) | `~/.claude/projects/` (untested) |
| Deep link | `open "claude://resume?session=<id>"` (tested) | `start "" "claude://resume?session=<id>"` (untested) | not documented |
| `claude --desktop --resume` | documented | documented for x64 | not documented |

On Windows and Linux pass `--store` and `--projects` to `ccrecover.py`; `import --apply` prints each
command for you to run and waits `--timeout` seconds (default 30) for the new record.

## Related work and what is new here

This is not the only write-up. Credit where it is due:

- [anthropics/claude-code#94507](https://github.com/anthropics/claude-code/issues/94507): session
  records are per organization while transcripts are shared.
- [dev.to: "Claude Desktop history missing after switching accounts, and how to get it back"](https://dev.to/vitaliyhayda/claude-desktop-history-missing-after-switching-accounts-and-how-to-get-it-back-4a26)
  and its tool [claude-transplant](https://github.com/vitaliyhayda/claude-transplant): moves session
  records and scheduled-task registries between workspace folders, with undo. It moves rather than
  copies.
- [claude-code-export-import](https://github.com/Dangelo123/claude-code-export-import): export and
  import sessions across machines and accounts, including cloud sessions.
- [BasedGPT/claude-code-session-recovery](https://github.com/BasedGPT/claude-code-session-recovery):
  diagnose and rebuild `local_*.json` records from transcripts, plus backups.
- [claude-code-session-restorer](https://github.com/sahol3/claude-code-session-restorer) (Windows),
  [claude-account-switcher](https://github.com/SnlperStripes/claude-account-switcher),
  [ccdejavu](https://github.com/wjames111/ccdejavu).
- [claude-file-recovery](https://github.com/hjtenklooster/claude-file-recovery): rebuild files from
  transcripts. Closest prior art for the artifact rebuild.
- [claude-code-history-viewer](https://github.com/jhlee0409/claude-code-history-viewer): browse
  transcripts.
- Issues on the same symptoms: [#95272](https://github.com/anthropics/claude-code/issues/95272)
  (routines per workspace), [#77601](https://github.com/anthropics/claude-code/issues/77601)
  (folders wiped), [#74662](https://github.com/anthropics/claude-code/issues/74662) (asks to open
  sessions missing from the sidebar), [#95863](https://github.com/anthropics/claude-code/issues/95863)
  (importer skips transcripts, Windows), [#69585](https://github.com/anthropics/claude-code/issues/69585) (new machine).

What I did not find written down anywhere, as of 2026-10-10:

- That `claude://resume?session=<id>` (the link `claude --desktop --resume` opens; Anthropic's errors
  page shows it) imports a session into the workspace on screen even when another workspace already
  lists it, with no hand-editing of records.
- Why **Import Claude Code CLI Sessions…** finds nothing after a workspace switch.
- Where sidebar folders live per workspace, and how to recreate folders and routines (that routines
  are per workspace is already known from #95272 and claude-transplant).
- A tested method to inventory and rebuild published artifacts from transcripts and file backups.
- One checklist for sessions, folders, routines, artifacts, connectors, other machines, the 403 and
  retention.

More: [docs/faq.md](docs/faq.md) · For agents: [AGENTS.md](AGENTS.md),
[SKILL.md](skills/workspace-switch-recovery/SKILL.md), [llms.txt](llms.txt).

## Install as a Claude Code plugin or skill

```bash
claude plugin marketplace add schneidermilanistvan-hash/claude-code-account-switch-recovery
claude plugin install workspace-switch-recovery@workspace-switch-recovery
```

Or copy `skills/workspace-switch-recovery` to `~/.claude/skills/`, and clone the repo for the toolkit.
Then ask Claude: "my Code sidebar is empty after switching to Team".

## Privacy and license

Transcripts (`~/.claude/projects`), file backups (`~/.claude/file-history`), the app log
(`~/Library/Logs/Claude/main*.log`), your Step 0 backup and every output of `ccrecover.py`
(`ids.txt`, `artifacts.json`, rebuilt pages) can contain API keys, tokens, passwords, private
messages, file contents, paths and titles. Never upload them, attach them to a GitHub issue, paste
them into a public chat or commit them. To report a problem here, describe it and redact ids and
paths. The repository's `.gitignore` keeps the toolkit's usual output files out of commits. Nothing
in this repository contains real account ids, names or paths; examples use placeholders.

MIT. See [LICENSE](LICENSE). Claude and Claude Code are trademarks of Anthropic. This project is not
affiliated with or endorsed by Anthropic.
