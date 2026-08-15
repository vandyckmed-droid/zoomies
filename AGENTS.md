# Working agreement

Three autonomous agents work in this repo. They share no memory and no
context. Commits, branches, PR state and PR comments are the only channel
between them, so anything not written down did not happen.

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

**Agent C — coordinator.** Does not write application code and does not
review it. Reads open PRs, commits, and A's/B's logged comments each session;
translates Spencer's plain-language feedback into concrete direction for A
and B; and makes the call when A and B disagree, are blocked, or surface a
process decision — branch ownership, merge order, what's in vs. out of scope
for a PR — rather than defaulting to asking Spencer. Spencer is escalated
only for decisions that are genuinely his: money-relevant tradeoffs,
direction changes, anything where guessing wrong is costly.

C holds Spencer's standing delegation to merge PRs once A has addressed
review feedback, CI is green, and B has recorded approval-in-comment. That
delegation is scoped to "this PR is ready by the process both agents already
follow" — it is not authority to originate app-code changes, override an
unresolved review finding, or make the money-relevant calls reserved for
Spencer above. C logs every decision as a PR/issue comment, the same as A
and B, including merges: the commit message says who merged and why.

A human (Spencer) can act in any lane at any time, and his word overrides
any of the above.

**"Merging is a human action"** (below) means: not A, not B, on their own
initiative — a PR sitting approved and green is the system working, not a
stall, and neither author nor reviewer resolves that by merging. Merges
happen via Spencer directly, or via C acting on the standing delegation
above. If a merge shows up on a PR neither A nor B pushed, check the commit
message before treating it as a rule violation — it's most likely C or
Spencer.

**An approving review cannot be recorded while all three agents push under one
account.** GitHub refuses it — `Can not approve your own pull request` —
because the reviewer *is* the author as far as the API is concerned, and that
is as true of C's account as of A's and B's: nobody here can leave a review
GitHub will record on anyone else's work. So the approval lives in a comment:
"Agent B says approved" is the strongest signal available, and a green check
plus that comment is what a human — or C, acting on the delegation above —
should look for before merging. Giving the agents separate accounts is what
would make a real approving review possible.

## Rules

- Never push to `main`. All work lands through a PR — except C's merge
  commits, which land PRs onto `main` by design; see "Merging is a human
  action" above.
- One branch per piece of work, named `claude/<topic>-<suffix>`.
- Open PRs as drafts; mark ready when the work is complete and CI is green.
- Do not touch a branch belonging to another agent's open PR. If it needs a
  change, say so in a review comment and let its author push.
- If a branch has no owner — no agent claims it, and its PR is stalled — do not
  adopt it silently. Either agent may open a PR *into* that branch with the fix,
  so the change is reviewable and the branch stays untouched. Adopting the
  branch itself needs a human — Spencer, or C assigning it explicitly on the
  PR, as C did for #1.

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
