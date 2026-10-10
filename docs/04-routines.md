# Claude Code scheduled tasks (Routines) stopped after switching workspace

Desktop scheduled tasks, shown under **Routines** in the Code sidebar, belong to one workspace. After
a switch they stop firing, and the new workspace has none.

Tested on macOS, desktop app build 2.31226.x, 2026-10-10. Unofficial; not affiliated with or endorsed by Anthropic. Back up first
([README Step 0](../README.md#step-0-back-up-and-stop-the-clock)).

## How they are stored

| Part | Where | Shared? |
|---|---|---|
| Schedule, on/off state | `~/Library/Application Support/Claude/claude-code-sessions/<accountUuid>/<orgUuid>/scheduled-tasks.json` | per workspace |
| Prompt | `~/.claude/scheduled-tasks/<id>/SKILL.md` | all workspaces |

The [official docs](https://code.claude.com/docs/en/desktop-scheduled-tasks) confirm the prompt file
and say schedule, folder, model and enabled state are not in it. They do not mention workspaces.

## When they fire

- Only for the workspace the app is **currently showing**
  ([#95272](https://github.com/anthropics/claude-code/issues/95272)).
- Only while the app is open and the computer is awake.

So a task that lives in the old workspace never fires while you work in the new one.

## Recreate them

```bash
python3 tools/ccrecover.py tasks --from <old>
```

It prints each task's schedule, on/off state, prompt path and whether the prompt file still exists.

Then, in the new workspace, create each task again with the same schedule and prompt. In the app, or
ask Claude inside a Code session: the desktop app gives Claude a tool to create a scheduled task.
Paste the schedule and the prompt path.

Checks:

- Skip one-off tasks that already ran.
- If you replaced a task with a cron or launchd job while it was broken, keep only one of the two, or
  they will both run.
- Each run of a scheduled task creates its own session. `ccrecover.py plan` skips those when
  importing sessions unless you pass `--include-task-runs`.

[claude-transplant](https://github.com/vitaliyhayda/claude-transplant) can also move scheduled-task
registries between workspace folders.

In the case study the old workspace had 6 tasks. 2 were finished one-offs. 4 were recreated with the
same schedule.
