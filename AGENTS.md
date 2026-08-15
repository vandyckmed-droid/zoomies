# Working agreement

Autonomous agents work in this repo. They share no memory and no context.
Commits, branches, PR state and PR comments are the only channel between them,
so anything not written down did not happen.

Two lanes were designed up front — an author and a reviewer. A third, a
coordinator, was discovered by observing the repo rather than by being told,
which is the point: this file records what is *observed to be true*, and a
claim in it that the history contradicts is a bug in the file.

## Lanes

**Agent A — author.** Writes code, commits, pushes to feature branches, opens
PRs and keeps them updated. Does not review its own PRs, approve them, or merge.
Like B, A pushes only to a branch it owns.

**Agent B — reviewer.** Reviews open PRs, leaves review comments, and approves
or requests changes. Reviewing is B's default mode, not a prohibition on
writing code: B may author a fix when it is small and clearly correct. What B
does not do is push to a branch it does not own — including `main` and
Agent A's branches — without a human explicitly authorising it. B does not
merge; merging requires a human to ask for it on the PR.

**Agent C — coordinator.** Merges. Not part of the original two-lane design;
recorded here because it merged #2 and said so in the merge commit:

> Agent B reviewed twice … Agent A addressed every finding, CI green at
> `cf71448`. Both agents explicitly logged this as waiting on a human to merge.
> Merging as Agent C (coordinator) — process/tooling change only, no app code
> touched.

That is the whole evidence base. It establishes that C exists, that it merges,
and that it read both agents' status comments first; it does not establish what
else C does or what it will merge. The qualifier C gave itself — *process and
tooling only, no app code* — is C's own, and worth not generalising from.

A human can act in any lane at any time.

**Neither the author nor the reviewer merges.** The author declines to merge
its own work; the reviewer declines to merge at all without being asked. A PR
can sit approved and green for a long time. That is the system working, not a
stall, and neither A nor B should resolve it by merging.

What clears that state is a human or the coordinator. An earlier version of
this file said "merging is a human action", which the merge of #2 disproved
within the hour — both A and B had written "waiting on a human", and C merged
instead. Neither agent was wrong to wait; the file was wrong to name the only
actor who could finish it.

**An approving review cannot be recorded while the agents share one account.**
GitHub refuses it — `Can not approve your own pull request` — because the
reviewer *is* the author as far as the API is concerned. Every agent here
pushes as `vandyckmed-droid`, C included, so no agent can review another's work
in a way GitHub will record. So the approval
lives in a comment: "Agent B says approved" is the strongest signal available,
and a green check plus that comment is what a human should look for. Giving the
agents separate accounts is what would make a real approving review possible.

## Rules

- Never push to `main`. All work lands through a PR.
- One branch per piece of work, named `claude/<topic>-<suffix>`.
- Open PRs as drafts; mark ready when the work is complete and CI is green.
- Do not touch a branch belonging to another agent's open PR. If it needs a
  change, say so in a review comment and let its author push.
- If a branch has no owner — no agent claims it, and its PR is stalled — do not
  adopt it silently. Either agent may open a PR *into* that branch with the fix,
  so the change is reviewable and the branch stays untouched. Adopting the
  branch itself needs a human.

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
| Validate JSON | Every tracked `.json` file must parse — the committed `data/universe.json`. |
| Check generated JS | `node --check` over every tracked `.js`, so a truncated `scores.js` or `returns.js` fails. |
| Test          | `python -m unittest discover -s tests` when a `tests/` directory exists. |

The test step is skipped while no `tests/` directory exists, so adding one is
enough to turn it on — no workflow change needed.

Both file checks read the list from `git ls-files`, so they cover what is
committed and an untracked scratch file cannot fail a local run in a way CI
would never reproduce.

Reproduce the whole run locally with:

```sh
pip install ruff==0.15.8
ruff check . && python -m compileall -q . && python .github/scripts/check_json.py
for f in $(git ls-files '*.js'); do node --check "$f"; done
```

**Not covered:** `index.html` is 876 lines of behavioural JS that nothing here
executes, and `data/prices/*.csv` is ~6 MB that nothing here parses. A browser
test would reach the first; a CSV shape check the second.
