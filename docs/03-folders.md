# Claude Code sidebar folders (groups) lost after switching workspace

Folders in the Code sidebar, and the order of sessions in them, are stored per workspace. They do not
follow sessions into another workspace. Switching accounts has been reported to wipe them
([#77601](https://github.com/anthropics/claude-code/issues/77601)).

Tested on macOS, desktop app build 2.31226.x, 2026-10-10. Unofficial; not affiliated with or endorsed by Anthropic. Back up first
([README Step 0](../README.md#step-0-back-up-and-stop-the-clock)).

## Where they live

`~/Library/Application Support/Claude/claude_desktop_config.json`:

```text
preferences.epitaxyPrefs["dframe-group-scopes"]["<accountUuid>/<orgUuid>"] = {
  "groups":      [ { "id": "<groupId>", "name": "<folder name>" }, ... ],
  "assignments": { "code:local_<id>": "<groupId>", ... },
  "order":       { "<groupId>": [ "code:local_<id>", ... ] }
}
```

Next to it, `dframe-code-sections` holds the sidebar sections per workspace. These key names were
observed in the config file, not documented.

## Read the old layout

```bash
python3 tools/ccrecover.py folders --from <old> --to <new>
```

It prints each old folder in order, the sessions in it, and their new sidebar keys in the target
workspace (`code:local_<cliSessionId>` for sessions imported with the resume link). Import the
sessions first ([02-sessions.md](02-sessions.md)), then do this.

Manual equivalent:

```bash
python3 - <<'EOF'
import json, os
p = os.path.expanduser("~/Library/Application Support/Claude/claude_desktop_config.json")
scopes = json.load(open(p))["preferences"]["epitaxyPrefs"]["dframe-group-scopes"]
for scope, v in scopes.items():
    print("==", scope[:8])
    for g in v.get("groups", []):
        print(g["name"], len(v.get("order", {}).get(g["id"], [])), "sessions")
EOF
```

## Recreate them

Two ways that worked:

1. **By hand** in the sidebar: create each folder, drag the sessions in.
2. **Ask Claude inside a Code session.** The desktop app gives Claude tools to create a sidebar
   folder and move sessions into it. Paste the output of `ccrecover.py folders` and ask: "Create
   these folders in this order and move these sessions into them." In the case study this recreated
   9 folders with 45 sessions in the original order.

I did not test editing `claude_desktop_config.json` by hand. If you try it, quit the app first and
keep a copy of the file.
