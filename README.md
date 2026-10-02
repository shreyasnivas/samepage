# samepage

**Coding with Claude Code, Codex, and Gemini side by side is easy now.**

1. Authenticate the one coding agent you trust.
2. Run `samepage` in its pane; it creates the shared brain and puts every other agent pane on the same page.
3. Shared context, memory, skills and what each pane is working on.

<img width="1920" height="1080" alt="Screenshot 2026-09-02 at 1 03 27 AM" src="https://github.com/user-attachments/assets/f2f22424-40eb-41b4-8234-cebd676390dd" />

A tiny shared brain for [cmux](https://cmux.com) and tmux. They already give you
the panes. This gives them a brain.

## Requirements

- macOS or Linux (Windows via WSL). Any terminal; tmux or cmux optional.
- git, python3, and jq for live `cmux identify` JSON.
- One coding-agent CLI, installed and authenticated. The rest come later.

## Quick start

```bash
git clone <this-repo>
cd tools/samepage
./install.sh
```

Then, in the project you care about, start the CLI you already use (`claude`,
`codex`, `grok`, `gemini`, …) and run one command in its pane:

```bash
samepage
samepage sync
```

`samepage` creates `.samepage/` if this repository has none, installs a small
skill every harness can see, pings the agent panes you already have open for a
one-line status, and prints the digest. `sync` gives those panes your
connections: it reads the MCP servers out of the harness you already trust and
projects them onto the rest. Install, run it, sync, done.

There is nothing to run in each terminal. Every pane runs the same one command,
it is safe to run again at any time, and a settled workspace gets no messages
from it.

**The setup instructions are a prompt, not code.** If you would rather hand the
whole thing to the agent you trust, paste [prompt.md](prompt.md) into it: that
file is what tells a model how to install this, what to run, and what to do with
what comes back. A new agent CLI ships tomorrow and nothing here changes.

### The panes you already have open

A brain is files, and a running agent read its instructions when it started. Writing `.samepage/` reaches every session that begins after the write and none that began before it. That is why creating the brain can look like it did nothing: you have six panes open, the brain is live, and not one of them has heard of it.

So `samepage` also **pulses**. It finds every pane already running a coding agent on this repository, in **cmux or tmux**, and sends one line asking for a status. Only panes whose note has gone stale, at most one per branch, never the same pane twice in ten minutes, and never its own: a settled workspace gets no messages at all. Panes you open later need no help either, because they read the pointer left in `AGENTS.md`.

Finding the agent is the fiddly part, and the obvious approach does not work. A multiplexer's foreground-command field reports a node-based CLI (Claude, Codex, Gemini) as `node`, and macOS truncates `comm` to 16 characters, so a real Claude Code reads as `/opt/homebrew/bi`. samepage matches the **command line** instead: the basename of `argv[0]`, and when that turns out to be a runtime, the script one token along. If your CLI is not recognised, `adopt` says so and names what it saw, rather than claiming there were no panes.

A pane belongs if its directory is in this repository or in any worktree of it, which is decided by comparing the repository each one is in, not by comparing paths: a different repository nested inside this tree is somebody else's, and a directory inside no repository at all is refused.

Outside cmux and tmux there is nothing to type into, so an IDE terminal (VS Code, Cursor, Antigravity), a Warp tab or a second machine joins the way any pane does: run `samepage` in it once. `SAMEPAGE_TMUX_BIN` points the tmux driver at a non-default binary or server.

Nothing you sync carries a secret. The other harnesses get the NAME of an environment variable, your shell derives the token from the primary config at shell start, and the one real copy never moves. Rotate a key in the harness you trust and every other one follows.

A server name is data, never shell: anything outside letters, digits, dot, dash and underscore is refused and projected nowhere. `sync` exits non-zero if any server did not project, and says on its own line why each one did not.

## What you get

```
your-project/
├── AGENTS.md                 ← pointer, not a copy of the protocol
├── .agents/skills/samepage/  ← same skill for Claude, Codex, Grok, …
└── .samepage/
    ├── PROTOCOL.md           ← the rules (source of truth)
    ├── SHARED.md             ← durable decisions, where every agent writes
    ├── memory/               ← link to the project's real memory estate
    ├── skills/               ← link to the project's real skills
    ├── wip/<branch>.md       ← what is in flight right now
    ├── STATUS.md             ← who is in which pane
    ├── roster.tsv
    ├── events.log
    └── backups/              ← what sync replaced, before it replaced it
```

One shared layer per project: a pointer in `AGENTS.md`, one real skill with a
link from every other harness's directory, and `memory` and `skills` as symlinks
to what the project already has. No copies, no drift.

Every later session, and every new pane:

```bash
samepage
```

One command. It creates the brain if this repository has none, pings the other
agent panes for a one-line status (only the ones whose note has gone stale, and
never the same pane twice in ten minutes), and prints a digest of at most forty
lines: who is open and what each is doing, the live memory rows, the last
lessons, and OVERLAP when your task touches another pane's work.

The brain lives at the MAIN checkout, so every worktree of a repository shares
one board, one set of notes and one log.

## Commands

| Command | What it does |
|---|---|
| `samepage [--task "…"]` | The whole tool: create the brain if it is missing, ping the other panes, print the digest |
| `samepage wip "…"` | What is in flight on this branch. Write it EARLY; it is what every other pane's digest reads |
| `samepage doctor` | What is installed, what is inited, whether the links still resolve, whether this shell is inside cmux |
| `samepage init [--spawn]` | Write the brain and connect every agent pane already open on this project. A bare `samepage` does this on a first run. `--spawn` also opens a pane per missing provider |
| `samepage adopt` | Tell the panes already open that this project has a brain, across cmux and tmux |
| `samepage sync` | Project your MCP servers onto every other harness, by reference |
| `samepage prime [--full]` | The digest again, pinging nobody. `--full` is the long form: protocol, memory index, skills, board |
| `samepage remember "…"` | Append a durable lesson |
| `samepage recall foo` | Search memory |
| `samepage spawn codex --task "review the diff"` | Open one pane and launch that CLI |
| `samepage fleet` | Spawn every other detected provider |
| `samepage handoff claude "…"` | Leave work for a peer |
| `samepage status` | One-screen board |
| `samepage workboard [--port N]` | Serve the project dashboard on 127.0.0.1 in the foreground |

`--dry-run` works on the sonar itself, and on init, spawn, fleet and sync.

### Workboard

Run `samepage workboard` from a project directory, or pass `--project DIR`.
The default port is 3113. The dashboard reads the same main-checkout
`.samepage/wip/` and `SHARED.md` that every worktree uses. It shows reports,
activity, decisions and saved replies without starting another service or
opening agent panes. Stop the foreground command to stop serving it.

An agent writes a structured report with `samepage workboard report --session ID
--label TEXT --items FILE`, or uses `--items -` to read standard input. See
[REPORTING.md](workboard/REPORTING.md) for the report format and options. A
later ordinary `samepage wip "…"` keeps that completed report block alongside
the updated prose.

Browser replies are **saved for pickup**, not delivered to an agent
automatically. An agent can run `samepage workboard request list --session ID`,
`samepage workboard request get --session ID --id UUID`, then acknowledge a
request with `samepage workboard request ack --session ID --id UUID --status
received|working|done|blocked --note TEXT`. The session must match the report
owner. Run `samepage workboard --help` for the short command guide.

## Honesty

This is shared files, not a live mind-meld. A peer does not see your current thought until they read `.samepage/`. Write (`remember` / `handoff`) before you expect them to know.

It does not replace cmux, and it does not replace [cmux-bus](https://github.com/0xNekr/cmux-bus) (file claims, thread state) or [EGC](https://github.com/Fmarzochi/EGC) (a full cross-tool memory OS). It is the missing bootstrap: one trusted model sets up the rest, and they share a project brain.

## Glue, not a platform

- Panes and worktrees: [cmux](https://github.com/manaflow-ai/cmux),
  [claude-squad](https://github.com/smtg-ai/claude-squad),
  [amux](https://github.com/mixpeek/amux). samepage runs inside any of them.
- Maintained per-agent config sync:
  [ruler](https://github.com/intellectronica/ruler). Use it for agents samepage
  does not link natively.
- Real shared-memory servers:
  [agentmemory](https://github.com/rohitg00/agentmemory),
  [OpenViking](https://github.com/volcengine/OpenViking). Graduate when a
  markdown file is not enough.

## Caveats

- Symlinked context assumes the agent follows symlinks (the big three do).
  `doctor` flags a link that has gone dangling, and names the path it wanted.
- Memory is a markdown file with a protocol, not a database. A feature, until
  it isn't.
- A pulse is a line typed into another pane, because nothing can push into a
  running agent's context. That is why the sonar is careful about who it types
  into: only panes on this repository, only when their note has gone stale, at
  most once in ten minutes, and never its own.

## Tests

```bash
./tests/test.sh
```

No daemon. No Node. Bash, python3, jq (for live `cmux identify` JSON).

## Publishing

This tool is meant to go public. One script does it, repeatably:

```bash
./publish.sh --dry-run     # what would ship, and where
./publish.sh               # gate, copy, commit, push
```

It refuses any target that is not a checkout of the public repository, runs the
pre-publish gate on the source, copies the kit (everything but `.git/` and
`tests/`), runs the gate AGAIN on the target so the checked tree is the shipped
tree, then commits and pushes. `--to <checkout>` overrides the target, which
otherwise comes from `$SAMEPAGE_PUBLIC_CHECKOUT` and defaults to
`$HOME/CLAUDE_samepage`.

The gate underneath it can be run alone:

```bash
python3 ./tests/prepublish-check
```

It scans the whole tool surface and refuses to pass while anything personal, a
tenant identifier, or a key-shaped string is still in it. It is wired into
`./tests/test.sh`, so the suite fails if the surface is not clean.

## License

MIT
