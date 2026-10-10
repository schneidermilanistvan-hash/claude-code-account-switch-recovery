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

Steps:

1. Find out which workspace the CLI uses. Start `claude` and type `/status`.
2. If it is the wrong one and your login belongs to several, run `/login` and pick the right one, if
   the sign-in offers a choice.
3. If it is the right one, ask an Owner of that organization to enable Claude Code with subscription
   sign-in. I did not verify the exact name of that setting in the admin console.
4. Or set up a Console API key ([authentication docs](https://code.claude.com/docs/en/authentication)).
   API usage is billed separately from the subscription.

Then check every script and scheduled job that calls `claude -p`. They fail quietly: look at their
logs, not at the app. In the case study the desktop app's Code tab worked in the new workspace while
every headless run returned this 403.

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
