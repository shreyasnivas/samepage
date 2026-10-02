#!/usr/bin/env python3
"""Read and acknowledge saved Workboard instructions for your own session."""

import argparse
import json

from common import project_paths, valid_session
from requests_store import OWNER_ACKS, RequestStore


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("list", "get", "ack"))
    parser.add_argument("--project", default=".")
    parser.add_argument("--session", required=True)
    parser.add_argument("--id")
    parser.add_argument("--status", choices=sorted(OWNER_ACKS))
    parser.add_argument("--note", default="")
    args = parser.parse_args(argv)
    if not valid_session(args.session):
        parser.error("Use a valid session id")
    cwd, brain = project_paths(args.project)
    store = RequestStore(brain, cwd)
    if args.action == "list":
        value = [entry for entry in store.read() if entry["owner_session"] == args.session and entry["status"] != "done"]
    elif args.action == "get":
        if not args.id:
            parser.error("get needs --id")
        value = next((entry for entry in store.read() if entry["owner_session"] == args.session and entry["id"] == args.id), None)
        if value is None:
            parser.error("No instruction with this id belongs to that session")
    else:
        if not args.id or not args.status:
            parser.error("ack needs --id and --status")
        try:
            value = store.acknowledge(args.id, args.session, args.status, args.note)
        except ValueError as error:
            parser.error(str(error))
    print(json.dumps(value, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
