# Working agreement

Two autonomous agents work in this repo. They share no memory and no context.
Commits, branches, PR state and PR comments are the only channel between them,
so anything not written down did not happen.

## Lanes

**Agent A — author.** Writes code, commits, pushes to feature branches, opens
PRs and keeps them updated. Does not review its own PRs, approve them, or merge.

**Agent B — reviewer.** Reviews open PRs, leaves review comments, approves or
requests changes, and merges. Does not push code to Agent A's branches.

A human can act in either lane at any time.

## Rules

- Never push to `main`. All work lands through a PR.
- One branch per piece of work, named `claude/<topic>-<suffix>`.
- Open PRs as drafts; mark ready when the work is complete and CI is green.
- Do not touch a branch belonging to another agent's open PR. If it needs a
  change, say so in a review comment and let its author push.

## Before starting anything

1. List open PRs and check each one's head commit, CI status and review state.
2. Read the most recent comments on any PR you are involved in. Treat them as
   messages addressed to you.
3. Address outstanding review comments before starting new work.

## Responding to review feedback

Answer every review comment: either push a fix, or reply saying why you are not
(you disagree, or it is out of scope). Silence is not an answer. When a comment
is ambiguous, ask in a reply rather than guessing at intent.

## Logging

Every working session ends with a PR or issue comment recording what changed,
the current state, and what comes next — for example "pushed fix for X, ready
for re-review" or "blocked on Y, needs human input". Write it for a reader with
no prior context, because that is who reads it.

## CI

`.github/workflows/ci.yml` runs on every PR and on pushes to `main`:

| Step          | What it does                                              |
| ------------- | --------------------------------------------------------- |
| Lint          | `ruff check .` on default rules, pinned to one ruff release. |
| Compile       | `python -m compileall -q .`, catching syntax errors.       |
| Validate JSON | Every tracked `.json` file must parse, including the committed caches under `data/`. |
| Test          | `python -m unittest discover -s tests` when a `tests/` directory exists. |

The test step is skipped while no `tests/` directory exists, so adding one is
enough to turn it on — no workflow change needed.

Reproduce the whole run locally with:

```sh
pip install ruff==0.15.8
ruff check . && python -m compileall -q . && python .github/scripts/check_json.py
```
