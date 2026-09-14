# Issue tracker: Local Markdown

Issues and specs for Chapter 13 live as Markdown files under `chapter13/.scratch/`.

## Conventions

- One feature per directory: `chapter13/.scratch/<feature-slug>/`
- The spec is `chapter13/.scratch/<feature-slug>/spec.md`
- Implementation issues are one file per ticket at `chapter13/.scratch/<feature-slug>/issues/<NN>-<slug>.md`, numbered from `01`; never use a single combined tickets file
- Triage state is recorded as a `Status:` line near the top of each issue file; see `triage-labels.md`
- Comments and conversation history are appended under a `## Comments` heading

## When a skill says "publish to the issue tracker"

Create a file under `chapter13/.scratch/<feature-slug>/`, creating the directory when needed.

## When a skill says "fetch the relevant ticket"

Read the referenced file. The user will normally provide its path or issue number.

## Wayfinding operations

Used by `/wayfinder`. A map has one child file per ticket.

- Map: `chapter13/.scratch/<effort>/map.md`
- Child ticket: `chapter13/.scratch/<effort>/issues/NN-<slug>.md`, numbered from `01`
- Ticket metadata: `Type:` records `research`, `prototype`, `grilling`, or `task`; `Status:` records `claimed` or `resolved`
- Blocking: `Blocked by: NN, NN`; a ticket is unblocked after every listed ticket is `resolved`
- Frontier: scan the effort's `issues/` directory for open, unblocked, unclaimed tickets; lowest number wins
- Claim: set `Status: claimed` before starting work
- Resolve: append the answer under `## Answer`, set `Status: resolved`, then append a summary and link to the map's decisions-so-far
