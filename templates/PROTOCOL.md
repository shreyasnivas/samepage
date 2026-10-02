# samepage protocol

Every coding agent in this project reads this file at session start.
The files in `.samepage/` are the shared brain. Chat history is not.

## Files

The brain lives at the MAIN checkout of this repository, and every worktree
shares it: one board, one set of notes, one log, one memory link. A pane in
`.worktrees/anything` reads and writes the same files as a pane at the root.

| Path | Role |
|---|---|
| `PROTOCOL.md` | This file. The rules. |
| `memory/` | LINK to the project's real memory estate. Read it, never write into it. |
| `SHARED.md` | Where every agent writes. Durable facts, one line each. |
| `wip/<branch>.md` | What is in flight on that branch RIGHT NOW. |
| `skills/` | LINK to the project's real skills. Read `<name>/SKILL.md`. |
| `STATUS.md` | Who is running in which pane, and on which branch. |
| `roster.tsv` | Machine registry of panes. Regenerable; never edit by hand. |
| `events.log` | Append-only log of remembers, pulses, spawns, handoffs. |
| `backups/` | What `samepage sync` replaced, timestamped. Machine-local. |
| `workboard/` | Ignored local runtime locks for the optional dashboard. Not a task store. |

**Read, do not duplicate.** `memory/` and `skills/` are symlinks to assets
this kit does not own. Two copies of a fact is two answers to one question,
and the copy nobody edits is the one that gets believed.

Do not copy these into `CLAUDE.md`, `AGENTS.md`, or a prompt. Point at them.

## Session start

1. Run `samepage`. Add `--task "<what you are about to do>"` when you know it.
   It creates the brain if this repository has none, puts your pane on the
   board, pings the other panes, and prints the digest.
2. Read the digest. If OVERLAP names a pane, tell the user which files it
   touches and ask before editing them.
3. Work. Do not ask the user to re-explain anything the digest already says.

`samepage prime` prints the digest again without pinging anyone, and
`samepage prime --full` prints the long form: this protocol's path, the memory
index, the skills list and the board.

## When a one-line message arrives asking you to run `samepage wip`

That is another pane's sonar. It went out because your note on this branch is
older than ten minutes, so nobody can tell what you are doing. Answer it by
running that one command with a one-line status, and carry on with what you
were doing. Nothing else is being asked of you: do not run `samepage prime`,
do not re-read the brain, do not reply in prose.

A pane is pinged at most once in ten minutes, whoever pings it, and only when
its note has gone stale. If the message names a project path that is not the
one you are working on, ignore it.

## When you are part-way through something

```
samepage wip "rebasing onto main; the auth test fails on line 40; next is X"
```

Write it EARLY and update it, never at the end: a session that dies of a
crash or a full context window saves nothing. This is what lets the founder
close this pane and open a different provider on the same branch, and it is
what every other pane's digest reads. Read the current one with a bare
`samepage wip`.

## Optional Workboard

`samepage workboard` serves the project's existing WIP and SHARED records on
127.0.0.1 in the foreground. `samepage workboard report` writes a structured
report through this same WIP path; ordinary `samepage wip` updates preserve the
last complete report block. See the installed kit's `workboard/REPORTING.md`
for report syntax.

Browser replies are saved in SHARED for agent pickup. They are not sent to a
running pane automatically. Use `samepage workboard request list|get --session
ID` to inspect your session's saved requests, then `samepage workboard request
ack --session ID --id UUID --status received|working|done|blocked` to record
the response. Do not claim work is delivered or done merely because the reply
was saved.

## When you learn something durable

```
samepage remember "Decision: we use X because Y"
```

One sentence, into `SHARED.md`. No secrets, tokens, or passwords.

## When you need another provider

```
samepage spawn codex --task "review the auth diff"
```

Do not open raw cmux splits unless `samepage` is missing from PATH.

## Connections follow the primary

MCP servers are declared in ONE place: the config of the harness the founder
adds them to. There is no connections file in here to author, because a second
list is a second answer to "which servers do we have".

After adding a server to your main model, run:

```
samepage sync
```

It projects every HTTP server outward to the other harnesses and prints what
each one holds. No secret value is written anywhere: the other harnesses get
the NAME of an environment variable, and your shell derives the token from the
primary config at shell start. Rotate a key in the primary config and every
harness follows, with nothing to re-sync. A bare `samepage` re-runs this only
when that declaration has actually changed.

A server that comes back Disconnected is usually waiting for a one-time OAuth
inside that harness. Open it there once. Re-running sync will not fix it.

## Handoffs

```
samepage handoff claude "Review src/auth.ts. Acceptance: tests pass."
```

The other pane is notified. They pick the work up on their next turn through `samepage`. This is shared files, not a live mind-meld: write before you expect a peer to know.

## Honesty

A peer does not see your current thought until they read these files. If the gap would hurt, `remember` or `handoff` first.
