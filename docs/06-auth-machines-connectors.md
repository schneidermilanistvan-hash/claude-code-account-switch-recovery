# `claude -p` 403 "Your organization has disabled Claude subscription access for Claude Code", other machines, connectors

What else breaks after a workspace switch, apart from the Code sidebar.

Unofficial; not affiliated with or endorsed by Anthropic. Do not try to work around an organization's settings: if an admin disabled
something, ask the admin.

## The 403: `oauth_org_not_allowed`

```text
Your organization has disabled Claude subscription access for Claude Code · Use an Anthropic API key instead, or ask your admin to enable access
```

You see this from headless runs: `claude -p`, the Agent SDK, scripts, cron and launchd jobs. In `-p`
mode and the SDK it is the error code `oauth_org_not_allowed`.

Per the [official errors page](https://code.claude.com/docs/en/errors#your-organization-has-disabled-claude-subscription-access):

- It is a server-side setting of the organization. Local settings, environment variables and CLI
  flags cannot override it.
- Running `/login` again with the same account returns the same error.
- Fix: an admin enables Claude Code access for the organization, or you authenticate with a Console
  API key instead of the subscription.

That describes an organization that really has Claude Code switched off. After a workspace switch
there is a cheaper cause with the same message: the CLI keeps its own login token, and it can still
hold the OLD workspace's token. If that workspace's plan no longer includes Claude Code (a personal
plan that lapsed to Free), every headless run returns this 403.

In the case study (2026-10-10) a fresh `claude auth login` fixed it on both Macs. On the second Mac
`claude auth status` showed the old workspace: its token visibly still belonged there. On the first
Mac it already showed the new workspace's name, but with the old plan type (`max`), while every run
still failed. After the login `claude -p "say ok"` answered `ok` on both, also from a launchd job.
Whether anyone changed an admin setting in between is not known, so treat the login as the first
thing to try, not as proof that the setting never matters.

Steps:

1. Sign the CLI in again: `claude auth login`, pick the new workspace if the sign-in asks. Then
   re-test with `claude -p "say ok"`. Do not trust `claude auth status` or `/status` alone: the
   re-test is the proof.
2. If the 403 survives a fresh login into the right workspace, ask an Owner of that organization to
   enable Claude Code with subscription sign-in. I did not verify the exact name of that setting in
   the admin console.
3. Or set up a Console API key ([authentication docs](https://code.claude.com/docs/en/authentication)).
   API usage is billed separately from the subscription.

Then check every script and scheduled job that calls `claude -p`. They fail quietly: look at their
logs, not at the app. In the case study the desktop app's Code tab worked in the new workspace while
every headless run returned this 403, until the CLI was signed in again.

## Other machines

Each machine has its own transcripts (`~/.claude/projects`), its own session store and its own CLI
login. On each one:

1. Back up ([07-before-you-switch.md](07-before-you-switch.md)).
2. Run `ccrecover.py scan` and import what you want ([02-sessions.md](02-sessions.md)).
3. Run `/status` in the CLI. In the case study a second Mac's CLI was still signed in to the old
   workspace.
4. Search its transcripts for artifacts you cannot find elsewhere, by page title
   ([05-artifacts.md](05-artifacts.md#4-other-places-a-copy-hides)).

## Connectors

Connectors are per workspace. Reconnect each one you use in the new workspace. The official
migration also revokes connector sign-ins and does not move custom connectors
([support article 9267400](https://support.claude.com/en/articles/9267400)). An organization policy
may not allow a connector you used privately.

## The Chrome extension

The Claude in Chrome extension is signed in to one workspace. Sign it in to the workspace you use now.

## Running sessions

Switching workspace in the account menu stops every running local session mid-turn
([#89966](https://github.com/anthropics/claude-code/issues/89966)). Finish or pause work before you
switch, and do not switch during an import.
