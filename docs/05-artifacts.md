# Recover Claude Code published artifacts after switching workspace

A published artifact belongs to the workspace that published it. After a switch you cannot open it
from the new workspace, move it, or keep its URL. You can find every artifact you ever published,
rebuild its source if the source is gone, and publish it again from the new workspace. In the case
study this recovered 51 of 51.

Tested on macOS, Claude Code 2.1.284 to 2.1.295, 2026-10-10. Unofficial; not affiliated with or endorsed by Anthropic. Back up first
([README Step 0](../README.md#step-0-back-up-and-stop-the-clock)). `artifacts.json` and rebuilt pages can contain secrets; keep them private.

## 1. Inventory: what did I publish?

Every publish is a tool call in a transcript. The toolkit pairs each call with its result:

```bash
python3 tools/ccrecover.py artifacts --json > artifacts.json
python3 tools/ccrecover.py artifacts           # table: URL, title, last publish, source, on disk
```

Each row has the URL, title, last publish, source path, whether the source still exists, declared
supporting files and capabilities, the publish history and the session of the first publish. You need
that session's transcript to rebuild.

The inventory covers all workspaces, including your own re-publishes. After the case-study recovery
it showed 99 URLs on that Mac: 47 first published before the recovery day and 52 published on it.
Use the first-publish date and session to tell old from new.

Manual equivalent (lists the calls; the URL of a first publish is only in the tool result):

```bash
python3 - <<'EOF'
import json, glob, os
for f in glob.glob(os.path.expanduser("~/.claude/projects/*/*.jsonl")):
    for line in open(f, errors="ignore"):
        if '"Artifact"' not in line:
            continue
        try:
            e = json.loads(line)
        except ValueError:
            continue
        for c in (e.get("message") or {}).get("content") or []:
            if isinstance(c, dict) and c.get("type") == "tool_use" and c.get("name") == "Artifact":
                i = c.get("input") or {}
                print(e.get("timestamp"), i.get("action", "publish"), i.get("url", ""),
                      i.get("file_path", ""), os.path.basename(f))
EOF
```

## 2. Source still on disk: publish again

Open a Code session in the new workspace and ask Claude to publish the file. For multi-file pages,
publish the same supporting files. Read the page first (step 5).

## 3. Source gone: rebuild it from the transcript

Scratchpad files under `/private/tmp` disappear. The transcript still holds every `Write` and `Edit`
Claude made, and `~/.claude/file-history` holds backups.

```bash
python3 tools/ccrecover.py rebuild-file \
  --transcript ~/.claude/projects/<cwd-slug>/<first-publish-session>.jsonl \
  --path /abs/path/as/recorded/page.html --out page.html
```

What it does:

1. Replays `Write`, `Edit` and `MultiEdit` calls on that path in transcript order, up to the last
   successful publish of the path (or `--until <ISO time>`). Calls whose result was an error are
   skipped.
2. If an edit does not apply, it takes the `originalFile` stored in that edit's tool result, or the
   newest file-history backup before the edit that contains the text, and continues.
3. It lists every `Bash` command that mentions the file. Those it cannot replay.

How the file backups work:

- `~/.claude/file-history/<sessionId>/<hash>@v<N>` is the file as it was at a checkpoint (start of a
  turn, or just before Claude first touched it), before that turn's edits. The state after the last
  edit of a session is not backed up.
- Lines of type `file-history-snapshot` in the transcript map each backup to its path, under
  `snapshot.trackedFileBackups["<path>"].backupFileName`. The path can be relative to the
  `realParentDir` field.
- So: take the newest backup, then replay the `Write` and `Edit` calls recorded after it.

When a `Bash` or Python command changed the file (a `sed`, a build script):

1. Copy the rebuilt file into a scratch folder.
2. Re-run the recorded commands in order, with paths pointed at the scratch copy.
3. Compare each command's output with the output recorded in the transcript. Same output is your
   evidence the step reproduced.

Then check the result against the original session: text Claude quoted, sizes and counts it printed,
what the user said about the page.

Measured on one Mac, against 23 pages whose source was really gone and that were recovered and
checked by hand: `rebuild-file` alone reproduced **9 byte-for-byte**; **6** differed because the
session had also changed them with shell commands (the tool lists those commands for you to re-run);
**8** produced nothing because they were assembled entirely by scripts and have no `Write`/`Edit`
history. All 23 were still recovered, by re-running the session's own commands in a sandbox and
checking each step against the output the transcript recorded. So expect to do the manual part for
pages built or changed by `Bash` or scripts.
[claude-file-recovery](https://github.com/hjtenklooster/claude-file-recovery) is another tool for
replaying transcripts into files.

## 4. Other places a copy hides

- **An earlier `read` of the artifact.** If a session ever read the published page, the full HTML is
  in that tool result.
- **Another machine.** Search its transcripts by the page **title**. The artifact id may never appear
  there.
  ```bash
  grep -rl "<page title>" ~/.claude/projects
  ```
- **Multi-file pages built by a script.** Re-run the original script on its saved input data and
  compare the numbers it prints with the recorded output.

## 5. Read before you publish again

Old pages can contain things you would not publish today. In the case study one page contained a
third party's private message; it was re-published only after the owner reviewed it, and kept
private. Also look for API keys, tokens and passwords that a page or its build data picked up.

## 6. Rewrite every link

Every re-publish is a new URL. Make a list of old URL to new URL, then search everywhere you may have
linked the old one:

```bash
grep -rIl "<old artifact id>" ~/Documents ~/.claude/scheduled-tasks ~/.claude/CLAUDE.md 2>/dev/null
```

- Copy each file before you change it and review the diff.
- Fix generated pages at their source (template, script), not in the output.
- Fix scheduled-task prompts in `~/.claude/scheduled-tasks/<id>/SKILL.md`.
- Pages that link each other: publish all, then update the links, then publish them again.

## Limits

- Only artifacts published from a Claude Code session whose transcript still exists can be found.
- File backups keep the last 100 checkpoints of a session plus each file's first backup, and age out
  with the transcripts ([docs](https://code.claude.com/docs/en/claude-directory)).
- `Edit` replay needs an exact match.
- The old URLs stay with the old workspace. Whether a workspace that dropped to Free still serves them
  is not verified.
- Anthropic's help center says publishing is not available on Team and Enterprise
  ([9267400](https://support.claude.com/en/articles/9267400)), while the
  [Claude Code artifacts docs](https://code.claude.com/docs/en/artifacts) describe sharing inside a
  Team. In the case study, publishing from Claude Code in a Team workspace worked on 2026-10-10.

## Case study

| How | Count |
|---|---|
| Source still on disk, re-published | 21 |
| Rebuilt from file-history backups + replayed edits (+ re-run `Bash` steps checked against recorded output) | 24 |
| Full HTML copy from an earlier `read` result in a transcript | 1 |
| Found in another Mac's transcripts by title | 3 |
| Multi-file page rebuilt by re-running its build script on saved input | 1 |
| Contained a third party's private message; owner reviewed, kept private | 1 |
| **Total** | **51 of 51** |
