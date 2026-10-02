# Workboard reports and replies

Workboard reads fenced `workboard` JSON reports from the project's existing `.samepage/wip/*.md` files. It does not create a second task database. A worktree shares the main checkout's `.samepage` estate. Reports describe the owner session's unfinished work and are replaced in full when that owner reports again.

Write an array of items to a JSON file, then run from your own checkout:

```sh
samepage workboard report --session my_session --label "My session" --items /path/to/items.json --activity working --activity-note "Reviewing the draft."
```

An item requires `id`, `title`, `state`, `summary`, and `next`. States are `decision`, `working`, `checking`, `blocked`, `queued`, and `done`. A decision item also requires its actual `decision` question. Optional fields are `owner`, `owner_session`, `workers`, `detail`, `url`, `links` (`label` and `url`), `version`, and `preview_url`. A coordinator report may seed work for another owner; that owner's direct report supersedes the seed. A `done` item leaves the open board. Keep IDs stable across reports and change `version` when a review changes. A seen mark is only a browser-local reading marker, never approval.

Session IDs start with a letter and may contain letters, digits, `_`, and `-`, up to 64 characters. Reported `activity` is the owner's account of the session, not a process heartbeat. After 30 minutes without a report, Workboard marks it stale and stops claiming current activity. Preserve ordinary WIP prose: the reporter updates only the fenced Workboard block through `samepage wip`.

Start the foreground browser with `samepage workboard` from the project, or pass `--project DIR --port N`. It binds only to `127.0.0.1`. General instructions require choosing a session already on the board. Task replies go to the item's owner. Both append an instruction to `.samepage/SHARED.md` and say **saved**. This portable version has no automatic delivery. The addressed agent must read and acknowledge it:

```sh
samepage workboard request list --session my_session
samepage workboard request get --session my_session --id REQUEST_UUID
samepage workboard request ack --session my_session --id REQUEST_UUID --status received --note "Read and queued."
```

Run acknowledgements from the same worktree whose WIP report names that session. This prevents an ordinary different pane from accidentally acknowledging its neighbour's work. It is a local same-user safeguard, not authentication against another process under the same operating-system account. Requests are UUID-idempotent; retry a save with the same UUID after an uncertain response. A conflicting payload with that UUID is refused. No message text is executed as a shell command.

Keep reports concise and free of secrets, customer data, raw transcripts, and unpublished private artifacts. Workboard shows supplied text to any local browser that can open its loopback port.
