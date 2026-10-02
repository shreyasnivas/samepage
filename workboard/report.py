#!/usr/bin/env python3
"""Publish this worktree's full Workboard report through samepage WIP."""

import argparse
import fcntl
import json
import re
import sys

from board_data import ACTIVITY_STATES, BLOCK, reports_in, stamp, validate
from common import PACKAGE_BIN, branch_wip, project_paths


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", default=".", help="Current project checkout or worktree")
    parser.add_argument("--session", required=True)
    parser.add_argument("--label", required=True)
    parser.add_argument("--items", required=True, help="JSON array file, or - for standard input")
    parser.add_argument("--coordinator", action="store_true")
    parser.add_argument("--closed", action="store_true")
    parser.add_argument("--activity", choices=sorted(ACTIVITY_STATES))
    parser.add_argument("--activity-note", default="")
    args = parser.parse_args(argv)
    if args.activity_note and not args.activity:
        parser.error("--activity-note requires --activity")
    cwd, brain = project_paths(args.project)
    if not brain.is_dir():
        parser.error("Run samepage init for this project first")
    if args.items == "-":
        source = sys.stdin.read(1_000_001)
    else:
        with open(args.items, encoding="utf-8") as stream:
            source = stream.read(1_000_001)
    if len(source) > 1_000_000:
        parser.error("Report is too large")
    try:
        report = validate({
            "session": args.session, "label": args.label, "updated_at": stamp(),
            "items": json.loads(source), "coordinator": args.coordinator, "closed": args.closed,
            **({"activity": {"state": args.activity, "note": args.activity_note}} if args.activity else {}),
        })
    except (ValueError, TypeError) as error:
        parser.error(str(error))

    runtime = brain / "workboard"
    runtime.mkdir(mode=0o700, exist_ok=True)
    path = branch_wip(cwd, brain)
    with (runtime / "report.lock").open("a+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if path.is_symlink():
            parser.error("Refusing a symlinked WIP file")
        raw = path.read_text(encoding="utf-8") if path.exists() else ""
        try:
            existing = reports_in(raw)
        except (ValueError, TypeError) as error:
            parser.error("Repair the existing Workboard block first: " + str(error))
        if any(previous["session"] != report["session"] for previous in existing):
            parser.error("This branch already has another session's Workboard report")
        # samepage owns the WIP file. Supply its ordinary prose plus one fresh
        # block, so even a normal WIP edit can preserve that block afterward.
        prose = re.sub(
            r"\A# in flight:[^\n]*\n\n- updated[^\n]*\n\n- head:[^\n]*\n\n",
            "", raw, count=1,
        )
        prose = BLOCK.sub("", prose).strip()
        body = (prose + "\n\n" if prose else "") + "```workboard\n" + json.dumps(
            report, ensure_ascii=False, indent=2,
        ) + "\n```"
        import subprocess
        subprocess.run([str(PACKAGE_BIN), "wip", body], cwd=cwd, check=True)
    print("Reported " + str(len(report["items"])) + " items for " + report["session"])


if __name__ == "__main__":
    main()
