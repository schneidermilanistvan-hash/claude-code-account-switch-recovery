#!/usr/bin/env python3
"""ccrecover - recover Claude Code desktop sessions, sidebar folders, scheduled
tasks and published artifacts after moving between accounts/workspaces.

Standard library only, Python 3.9+.  Everything is READ-ONLY except:
  * `plan`    writes the id list you ask for (--out),
  * `rebuild-file --out` writes the rebuilt file,
  * `import --apply` asks the desktop app to import sessions via its
    claude://resume deep link (macOS; opt-in, dry-run by default).

Layout it understands (macOS, verified; other OSes: use --store / --projects):
  <store>/<accountUuid>/<orgUuid>/local_<id>.json   one file per sidebar session
  <store>/<accountUuid>/<orgUuid>/scheduled-tasks.json
  <store>/../claude_desktop_config.json             sidebar folders
  <projects>/<cwd-slug>/<cliSessionId>.jsonl        the actual transcripts
See README.md for the full story.
"""
import argparse
import datetime
import glob
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

UUID_RE = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")
RAM_PER_SESSION_MB = 330
IDLE_MINUTES = 30


# ----------------------------------------------------------------- locations
def default_store():
    home = Path.home()
    if sys.platform == "darwin":
        return home / "Library" / "Application Support" / "Claude" / "claude-code-sessions"
    if sys.platform.startswith("win"):  # untested
        return Path(os.environ.get("APPDATA", str(home / "AppData" / "Roaming"))) / "Claude" / "claude-code-sessions"
    return home / ".config" / "Claude" / "claude-code-sessions"  # untested


def default_projects():
    base = os.environ.get("CLAUDE_CONFIG_DIR")
    return (Path(base) if base else Path.home() / ".claude") / "projects"


def claude_home(projects):
    return Path(projects).parent


def get_store(args):
    return Path(args.store).expanduser() if getattr(args, "store", None) else default_store()


def get_projects(args):
    return Path(args.projects).expanduser() if getattr(args, "projects", None) else default_projects()


def load_json(path, default=None):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def desktop_config(store):
    return load_json(Path(store).parent / "claude_desktop_config.json", {}) or {}


def folder_scopes(store, ws_key):
    cfg = desktop_config(store)
    try:
        return cfg["preferences"]["epitaxyPrefs"]["dframe-group-scopes"].get(ws_key) or {}
    except (KeyError, TypeError, AttributeError):
        return {}


def list_workspaces(store):
    out = []
    store = Path(store)
    if not store.is_dir():
        return out
    for a in sorted(p for p in store.iterdir() if p.is_dir()):
        for w in sorted(p for p in a.iterdir() if p.is_dir()):
            out.append((a.name, w.name, w))
    return out


def resolve_ws(store, spec):
    """'<account>/<workspace>' with unique prefixes allowed -> (key, path)."""
    if "/" not in spec:
        die("workspace must be <account>/<workspace> (prefixes ok); run `scan` to list them")
    a, w = spec.split("/", 1)
    hits = [(x, y, p) for x, y, p in list_workspaces(store) if x.startswith(a) and y.startswith(w)]
    if len(hits) == 1:
        return "%s/%s" % (hits[0][0], hits[0][1]), hits[0][2]
    if not hits:
        die("no workspace folder matches %r under %s" % (spec, store))
    die("ambiguous workspace %r: %s" % (spec, ", ".join("%s/%s" % (x, y) for x, y, _ in hits)))


def die(msg, code=2):
    print("error: " + msg, file=sys.stderr)
    sys.exit(code)


def fmt_ms(ms):
    try:
        return datetime.datetime.fromtimestamp(ms / 1000.0).strftime("%Y-%m-%d %H:%M")
    except (TypeError, ValueError, OSError):
        return "?"


# ----------------------------------------------------------------- sessions
def conv_id(rec):
    """The id of the conversation transcript: cliSessionId, else the last prior one."""
    cid = rec.get("cliSessionId")
    if cid:
        return cid
    prior = rec.get("priorCliSessionIds") or []
    return prior[-1] if prior else None


def transcript_index(projects):
    idx = {}
    for p in glob.glob(os.path.join(str(projects), "*", "*.jsonl")):
        idx[Path(p).stem] = p
    return idx


def load_sessions(wpath):
    out = []
    for p in sorted(Path(wpath).glob("local_*.json")):
        d = load_json(p)
        if isinstance(d, dict):
            d["_file"] = p.name
            out.append(d)
    return out


def folder_of(scopes, local_id):
    groups = {g.get("id"): g.get("name") for g in (scopes.get("groups") or [])}
    gid = (scopes.get("assignments") or {}).get("code:" + local_id)
    return groups.get(gid) if gid else None


# --------------------------------------------------------------------- scan
def cmd_scan(args):
    store, projects = get_store(args), get_projects(args)
    wss = list_workspaces(store)
    if not wss:
        die("no workspaces found under %s (use --store)" % store)
    tidx = transcript_index(projects)
    rows = []
    for a, w, p in wss:
        sess = load_sessions(p)
        with_t = sum(1 for s in sess if conv_id(s) in tidx)
        no_cli_prior = [s for s in sess if not s.get("cliSessionId") and s.get("priorCliSessionIds")]
        tasks = (load_json(p / "scheduled-tasks.json", {}) or {}).get("scheduledTasks", [])
        rows.append({
            "workspace": "%s/%s" % (a, w), "sessions": len(sess), "with_transcript": with_t,
            "archived": sum(1 for s in sess if s.get("isArchived")),
            "deleted_markers": len(list(p.glob("deleted_*"))),
            "scheduled_tasks": len(tasks),
            "empty_cli_but_prior_ids": len(no_cli_prior),
        })
    if args.json:
        print(json.dumps(rows, indent=2))
        return
    print("store: %s\nprojects: %s (%d transcripts indexed)\n" % (store, projects, len(tidx)))
    for r in rows:
        print(r["workspace"])
        print("  sessions %d | transcript on disk %d | archived %d | deleted markers %d | scheduled tasks %d"
              % (r["sessions"], r["with_transcript"], r["archived"], r["deleted_markers"], r["scheduled_tasks"]))
        if r["empty_cli_but_prior_ids"]:
            print("  note: %d session(s) have no cliSessionId but priorCliSessionIds (was /clear-ed); "
                  "the conversation is under the prior id - ccrecover uses it automatically"
                  % r["empty_cli_but_prior_ids"])
        missing = r["sessions"] - r["with_transcript"]
        if missing:
            print("  warning: %d session(s) have NO transcript on disk (cleaned up or on another machine)" % missing)


# ----------------------------------------------------------------- sessions
def session_rows(store, projects, ws_spec):
    key, wpath = resolve_ws(store, ws_spec)
    scopes = folder_scopes(store, key)
    tidx = transcript_index(projects)
    rows = []
    for s in load_sessions(wpath):
        cid = conv_id(s)
        rows.append({
            "local": Path(s["_file"]).stem,
            "lastActivityAt": s.get("lastActivityAt") or 0,
            "date": fmt_ms(s.get("lastActivityAt")),
            "title": s.get("title") or "",
            "conversationId": cid,
            "viaPriorId": bool(cid and not s.get("cliSessionId")),
            "transcript": bool(cid and cid in tidx),
            "folder": folder_of(scopes, Path(s["_file"]).stem),
            "archived": bool(s.get("isArchived")),
            "scheduledTaskId": s.get("scheduledTaskId"),
        })
    rows.sort(key=lambda r: r["lastActivityAt"], reverse=True)
    return key, wpath, rows


def cmd_sessions(args):
    key, _, rows = session_rows(get_store(args), get_projects(args), args.from_ws)
    if args.limit:
        rows = rows[: args.limit]
    if args.json:
        print(json.dumps(rows, indent=2, ensure_ascii=False))
        return
    for r in rows:
        print("%s | %s | %s | %s | %s%s"
              % (r["date"], r["title"][:60], r["conversationId"] or "-",
                 "transcript" if r["transcript"] else "NO-TRANSCRIPT", r["folder"] or "(loose)",
                 " | prior-id" if r["viaPriorId"] else ""))
    print("-- %d shown from %s" % (len(rows), key), file=sys.stderr)


# --------------------------------------------------------------------- plan
def target_known_ids(tpath):
    known = set()
    for s in load_sessions(tpath):
        for k in (s.get("cliSessionId"),) + tuple(s.get("priorCliSessionIds") or []):
            if k:
                known.add(k)
        known.add(Path(s["_file"]).stem[len("local_"):])
    return known


def cmd_plan(args):
    store, projects = get_store(args), get_projects(args)
    _, _, rows = session_rows(store, projects, args.from_ws)
    _, tpath = resolve_ws(store, args.to)
    known = target_known_ids(tpath)
    stat = {"in_source": len(rows), "archived_skipped": 0, "no_transcript": 0, "task_run": 0, "already_in_target": 0, "not_selected": 0}
    chosen = []
    loose_taken = 0
    for r in rows:  # newest first
        if r["archived"] and not args.include_archived:
            stat["archived_skipped"] += 1
            continue
        if not r["transcript"]:
            stat["no_transcript"] += 1
            continue
        if r["scheduledTaskId"] and not args.include_task_runs:
            stat["task_run"] += 1  # runs of scheduled tasks; usually not wanted in the sidebar
            continue
        take = args.all or (args.folders and r["folder"])
        if not take and args.recent and not r["folder"] and loose_taken < args.recent:
            take = True  # the N most recent loose sessions of the SOURCE, whether or not already imported
            loose_taken += 1
        if not take:
            stat["not_selected"] += 1
        elif r["conversationId"] in known:
            stat["already_in_target"] += 1
        else:
            chosen.append(r)
    if not (args.all or args.folders or args.recent):
        die("choose what to import: --all, --folders and/or --recent N")
    chosen.sort(key=lambda r: r["lastActivityAt"])  # oldest first -> newest ends on top
    out = Path(args.out)
    out.write_text("".join(r["conversationId"] + "\n" for r in chosen), encoding="utf-8")
    n = len(chosen)
    print("selected %d sessions -> %s (oldest first)" % (n, out))
    print("skipped: %s" % ", ".join("%s=%d" % kv for kv in stat.items() if kv[0] != "in_source" and kv[1]))
    print("RAM: each import prewarms a background Claude Code process (~%d MB, idle timeout %d min)."
          % (RAM_PER_SESSION_MB, IDLE_MINUTES))
    print("     all %d at once: up to ~%.1f GB; in batches of %d: ~%.1f GB at a time (pause between batches)."
          % (n, n * RAM_PER_SESSION_MB / 1024.0, args.batch, min(n, args.batch) * RAM_PER_SESSION_MB / 1024.0))


# ------------------------------------------------------------------- import
def resume_url(cid):
    return "claude://resume?session=%s" % cid


def cmd_import(args):
    store = get_store(args)
    key, tpath = resolve_ws(store, args.to)  # exits with an error if the target folder does not exist
    ids = []
    for line in Path(args.ids_file).read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        if not UUID_RE.match(line):
            die("not a UUID in %s: %r" % (args.ids_file, line))
        ids.append(line)
    if args.apply and not Path(tpath).is_dir():
        die("target workspace folder does not exist: %s" % tpath)
    known = target_known_ids(tpath) if Path(tpath).is_dir() else set()
    todo = [i for i in ids if i not in known]
    print("%s: %d ids, %d already present in %s, %d to import"
          % ("APPLY" if args.apply else "DRY-RUN", len(ids), len(ids) - len(todo), key, len(todo)))
    if not args.apply:
        for i in todo:
            print("  would run: %s" % open_command(i, show=True))
        for i in ids:
            if i in known:
                print("  skip (already present): %s" % i)
        print("dry-run: nothing opened. Add --apply to run it. The app must be showing workspace %s." % key)
        return
    print("The desktop app must be SHOWING workspace %s, otherwise the file appears in another folder and every id FAILs." % key)
    ok = fail = 0
    for n0 in range(0, len(todo), args.batch):
        batch = todo[n0:n0 + args.batch]
        for cid in batch:
            run_open(cid)
            target = Path(tpath) / ("local_%s.json" % cid)
            t0 = time.time()
            while time.time() - t0 < args.timeout and not target.exists():
                time.sleep(0.5)
            if target.exists():
                ok += 1
                print("  OK   %s" % cid)
            else:
                fail += 1
                print("  FAIL %s (no %s after %ds)" % (cid, target.name, args.timeout))
        if n0 + args.batch < len(todo):
            print("  -- batch done, pausing %ds (each import keeps a ~%d MB process for %d min) --"
                  % (args.pause, RAM_PER_SESSION_MB, IDLE_MINUTES))
            time.sleep(args.pause)
    print("done: %d OK, %d FAIL" % (ok, fail))
    sys.exit(1 if fail else 0)


def open_command(cid, show=False):
    url = resume_url(cid)
    if sys.platform == "darwin":
        return 'open "%s"' % url
    if sys.platform.startswith("win"):
        return 'start "" "%s"' % url
    return 'xdg-open "%s"' % url


def run_open(cid):
    # The only place a deep link is ever opened. UUID was validated by the caller.
    url = resume_url(cid)
    if sys.platform == "darwin":
        subprocess.run(["open", url], check=False)
    elif sys.platform.startswith("win"):
        print("    run this yourself (not executed automatically on Windows): " + open_command(cid))
    else:
        print("    run this yourself (untested on Linux): " + open_command(cid))


# ------------------------------------------------------------------ folders
def cmd_folders(args):
    store, projects = get_store(args), get_projects(args)
    key, wpath = resolve_ws(store, args.from_ws)
    scopes = folder_scopes(store, key)
    if not scopes:
        die("no sidebar folders stored for %s in claude_desktop_config.json" % key, 1)
    sess = {Path(s["_file"]).stem: s for s in load_sessions(wpath)}
    to_local = {}
    if args.to:
        _, tpath = resolve_ws(store, args.to)
        for s in load_sessions(tpath):
            for k in (s.get("cliSessionId"),) + tuple(s.get("priorCliSessionIds") or []):
                if k:
                    to_local[k] = Path(s["_file"]).stem
    groups = scopes.get("groups") or []
    order = scopes.get("order") or {}
    assign = scopes.get("assignments") or {}
    result = []
    for g in groups:
        ids = list(order.get(g["id"]) or [])
        ids += [k for k, v in assign.items() if v == g["id"] and k not in ids]
        items = []
        for k in ids:
            local = k[len("code:"):] if k.startswith("code:") else k
            s = sess.get(local)
            cid = conv_id(s) if s else None
            new_local = to_local.get(cid) if cid else None
            if not new_local and cid:
                new_local = "local_" + cid  # what the claude://resume import creates
            items.append({"old": local, "title": (s or {}).get("title", ""), "conversationId": cid,
                          "new": "code:" + new_local if new_local else None})
        result.append({"folder": g.get("name"), "sessions": items})
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return
    print("# folder layout of %s, top to bottom; 'new' = sidebar key in the imported workspace" % key)
    for g in result:
        print("\n[%s] (%d)" % (g["folder"], len(g["sessions"])))
        for it in g["sessions"]:
            print("  %s  <- %s  (%s)" % (it["new"], it["old"], it["title"][:50]))


# -------------------------------------------------------------------- tasks
def cmd_tasks(args):
    store = get_store(args)
    key, wpath = resolve_ws(store, args.from_ws)
    data = load_json(wpath / "scheduled-tasks.json", {}) or {}
    tasks = data.get("scheduledTasks", [])
    rows = []
    for t in tasks:
        fp = t.get("filePath")
        when = t.get("cronExpression") or ("once at " + fmt_ms(t["fireAt"]) if t.get("fireAt") else "?")
        rows.append({"id": t.get("id"), "enabled": bool(t.get("enabled")), "schedule": when,
                     "promptPath": fp, "promptExists": bool(fp and Path(fp).exists()),
                     "lastRunAt": t.get("lastRunAt")})
    if args.json:
        print(json.dumps(rows, indent=2))
        return
    for r in rows:
        print("%s | %s | %s | prompt %s | %s"
              % (r["id"], "enabled" if r["enabled"] else "disabled", r["schedule"],
                 "present" if r["promptExists"] else "MISSING", r["promptPath"]))
    print("-- %d task(s) in %s. Prompts are shared across workspaces; the schedule/enabled state is per workspace."
          % (len(rows), key), file=sys.stderr)


# ----------------------------------------------------------- transcript scan
def norm_path(p):
    if not isinstance(p, str):
        return p
    if p.startswith("/tmp/") or p == "/tmp":
        return "/private" + p
    if p.startswith("/var/") and sys.platform == "darwin":
        return "/private" + p
    return p


def iter_transcript(path):
    """Yield (line_index, parsed_json, raw_line) lazily; bad lines skipped."""
    with open(path, encoding="utf-8", errors="replace") as f:
        for i, line in enumerate(f):
            line = line.strip()
            if not line:
                continue
            try:
                yield i, json.loads(line), line
            except ValueError:
                continue


def result_blocks(d):
    msg = d.get("message") or {}
    content = msg.get("content")
    if isinstance(content, list):
        for b in content:
            if isinstance(b, dict) and b.get("type") == "tool_result":
                yield b


def use_blocks(d):
    msg = d.get("message") or {}
    content = msg.get("content")
    if isinstance(content, list):
        for b in content:
            if isinstance(b, dict) and b.get("type") == "tool_use":
                yield b


ART_USE_RE = re.compile(r'"name":\s*"Artifact"')


def scan_artifacts(projects, only=None):
    """Return {url: info} for every successful Artifact publish found."""
    arts = {}
    files = glob.glob(os.path.join(str(projects), "**", "*.jsonl"), recursive=True)
    for tp in files:
        pending = {}
        try:
            for i, d, raw in iter_transcript_filtered(tp):
                t = d.get("type")
                if t == "assistant":
                    for b in use_blocks(d):
                        if b.get("name") == "Artifact":
                            inp = b.get("input") or {}
                            act = inp.get("action")
                            if act in (None, "publish") and not inp.get("asset") and (inp.get("file_path") or inp.get("url")):
                                pending[b["id"]] = (i, d.get("timestamp"), inp)
                elif t == "user" and pending:
                    for b in result_blocks(d):
                        tid = b.get("tool_use_id")
                        if tid in pending:
                            idx, ts, inp = pending.pop(tid)
                            res = d.get("toolUseResult")
                            if b.get("is_error") or not isinstance(res, dict) or not res.get("url"):
                                continue
                            note(arts, res, inp, ts, tp)
        except OSError:
            continue
    return arts


def iter_transcript_filtered(path):
    """Like iter_transcript but only parses lines that can matter for artifacts."""
    with open(path, encoding="utf-8", errors="replace") as f:
        for i, line in enumerate(f):
            if ART_USE_RE.search(line) or '"tool_result"' in line:
                if '"tool_result"' in line and '"toolUseResult"' not in line:
                    continue
                try:
                    yield i, json.loads(line), line
                except ValueError:
                    continue


def note(arts, res, inp, ts, tp):
    url = res["url"]
    a = arts.setdefault(url, {"url": url, "title": None, "publishes": 0, "firstPublish": ts, "lastPublish": ts,
                              "filePath": None, "files": [], "capabilities": [], "transcript": None, "history": []})
    a["publishes"] += 1
    a["history"].append({"time": ts, "transcript": Path(tp).stem, "filePath": norm_path(inp.get("file_path") or res.get("path"))})
    if ts and (not a["lastPublish"] or ts >= a["lastPublish"]):
        a["lastPublish"] = ts
        a["filePath"] = norm_path(inp.get("file_path") or res.get("path"))
        a["transcript"] = Path(tp).stem
        a["title"] = res.get("title") or a["title"]
        f = inp.get("files")
        a["files"] = sorted(f) if isinstance(f, dict) else [x.get("path", "") if isinstance(x, dict) else str(x) for x in (f or [])]
        c = res.get("capabilities") or inp.get("capabilities")
        a["capabilities"] = sorted(c) if isinstance(c, dict) else []
    if ts and (not a["firstPublish"] or ts < a["firstPublish"]):
        a["firstPublish"] = ts
    a["title"] = a["title"] or res.get("title")


def cmd_artifacts(args):
    projects = get_projects(args)
    arts = scan_artifacts(projects)
    rows = sorted(arts.values(), key=lambda a: a["lastPublish"] or "", reverse=True)
    for a in rows:
        a["history"].sort(key=lambda h: h["time"] or "")
        a["authoringTranscript"] = a["history"][0]["transcript"] if a["history"] else None
        a["sourceOnDisk"] = bool(a["filePath"] and Path(a["filePath"]).exists())
    if args.json:
        print(json.dumps(rows, indent=2, ensure_ascii=False))
        return
    for a in rows:
        print("%s | %s | %s | %s | source %s | files=%s caps=%s | first publish in session %s"
              % (a["url"], (a["title"] or "")[:40], (a["lastPublish"] or "")[:19], a["filePath"],
                 "ON-DISK" if a["sourceOnDisk"] else "gone", len(a["files"]), ",".join(a["capabilities"]) or "-",
                 a["authoringTranscript"]))
    gone = sum(1 for a in rows if not a["sourceOnDisk"])
    print("-- %d artifact URL(s); source still on disk: %d; source gone (use rebuild-file): %d"
          % (len(rows), len(rows) - gone, gone), file=sys.stderr)
    print("-- rebuild a gone source with: rebuild-file --transcript <projects>/<slug>/<first-publish session>.jsonl --path <its file_path>"
          " (the FIRST publish's session usually holds the Write/Edit history; later ones may only re-publish)", file=sys.stderr)


# ------------------------------------------------------------- rebuild-file
def apply_edit(content, old, new, replace_all):
    """Return (new_content, status) status in ok|ambiguous|missing."""
    if old is None or content is None:
        return content, "missing"
    n = content.count(old)
    if n == 0:
        return content, "missing"
    if old == "":
        return content, "missing"
    if replace_all:
        return content.replace(old, new), "ok"
    return content.replace(old, new, 1), ("ok" if n == 1 else "ambiguous")


def collect_events(tpath, target, claude_dir):
    """Events touching `target` in transcript order."""
    tnorm = norm_path(target)
    base = os.path.basename(target)
    events, backups, pending = [], {}, {}
    sid = Path(tpath).stem
    with open(tpath, encoding="utf-8", errors="replace") as f:
        for i, line in enumerate(f):
            if base not in line and not (pending and any(pid in line for pid in pending)):
                continue  # relevant lines mention the file name, or answer a pending tool call
            try:
                d = json.loads(line)
            except ValueError:
                continue
            t = d.get("type")
            if t == "file-history-snapshot":
                for p, b in ((d.get("snapshot") or {}).get("trackedFileBackups") or {}).items():
                    if not isinstance(b, dict):
                        continue
                    # keys may be relative to the session's project folder (realParentDir)
                    full = os.path.join(b["realParentDir"], p) if (b.get("realParentDir") and not os.path.isabs(p)) else p
                    if norm_path(full) == tnorm or norm_path(p) == tnorm:
                        backups[(b.get("backupFileName"), b.get("version"))] = b
            elif t == "file-history-delta":
                if norm_path(d.get("trackingPath")) == tnorm and isinstance(d.get("backup"), dict):
                    b = d["backup"]
                    backups[(b.get("backupFileName"), b.get("version"))] = b
            elif t == "assistant":
                for b in use_blocks(d):
                    inp = b.get("input") or {}
                    name = b.get("name")
                    hit = False
                    if name in ("Write", "Edit", "MultiEdit", "NotebookEdit"):
                        hit = norm_path(inp.get("file_path")) == tnorm
                    elif name == "Artifact":
                        fm = inp.get("files")
                        vals = [v if isinstance(v, str) else (v or {}).get("from", "") if isinstance(v, dict) else ""
                                for v in (fm.values() if isinstance(fm, dict) else [])]
                        hit = norm_path(inp.get("file_path")) == tnorm or any(norm_path(v) == tnorm for v in vals)
                    elif name == "Bash":
                        hit = base in (inp.get("command") or "")
                    if hit:
                        pending[b["id"]] = {"i": i, "ts": d.get("timestamp"), "name": name, "input": inp}
            elif t == "user":
                for b in result_blocks(d):
                    ev = pending.pop(b.get("tool_use_id"), None)
                    if ev is None:
                        continue
                    ev["ok"] = not b.get("is_error")
                    ev["res"] = d.get("toolUseResult") if isinstance(d.get("toolUseResult"), dict) else {}
                    c = b.get("content")
                    ev["out"] = c if isinstance(c, str) else json.dumps(c)[:200]
                    events.append(ev)
    events.sort(key=lambda e: e["i"])
    fh = claude_dir / "file-history" / sid
    blist = []
    for b in backups.values():
        name = b.get("backupFileName")
        if not name:
            continue
        p = fh / name
        if p.exists():
            blist.append((b.get("backupTime") or "", name, p))
    blist.sort()
    return events, blist


def read_text_exact(p):
    with open(p, "rb") as f:
        return f.read().decode("utf-8", errors="replace")


def replay(events, blist, cutoff_idx, cutoff_ts, log, cutoff_time=None):
    content, base_note = None, None

    def step(ev, content):
        n = ev["name"]
        inp, res = ev["input"], ev["res"]
        if n == "Write":
            c = inp.get("content")
            if not isinstance(c, str):
                c = res.get("content")
            return (c, "ok") if isinstance(c, str) else (content, "missing")
        if n == "Edit":
            old = res.get("oldString") if isinstance(res.get("oldString"), str) else inp.get("old_string")
            new = res.get("newString") if isinstance(res.get("newString"), str) else inp.get("new_string")
            return apply_edit(content, old, new, bool(inp.get("replace_all")))
        if n == "MultiEdit":
            cur, st = content, "ok"
            for e in inp.get("edits") or []:
                cur, s = apply_edit(cur, e.get("old_string"), e.get("new_string"), bool(e.get("replace_all")))
                if s != "ok":
                    st = s
                    if s == "missing":
                        return content, "missing"
            return cur, st
        return content, "skip"

    work = [e for e in events if e["name"] in ("Write", "Edit", "MultiEdit") and e.get("ok")
            and (cutoff_idx is None or e["i"] < cutoff_idx) and (cutoff_ts is None or (e["ts"] or "") <= cutoff_ts)]
    # Start from the newest file-history backup taken at or before the cutoff. A backup is the file
    # as it was at a checkpoint, so it already contains every earlier change, including ones made by
    # shell commands that left no Write/Edit record. Only the Write/Edit calls after it are replayed.
    if blist:
        limit = cutoff_time or ""
        cands = [b for b in blist if not limit or b[0] <= limit]
        if cands:
            tb, name, p = cands[-1]
            later = [e for e in work if (e["ts"] or "") > tb]
            if not later or later[0]["name"] != "Write":  # a Write right after it would overwrite it anyway
                content = read_text_exact(p)
                work = later
                log.append((-1, tb, "backup", "started from file-history backup %s (taken %s)" % (name, tb)))
    for k, ev in enumerate(work):
        before = content
        content, st = step(ev, content)
        if st in ("ok", "ambiguous"):
            log.append((ev["i"], ev["ts"], ev["name"], "applied" + (" (old_string ambiguous; first match used)" if st == "ambiguous" else "")))
            continue
        # edit did not apply: try exact pre-edit text, then the latest file-history backup that fits
        fixed = False
        orig = ev["res"].get("originalFile")
        if ev["name"] == "Edit" and isinstance(orig, str):
            old = ev["input"].get("old_string")
            if old and old in orig:
                content, st2 = step(ev, orig)
                log.append((ev["i"], ev["ts"], ev["name"], "applied on tool-result originalFile (state before the edit)"))
                fixed = True
        if not fixed:
            old = ev["res"].get("oldString") if isinstance(ev["res"].get("oldString"), str) else ev["input"].get("old_string")
            cands = [b for b in blist if b[0] <= (ev["ts"] or "") and old and old in read_text_exact(b[2])]
            if ev["name"] == "MultiEdit":
                cands = [b for b in blist if b[0] <= (ev["ts"] or "")]
            if cands:
                tb, name, p = cands[-1]
                content = read_text_exact(p)
                for ev2 in work[:k]:  # re-apply what happened after that backup
                    if (ev2["ts"] or "") > tb:
                        content, _ = step(ev2, content)
                content, st2 = step(ev, content)
                if st2 in ("ok", "ambiguous"):
                    log.append((ev["i"], ev["ts"], ev["name"], "applied after resetting to file-history backup %s (taken %s)" % (name, tb)))
                    fixed = True
                else:
                    content = before
        if not fixed:
            log.append((ev["i"], ev["ts"], ev["name"], "FAILED: old_string not found in reconstructed text"))
    return content


def cmd_rebuild(args):
    projects = get_projects(args)
    tpath = Path(args.transcript).expanduser()
    if not tpath.is_file():
        die("transcript not found: %s" % tpath)
    if args.out and os.path.exists(args.out) and not args.force:
        die("refusing to overwrite existing %s: choose another --out, or pass --force" % args.out)
    target = args.path
    events, blist = collect_events(tpath, target, claude_home(projects))
    tnorm = norm_path(target)
    publishes = [e for e in events if e["name"] == "Artifact" and e.get("ok") and isinstance(e["res"].get("url"), str)]
    cutoff_idx = cutoff_ts = None
    if args.until:
        cutoff_ts = args.until
        label = "until %s" % args.until
    elif publishes:
        cutoff_idx = publishes[-1]["i"]
        label = "last successful publish (%s, line %d)" % ((publishes[-1]["ts"] or "")[:19], cutoff_idx)
    else:
        label = "end of transcript (no successful Artifact publish of this path found)"
    log = []
    cutoff_time = cutoff_ts or (publishes[-1]["ts"] if publishes and not args.until else None)
    content = replay(events, blist, cutoff_idx, cutoff_ts, log, cutoff_time)
    err = sys.stderr
    print("rebuild-file: %s\n  transcript %s\n  replay %s\n  file-history backups on disk for this path: %d"
          % (tnorm, tpath.name, label, len(blist)), file=err)
    for i, ts, name, msg in log:
        where = "line %d" % i if i >= 0 else "start"
        print("  %s %s %s: %s" % (where, (ts or "")[:19], name, msg), file=err)
    edits = [x for x in log if x[2] != "backup"]
    failed = sum(1 for x in edits if x[3].startswith("FAILED"))
    print("  edits applied %d, failed %d" % (len(edits) - failed, failed), file=err)
    touched = [e for e in events if e["name"] == "Bash" and (cutoff_idx is None or e["i"] < cutoff_idx)
               and (cutoff_ts is None or (e["ts"] or "") <= cutoff_ts)]
    if touched:
        print("  %d Bash command(s) mention this file; if they modified it, re-run them manually in order:" % len(touched), file=err)
        for e in touched:
            cmd = (e["input"].get("command") or "").replace("\n", " ")
            print("    line %d %s: %s" % (e["i"], (e["ts"] or "")[:19], cmd[:160]), file=err)
    if content is None:
        print("  RESULT: nothing could be reconstructed (no Write/Edit and no usable backup).", file=err)
        sys.exit(1)
    if args.out:
        with open(args.out, "w", encoding="utf-8", newline="") as f:
            f.write(content)
        print("  wrote %s (%d bytes)" % (args.out, len(content.encode("utf-8"))), file=err)
    else:
        sys.stdout.write(content)
    sys.exit(1 if failed else 0)


# --------------------------------------------------------------------- main
def build_parser():
    p = argparse.ArgumentParser(prog="ccrecover", description="Recover Claude Code desktop sessions, folders, tasks and artifacts (read-only unless stated).")
    p.add_argument("--store", help="session store dir (default: macOS Application Support/Claude/claude-code-sessions)")
    p.add_argument("--projects", help="transcripts dir (default: ~/.claude/projects)")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("scan", help="list workspaces with counts"); s.add_argument("--json", action="store_true"); s.set_defaults(fn=cmd_scan)

    s = sub.add_parser("sessions", help="sessions of one workspace, newest first")
    s.add_argument("--from", dest="from_ws", required=True, metavar="ACCOUNT/WORKSPACE")
    s.add_argument("--limit", type=int); s.add_argument("--json", action="store_true"); s.set_defaults(fn=cmd_sessions)

    s = sub.add_parser("plan", help="write ids.txt of sessions to import (oldest first)")
    s.add_argument("--from", dest="from_ws", required=True); s.add_argument("--to", required=True)
    s.add_argument("--folders", action="store_true", help="sessions that sit in a sidebar folder")
    s.add_argument("--recent", type=int, default=0, help="plus the N most recent loose sessions")
    s.add_argument("--all", action="store_true"); s.add_argument("--include-archived", action="store_true")
    s.add_argument("--include-task-runs", action="store_true", help="also plan sessions created by scheduled-task runs")
    s.add_argument("--batch", type=int, default=10); s.add_argument("--out", default="ids.txt"); s.set_defaults(fn=cmd_plan)

    s = sub.add_parser("import", help="import ids via claude://resume (DRY-RUN unless --apply)")
    s.add_argument("ids_file"); s.add_argument("--to", required=True)
    s.add_argument("--batch", type=int, default=10); s.add_argument("--pause", type=int, default=20)
    s.add_argument("--timeout", type=int, default=30); s.add_argument("--apply", action="store_true")
    s.set_defaults(fn=cmd_import)

    s = sub.add_parser("folders", help="old sidebar folders with the new session keys")
    s.add_argument("--from", dest="from_ws", required=True); s.add_argument("--to", help="map to ids that already exist in this workspace")
    s.add_argument("--json", action="store_true"); s.set_defaults(fn=cmd_folders)

    s = sub.add_parser("tasks", help="scheduled tasks of one workspace")
    s.add_argument("--from", dest="from_ws", required=True); s.add_argument("--json", action="store_true"); s.set_defaults(fn=cmd_tasks)

    s = sub.add_parser("artifacts", help="inventory every published artifact found in transcripts")
    s.add_argument("--json", action="store_true"); s.set_defaults(fn=cmd_artifacts)

    s = sub.add_parser("rebuild-file", help="rebuild a file from Write/Edit calls + file-history backups")
    s.add_argument("--transcript", required=True); s.add_argument("--path", required=True)
    s.add_argument("--until", help="ISO timestamp (default: last successful Artifact publish of the path)")
    s.add_argument("--out"); s.add_argument("--force", action="store_true", help="overwrite --out if it exists")
    s.set_defaults(fn=cmd_rebuild)
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    args.fn(args)


if __name__ == "__main__":
    main()
