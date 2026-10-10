# Changelog

## 1.0.1 - 2026-10-10

- Corrected the 403 (`oauth_org_not_allowed`) advice. In the case study a fresh `claude auth login`
  fixed it on both Macs; one of them visibly still held the old (lapsed) workspace's token. `claude auth status` can name the new workspace while the
  token is still the old one, so `claude -p "say ok"` after a fresh login is the proof. The Owner
  setting and an API key stay as the fallbacks.

## 1.0.0 - 2026-10-10

- Guide: symptoms with exact error strings, step-by-step recovery, official options, before-you-switch
  checklist, platform notes, related work.
- `tools/ccrecover.py`: `scan`, `sessions`, `plan`, `import` (dry run unless `--apply`), `folders`,
  `tasks`, `artifacts`, `rebuild-file`; self-tests in `tools/test_ccrecover.py`.
- Agent skill `workspace-switch-recovery`, plugin and marketplace manifests, `AGENTS.md`, `llms.txt`.
- Verified against Claude desktop build 2.31226.x, Claude Code 2.1.284 and 2.1.295, macOS.
- Safety and privacy pass: backup reports failed copies and never merges into an earlier backup,
  ground rules (back up, dry-run, delete nothing, keep the old account, keep transcripts private,
  follow org policy), `rebuild-file` refuses to overwrite without `--force`, `.gitignore` for
  toolkit output, unofficial notice on every page.
