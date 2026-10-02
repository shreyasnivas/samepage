"""Append-only founder instructions and owner acknowledgements in SHARED.md."""

from contextlib import contextmanager
import fcntl
import json
from pathlib import Path
import re
import subprocess
import uuid

from board_data import collect, reports_in, stamp
from common import PACKAGE_BIN, branch_wip, valid_session

MARKER = re.compile(r"^- \d{4}-\d\d-\d\d \([^)]*\) WORKBOARD_(REQUEST|ACK) (\{.*\})$")
STATUSES = frozenset({"saved", "queued", "received", "working", "done", "blocked"})
OWNER_ACKS = frozenset({"received", "working", "done", "blocked"})


class RequestStore:
    def __init__(self, brain, cwd):
        self.brain = Path(brain)
        self.cwd = Path(cwd)
        self.runtime = self.brain / "workboard"

    @contextmanager
    def locked(self):
        self.runtime.mkdir(mode=0o700, exist_ok=True)
        with (self.runtime / "requests.lock").open("a+") as stream:
            fcntl.flock(stream, fcntl.LOCK_EX)
            yield

    def read(self):
        requests = {}
        path = self.brain / "SHARED.md"
        if not path.exists():
            return []
        if path.is_symlink() or path.stat().st_size > 10_000_000:
            raise ValueError("The shared record is not a regular bounded file")
        for line in path.read_text(encoding="utf-8").splitlines():
            match = MARKER.match(line)
            if not match:
                continue
            try:
                payload = json.loads(match.group(2))
                key = payload["id"]
                if not isinstance(key, str):
                    continue
                if match.group(1) == "REQUEST":
                    if (key not in requests and valid_session(payload.get("owner_session"))
                            and isinstance(payload.get("message"), str)):
                        requests[key] = payload
                elif (key in requests and payload.get("owner_session") == requests[key]["owner_session"]
                      and payload.get("status") in STATUSES):
                    requests[key].update({name: payload[name] for name in ("status", "note", "updated_at") if name in payload})
            except (KeyError, TypeError, ValueError):
                continue
        return list(requests.values())

    def remember(self, kind, payload):
        command = [str(PACKAGE_BIN), "remember", "WORKBOARD_" + kind + " " + json.dumps(
            payload, ensure_ascii=False, separators=(",", ":"),
        )]
        outcome = subprocess.run(command, cwd=self.cwd, capture_output=True, text=True, timeout=20, check=False)
        if outcome.returncode:
            raise RuntimeError("Could not save the instruction to samepage")

    def create(self, payload):
        if not isinstance(payload, dict):
            raise ValueError("Send an instruction object")
        key, message, owner = payload.get("id"), payload.get("message"), payload.get("owner_session")
        try:
            if not isinstance(key, str):
                raise ValueError
            canonical = str(uuid.UUID(key))
            if key.lower() != canonical:
                raise ValueError
            key = canonical
        except ValueError as error:
            raise ValueError("Invalid request id") from error
        if not isinstance(message, str) or not message.strip() or len(message) > 4000:
            raise ValueError("Write an instruction of up to 4,000 characters")
        if not valid_session(owner):
            raise ValueError("Choose an existing session")
        task = payload.get("task_id") or None
        if task is not None and (not isinstance(task, str) or len(task) > 128):
            raise ValueError("Invalid task id")
        message = message.strip()
        with self.locked():
            for previous in self.read():
                if previous["id"] == key:
                    if (previous["message"], previous["owner_session"], previous.get("task_id")) != (message, owner, task):
                        raise ValueError("This request id already belongs to another instruction")
                    return {"request": previous, "duplicate": True}
            board = collect(self.brain)
            session = next((entry for entry in board["sessions"] if entry["id"] == owner), None)
            if session is None:
                raise ValueError("That session is no longer on Workboard")
            if task and not any(item["id"] == task and item["owner_session"] == owner for item in board["items"]):
                raise ValueError("That task is no longer pending")
            now = stamp()
            request = {"id": key, "owner_session": owner, "owner": session["label"],
                       "task_id": task, "message": message, "status": "saved",
                       "note": "Saved in samepage; the agent must pick it up.",
                       "created_at": now, "updated_at": now}
            self.remember("REQUEST", request)
            return {"request": request, "duplicate": False}

    def _caller_report_session(self):
        path = branch_wip(self.cwd, self.brain)
        if not path.is_file() or path.is_symlink():
            return None
        reports = reports_in(path.read_text(encoding="utf-8"))
        return reports[0]["session"] if len(reports) == 1 else None

    def acknowledge(self, key, session, status, note):
        if not valid_session(session) or status not in OWNER_ACKS or not isinstance(note, str) or len(note) > 2000:
            raise ValueError("Invalid acknowledgement")
        # This prevents one ordinary pane from accidentally acknowledging as
        # another. Same-user local processes remain outside this trust claim.
        if self._caller_report_session() != session:
            raise ValueError("This worktree does not report as that session")
        with self.locked():
            request = next((entry for entry in self.read() if entry["id"] == key), None)
            if not request or request["owner_session"] != session:
                raise ValueError("Only the assigned session can acknowledge this instruction")
            if request["status"] == "done" and status != "done":
                raise ValueError("A completed instruction cannot restart")
            if request["status"] == status and request.get("note") == note:
                return request
            event = {"id": key, "owner_session": session, "status": status,
                     "note": note, "updated_at": stamp()}
            self.remember("ACK", event)
            return {**request, **event}
