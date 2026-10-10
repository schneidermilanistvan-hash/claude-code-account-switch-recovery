# Case study: recovering 161 Claude Code sessions and 51 artifacts after a Max to Team switch

An anonymized account of one real recovery on a Mac, done on 2026-10-10 with Claude Code itself.
Versions: Claude desktop app build 2.31226.x (bundled Claude Code 2.1.295), standalone CLI 2.1.284.
Unofficial; not affiliated with or endorsed by Anthropic.

## What happened

- A personal Claude Max subscription, bought through the iOS App Store, lapsed to Free.
- A Claude Team plan was bought, and the **same login** joined it. One login, two workspaces.
  (For App Store subscriptions, Anthropic's migration offers only "Keep both accounts" unless the iOS
  subscription is cancelled first, so two workspaces is the expected outcome.)

## What broke

| Symptom | Cause |
|---|---|
| Code tab sidebar empty in the Team workspace | Session records are per workspace; 161 sat in the old one |
| Help → Import Claude Code CLI Sessions… found nothing useful | It skips any session any workspace knows (a scan on 2026-10-01 in the app log: 893 scanned, 590 `skippedFiltered`, 302 `skippedNotLost`, 0 `skippedUntrusted`, 1 importable; scans on the recovery day offered 3) |
| Sidebar folders gone | Stored per workspace |
| Scheduled tasks stopped | Per-workspace scheduler; fires only for the workspace on screen |
| Published artifacts unreachable from the Team workspace | Artifacts belong to the workspace that published them |
| Every `claude -p` returned 403 `oauth_org_not_allowed` | The CLI's own login was stale: one Mac's token visibly still belonged to the old (lapsed) workspace, the other's status named the new one anyway; a fresh `claude auth login` fixed both |
| A second Mac's CLI still on the old workspace | CLI login is per machine |
| One connector in daily use missing | Connectors are per workspace |

## What was recovered, and how

| Item | Old workspace | Result | Method |
|---|---|---|---|
| Sessions | 161 (160 with a transcript, 1 cleared with `/clear` and found through `priorCliSessionIds`) | 55 imported, 0 failures | `open "claude://resume?session=<id>"`, oldest first, in batches |
| Which 55 | | 45 that were in folders + the 10 most recent loose ones | the rest stay reachable in the old workspace and through `claude --resume` |
| Sidebar folders | 9 | 9, same order, 45 sessions | the desktop app's sidebar tools, driven by Claude inside a Code session |
| Scheduled tasks | 6 | 4 recreated, same schedule | the app's create-scheduled-task tool; 2 finished one-offs dropped; 1 had been replaced by a launchd job meanwhile and was restored so the two do not race |
| Artifacts | 51 | 51 re-published, new URLs | see below |
| Connector | 1 in use | reconnected | by hand |
| `claude -p` | 403 | works again on both Macs | `claude auth login`, then `claude -p "say ok"` as the proof; see [docs/06](docs/06-auth-machines-connectors.md) |

Artifacts in detail:

| How | Count |
|---|---|
| Source still on disk, re-published | 21 |
| Scratchpad source gone; rebuilt from `~/.claude/file-history` backups + replayed `Write`/`Edit` calls up to the last successful publish; `Bash`/Python edits re-run in a sandbox with the recorded output as the check; each compared against the original session | 24 |
| Full HTML found in an old transcript (an earlier artifact `read` result) | 1 |
| Found in the second Mac's transcripts by searching the page title (the id never appeared there) | 3 |
| Multi-file page rebuilt by re-running its original build script on its saved input; all printed numbers matched | 1 |
| Contained a third party's private message; the owner reviewed it and it was kept private | 1 |

After that, every link to an old URL was rewritten: in documents, at the source of generated pages,
and in scheduled-task prompts. Pages that link each other were published again after the links were
updated.

## What did not work, or was not available

- The app's own import. By design it ignores sessions another workspace knows.
- `claude --desktop --resume` was not available: the standalone CLI was 2.1.284 and the command needs
  2.1.285. It was never tried. The raw link it opens was used instead.
- Archiving or deleting in the old workspace to "free" sessions. Ruled out by reading the app's code;
  deleting would also have deleted the transcripts on 2.1.284+.

## Costs and side effects

- Each import started a background Claude Code process of about 330 MB that stops after 30 idle
  minutes. Hence batches with pauses.
- Sessions that ran in `bypassPermissions` came back as `acceptEdits`.
- The app window jumps to each imported session. Leave the machine alone while it runs.

## Was a personal knowledge base needed?

No. The person had a large personal note collection ("second brain"). It helped with two things:
remembering that a second Mac existed and how to reach it, and background on what the work was. Every
recovery step ran on what Claude Code leaves on disk: transcripts, file backups and the desktop app's
session store. Anyone with those files can do the same.

## What decided the outcome

- The transcripts were still on disk. Desktop-started sessions have had no age limit since Claude
  Code 2.1.248; the oldest transcript (29 days) matched when `~/.claude` was created on that Mac.
- The app build had the `claude://resume` handler.
- Every artifact had been published from a Claude Code session whose transcript existed somewhere.
