"""Collect reported work from samepage WIP files, never a second task store."""

import csv
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from common import valid_session

BLOCK = re.compile(r"```workboard\s*\n(.*?)\n```", re.S)
STATES = frozenset({"decision", "working", "checking", "blocked", "queued", "done"})
ACTIVITY_STATES = frozenset({"working", "checking", "waiting", "blocked", "idle"})


def stamp():
    return datetime.now(timezone.utc).isoformat()


def parse_time(value):
    if not isinstance(value, str):
        raise ValueError("A timestamp is required")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError("Invalid report timestamp") from error
    if parsed.tzinfo is None:
        raise ValueError("Report timestamps need a timezone")
    return parsed


def validate(report):
    if not isinstance(report, dict):
        raise ValueError("Report must be an object")
    if not valid_session(report.get("session")):
        raise ValueError("Report needs a portable session id")
    if not isinstance(report.get("label"), str) or not report["label"].strip():
        raise ValueError("Report needs a label")
    parse_time(report.get("updated_at"))
    for key in ("coordinator", "closed"):
        if key in report and not isinstance(report[key], bool):
            raise ValueError(key + " must be boolean")
    if "activity" in report:
        activity = report["activity"]
        if (not isinstance(activity, dict) or activity.get("state") not in ACTIVITY_STATES
                or not isinstance(activity.get("note"), str)):
            raise ValueError("Activity needs a state and note")
    if not isinstance(report.get("items"), list):
        raise ValueError("Items must be an array")
    ids = set()
    for item in report["items"]:
        if not isinstance(item, dict):
            raise ValueError("Each item must be an object")
        for key in ("id", "title", "state", "summary", "next"):
            if not isinstance(item.get(key), str) or not item[key].strip():
                raise ValueError("Item needs " + key)
        if item["id"] in ids or item["state"] not in STATES:
            raise ValueError("Duplicate item id or unknown state")
        ids.add(item["id"])
        owner = item.get("owner_session", report["session"])
        if not valid_session(owner):
            raise ValueError("Invalid owner session")
        if owner != report["session"] and not report.get("coordinator"):
            raise ValueError("Only a coordinator may seed another owner")
        for key in ("owner", "detail", "decision", "url", "version", "preview_url"):
            if key in item and not isinstance(item[key], str):
                raise ValueError(key + " must be text")
        workers = item.get("workers", [])
        if not isinstance(workers, list) or any(not valid_session(worker) for worker in workers):
            raise ValueError("Invalid worker sessions")
        links = item.get("links", [])
        if not isinstance(links, list) or any(
            not isinstance(link, dict) or not isinstance(link.get("label"), str)
            or not isinstance(link.get("url"), str) for link in links
        ):
            raise ValueError("Invalid item links")
        if item["state"] == "decision" and not item.get("decision"):
            raise ValueError("A decision needs its question")
    return report


def reports_in(raw):
    if "```workboard" not in raw:
        return []
    blocks = BLOCK.findall(raw)
    if not blocks:
        raise ValueError("Incomplete workboard block")
    return [validate(json.loads(block)) for block in blocks]


def collect(brain, now=None):
    brain = Path(brain)
    now = now or datetime.now(timezone.utc)
    reports, warnings = {}, []
    wip = brain / "wip"
    for path in sorted(wip.glob("*.md")):
        try:
            if path.is_symlink() or path.stat().st_size > 1_000_000:
                raise ValueError("Unsafe or oversized report")
            for report in reports_in(path.read_text(encoding="utf-8")):
                old = reports.get(report["session"])
                if old is None or parse_time(report["updated_at"]) > parse_time(old["updated_at"]):
                    reports[report["session"]] = report
        except (OSError, UnicodeError, ValueError, TypeError):
            warnings.append("A samepage report could not be read. Its owner needs to refresh it.")

    expected = {}
    roster = brain / "roster.tsv"
    try:
        if roster.is_file() and not roster.is_symlink() and roster.stat().st_size <= 1_000_000:
            for row in csv.DictReader(roster.read_text(encoding="utf-8").splitlines(), delimiter="\t"):
                session = (row.get("surface") or "").replace(":", "")
                if valid_session(session):
                    expected[session] = ((row.get("provider") or "Session").title() + " · " + session)
    except (OSError, UnicodeError, csv.Error):
        warnings.append("The samepage session roster could not be read.")
    for report in reports.values():
        expected[report["session"]] = report["label"]
        for item in report["items"]:
            owner = item.get("owner_session", report["session"])
            expected.setdefault(owner, item.get("owner", owner))
            for worker in item.get("workers", []):
                expected.setdefault(worker, worker)

    items, seen = [], set()
    for report in sorted(reports.values(), key=lambda value: parse_time(value["updated_at"]), reverse=True):
        for original in report["items"]:
            owner = original.get("owner_session", report["session"])
            if owner != report["session"] and owner in reports:
                continue
            key = (owner, original["id"])
            if key in seen:
                continue
            seen.add(key)
            if original["state"] == "done":
                continue
            item = {name: original[name] for name in (
                "id", "title", "state", "summary", "next", "decision", "url", "detail",
                "links", "workers", "version", "preview_url",
            ) if name in original}
            item.update(owner=original.get("owner", report["label"]), owner_session=owner,
                        updated_at=report["updated_at"],
                        source="Owner report" if owner == report["session"] else "Coordinator report; owner update pending")
            items.append(item)

    sessions = []
    for session, label in expected.items():
        report = reports.get(session)
        if report and report.get("closed") and not any(item["owner_session"] == session for item in items):
            continue
        updated = report["updated_at"] if report else None
        sessions.append({"id": session, "label": report["label"] if report else label,
                         "updated_at": updated, "has_report": report is not None,
                         "activity": report.get("activity") if report else None,
                         "stale": not report or (now - parse_time(updated)).total_seconds() > 1800})
    return {"generated_at": now.isoformat(), "items": items, "sessions": sessions, "warnings": warnings}
