# FAQ: Claude Code history after switching account, plan or workspace

Short answers. Each links to the page with the steps. Tested on macOS, 2026-10-10.

### Are my Claude Code sessions deleted after switching to a Team plan?

Usually not. The transcripts stay in `~/.claude/projects/`. The desktop app shows a separate session
list per workspace, and your sessions are in the old workspace's list. Check with
[01-diagnose.md](01-diagnose.md).

### Why is the Code tab empty after my Max plan expired?

Same cause if the session store now has more than one workspace folder. Run
`python3 tools/ccrecover.py scan`. Others report an empty Code tab after a plan lapse while
`claude --resume` still lists the sessions ([#72541](https://github.com/anthropics/claude-code/issues/72541)).

### `claude --resume` works but the desktop sidebar is empty. Why?

The terminal reads transcripts directly. The sidebar reads the current workspace's records in
`~/Library/Application Support/Claude/claude-code-sessions/<accountUuid>/<orgUuid>/`. Import the
sessions into that workspace: [02-sessions.md](02-sessions.md).

### Why does "Import Claude Code CLI Sessions…" say `No CLI sessions to import`?

It skips every session that any workspace on this computer has recorded, including archived and
deleted ones, and Code-tab sessions it considers not lost.
[Details](02-sessions.md#why-the-import-finds-nothing).

### How do I move a Claude Code session from my personal workspace to my Team workspace?

Show the Team workspace in the app and run `open "claude://resume?session=<id>"` (tested). The
documented `claude --desktop --resume <id>` (Claude Code 2.1.285+) opens the same link but needs a
working CLI subscription login and was not tested across workspaces. The personal workspace keeps its
entry.
To move instead of copy, see [claude-transplant](https://github.com/vitaliyhayda/claude-transplant).

### Will deleting the sessions in my old workspace let the import find them?

No. The importer is built to skip ids it already knows, and a deleted session leaves a
`deleted_<id>` marker. Worse, since Claude Code 2.1.284 deleting a session from the sidebar deletes
its transcript
([#98642](https://github.com/anthropics/claude-code/issues/98642)). Do not do it.

### How do I get my sidebar folders back?

Read the old layout with `ccrecover.py folders`, then recreate the folders by hand or ask Claude in a
Code session to create them and move the sessions. [03-folders.md](03-folders.md).

### Why did my scheduled tasks (Routines) stop running?

They belong to one workspace and only fire while the app shows that workspace.
[04-routines.md](04-routines.md).

### Can I move a published artifact to my new workspace or keep its URL?

No. You can re-publish it from the new workspace, which gives a new URL, and rebuild a lost source
from the transcript. [05-artifacts.md](05-artifacts.md).

### What does `Your organization has disabled Claude subscription access for Claude Code` mean?

The organization the CLI's token belongs to does not allow Claude Code with a subscription login
(`oauth_org_not_allowed`). After a switch that is often the OLD workspace: run `claude auth login`,
pick the new one and re-test `claude -p "say ok"`. Only if it still fails does an Owner have to change
the setting, or you use an API key.
[06-auth-machines-connectors.md](06-auth-machines-connectors.md).

### Does Anthropic's "Bring your data with you" migration move Code tab sessions?

Its help article lists what moves (chats, projects, memory, Claude Code memory and settings, and more)
and what does not (published artifacts, connector sign-ins, custom skills, Claude Code cloud
sessions). Code-tab local sessions are not mentioned. It is one-way and same-email only.
See the [official options](../README.md#official-options).

### I bought Max through the App Store. Can I migrate into the Team?

Per the [help article](https://support.claude.com/en/articles/9267400), Keep both accounts is the
only option unless you first cancel the iOS subscription in your Apple ID settings.

### How long do I have before the transcripts are gone?

Desktop-started or Desktop-continued sessions: no age limit since Claude Code 2.1.248, unless an
organization policy sets one. Terminal and `claude -p` sessions: 30 days by default. Raise
`cleanupPeriodDays` now. [07-before-you-switch.md](07-before-you-switch.md).

### Can I recover sessions from another computer?

Yes, on that computer, as long as its transcripts exist. Each machine has its own store and login.
[06-auth-machines-connectors.md](06-auth-machines-connectors.md#other-machines).

### Does this work on Windows or Linux?

Untested. The paths are probably `%APPDATA%\Claude\claude-code-sessions` and
`~/.config/Claude/claude-code-sessions`. `claude --desktop --resume` is documented for macOS and
x64 Windows. Pass `--store` and `--projects` to the toolkit.

### Did you need a personal knowledge base or notes to do this?

No. Only what Claude Code leaves on disk. Notes helped to remember that a second machine existed.
See the [README](../README.md#do-i-need-notes-or-a-second-brain-for-this).

### Can I delete my old personal account once I am on Team?

Not while its login is also your Team seat, and not before you have recovered everything. The old
workspace is the only place the old session list and published artifact URLs live. The official
"Use your organization account only" migration also closes it and is one-way: choose it, if at all,
only after the recovery. Back up first ([07-before-you-switch.md](07-before-you-switch.md)).

### Can I share my transcripts or the toolkit output to get help?

Not publicly. Transcripts, file backups, the app log and files such as `artifacts.json` can contain
API keys, tokens, passwords, private messages and file contents. Describe the problem instead, and
redact ids and paths.

### Is this official?

No. Unofficial, not affiliated with or endorsed by Anthropic. It uses an undocumented link handler and private file formats observed in one app build. They
can change. The documented equivalent is `claude --desktop --resume`.
