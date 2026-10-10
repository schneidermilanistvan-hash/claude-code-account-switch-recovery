# Agent instructions

Unofficial community guide. Not affiliated with or endorsed by Anthropic.

This repository helps people who lost Claude Code desktop sessions, sidebar folders, scheduled tasks
(Routines) or published artifacts after switching Claude account, plan or workspace (for example
Pro/Max to Team, or one login in two organizations).

## If a user has this problem

Follow [skills/workspace-switch-recovery/SKILL.md](skills/workspace-switch-recovery/SKILL.md). The
background is in [README.md](README.md) and [docs/](docs/).

Safety rules, in short:

1. Back up `~/.claude/projects`, `~/.claude/file-history`, `~/.claude/scheduled-tasks`,
   `~/Library/Application Support/Claude/claude-code-sessions`, `claude_desktop_config.json` and
   `~/.claude/settings.json` first, and check that no copy failed.
2. Run the read-only commands first (`tools/ccrecover.py scan`, `sessions`, `plan`, `folders`,
   `tasks`, `artifacts`, and `import` without `--apply`). Show the user the plan.
3. Ask before `import --apply`, before opening any `claude://` link, and before publishing anything.
4. Never delete or archive sessions, `local_*.json`, `deleted_*` markers or transcripts. Since Claude
   Code 2.1.284, deleting a session from the sidebar also deletes its transcript.
5. Never switch the desktop app's workspace during an import.
6. macOS paths are tested; Windows and Linux are not. Say so when you use them.
7. Never suggest deleting the old account while its login is also the user's Team seat. Mention the
   one-way "Use your organization account only" migration only as a step after the recovery.
8. Transcripts, backups, logs and toolkit output can contain secrets (API keys, tokens, passwords,
   private messages). Never upload, post or commit them.
9. Follow the user's organization policies. If an admin disabled deep links, subscription access or
   a connector, say so and stop; do not work around it.

## If you are changing this repository

- Keep error strings and UI strings verbatim. They are what people search for.
- Never add real account ids, org ids, artifact ids, names, emails or absolute paths with a username.
  Use `<accountUuid>`, `<orgUuid>`, `<cliSessionId>`, `~`.
- Mark every claim as tested, documented (with a link) or unverified.
- `tools/ccrecover.py` must stay standard-library only and read-only by default. Run
  `python3 tools/test_ccrecover.py` after changes.
- Update "Last verified" dates when you re-test against a new app version.
