# Before you switch Claude plan, account or workspace: keep your Claude Code history

Ten minutes before a switch save hours after it. Do this before you join a Team plan, change
subscription, let a plan lapse, or sign in with another account. Unofficial; not affiliated with or endorsed by Anthropic.

## Retention: how long your transcripts survive

Everything in this guide needs the transcripts in `~/.claude/projects`. Per the
[`.claude` directory docs](https://code.claude.com/docs/en/claude-directory) and the
[settings reference](https://code.claude.com/docs/en/settings-reference):

- Claude Code deletes transcripts older than `cleanupPeriodDays`. The default is 30, the minimum is 1,
  and `0` is rejected. The deletion is silent.
- Since Claude Code 2.1.248, the transcript of a session **started or last continued in Claude
  Desktop** is kept at any age. `desktopSessionCleanupPeriodDays` can set a limit; its default `0`
  means none.
- That exemption does not apply when managed settings (for example your organization's) set
  `cleanupPeriodDays`, or under a HIPAA configuration.
- Terminal and `claude -p` sessions are swept after `cleanupPeriodDays`.
- The same sweep removes `file-history/<session>/`, and a session's scratchpad is temporary (on
  macOS it sits under `/private/tmp`). `file-history` keeps only the last 100 checkpoints of a session plus each file's first
  backup.
- Community reports say the sweep goes by file modification time
  ([#62250](https://github.com/anthropics/claude-code/issues/62250)). A restored old copy can be
  deleted by the next sweep unless you raise the setting first.

In the case study the oldest transcript was 29 days old, but `~/.claude` itself had been created 29
days earlier. That is not evidence of a sweep.

## Checklist

1. **Raise the cleanup period.** In `~/.claude/settings.json`:
   ```json
   { "cleanupPeriodDays": 3650 }
   ```
   No maximum is documented. Managed settings win over this; if your organization set them, ask the
   admin rather than working around them.
2. **Back up.**
   ```bash
   B=~/claude-backup-$(date +%Y%m%d-%H%M%S); mkdir "$B" && echo "backup: $B"
   for p in ~/.claude/projects ~/.claude/file-history ~/.claude/scheduled-tasks ~/.claude/settings.json \
       ~/Library/Application\ Support/Claude/claude-code-sessions \
       ~/Library/Application\ Support/Claude/claude_desktop_config.json; do
     if [ -e "$p" ]; then cp -Rp "$p" "$B"/ || echo "COPY FAILED: $p"; else echo "not present: $p"; fi
   done
   du -sh "$B"/*
   ```
   Stop if any line says `COPY FAILED`. Keep the backup private: transcripts can contain API keys,
   tokens, passwords and private messages.
3. **Write down your sidebar folders and routines.**
   ```bash
   python3 tools/ccrecover.py scan
   python3 tools/ccrecover.py folders --from <current> --json > folders.json
   python3 tools/ccrecover.py tasks   --from <current> --json > tasks.json
   ```
4. **Save your artifact list, and move sources out of temporary folders.**
   ```bash
   python3 tools/ccrecover.py artifacts --json > artifacts.json
   ```
   Any source under `/private/tmp` or a session scratchpad will not survive. Copy it somewhere
   permanent now.
5. **List your connectors** and everything that runs `claude -p` on a schedule (cron, launchd,
   scripts).
6. **Plan to sign the CLI in again** with `claude auth login` on every machine right after the
   switch, and re-test `claude -p "say ok"`. A CLI that keeps the old workspace's token returns
   `oauth_org_not_allowed` once that plan lapses. Also ask the Team Owner whether Claude Code with
   subscription sign-in is enabled for the organization.
7. **List every machine** where you use Claude Code. Each one needs the same steps.
8. **Finish running sessions.** Switching workspace stops them mid-turn.
9. **Know your options.** Keep both accounts, or bring your data into the Team workspace (one-way,
   same email only, not offered for App Store subscriptions unless cancelled first). See the
   [official options](../README.md#official-options). Neither moves your Code sidebar.
10. **Do not delete or archive old sessions afterwards.** Since Claude Code 2.1.284, deleting a
    session from the sidebar also deletes its transcript
    ([#98642](https://github.com/anthropics/claude-code/issues/98642)). Archiving does not help the
    import either, and `ccrecover.py plan` skips archived sessions unless you pass
    `--include-archived`.
11. **Do not delete the old account** while its login is also your Team seat. Keep it at least
    until sessions, routines and artifacts are recovered and links rewritten: the old workspace is
    the only place the old session list and artifact URLs live. The official "Use your organization account only"
    migration also closes it and is one-way: choose it, if at all, only after the recovery.
12. **Keep the backup private.** Transcripts, file backups and logs can contain API keys, tokens,
    passwords and private messages. Never upload, post or commit them.
13. **Follow your organization's rules.** If either workspace belongs to an employer or school,
    check that its policy allows copying sessions and keeping backups. If an admin disabled
    something, ask the admin; do not work around it.

After the switch, follow the [step-by-step recovery](../README.md#step-by-step-recovery).
