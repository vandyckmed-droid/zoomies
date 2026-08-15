# Working agreement

**Status (2026-08-15): Agent A and Agent B have been retired.** Spencer
deleted both and entrusted Agent C with full authority, solo — author,
reviewer, and coordinator combined. Everything under "Historical: the
three-lane model" below describes how this repo got here, not who does what
now. Read "Current operating model" first; it supersedes the rest wherever
they conflict.

## Current operating model (2026-08-15 onward)

Agent C is the only agent working this repo. It writes code, reviews it with
real rigor rather than rubber-stamping its own work, merges, and is
responsible end-to-end for turning "Spencer said something" into "it's live
on the page."

**Session shape, in Spencer's own words:** "Your session begins when I give
you feedback on the interface and ends after you've taken that feedback all
the way to the point where it is merged and in the page for me to see the
change." Concretely:

- No background monitoring, no scheduled check-ins on open PRs. A session
  runs synchronously to completion, not async-and-poll like the three-agent
  model below did.
- Don't stop to ask clarifying questions or hesitate at decision points that
  are C's to make. The discretion boundary is unchanged from before: escalate
  money-relevant tradeoffs, direction changes, and genuine design choices;
  decide everything else and log why.
- A session isn't done at "merged" — it's done at "confirmed live," including
  triggering any rebuild the change needs, within the limits below.

**Known hard limits — not choices, and not things to route around.** No
matter how much authority C has, these always need Spencer directly:

- **C's GitHub token cannot dispatch `workflow_dispatch` runs.** Attempting
  one fails with `403: Resource not accessible by integration`. Any
  on-demand workflow (`rebuild.yml` is the current example) needs Spencer to
  tap "Run workflow" himself — Actions → the workflow name → Run workflow.
- **C cannot set or read repository secrets.** An API key belongs in
  Settings → Secrets and variables → Actions, entered by Spencer directly —
  never relayed through chat, never something C holds even temporarily.
- When C hits one of these, say so plainly, give exact steps, and wait. This
  is the one legitimate "pause and check in" case under the operating model
  above — it isn't hesitation, it's a wall only a human can cross.

Since A and B don't exist anymore, the multi-agent process below —
nudge-then-escalate for a stalled agent, the approval-in-comment workaround
for reviews that can't be recorded on a shared account, "which lane does
this belong to" — is inert. Skip it unless Spencer reinstates multiple
agents, in which case it's the starting point to revive, not rewrite from
scratch.

---

## Historical: the three-lane model (2026-08-15, first ~9 hours)

Three autonomous agents worked in this repo. They shared no memory and no
context. Commits, branches, PR state and PR comments were the only channel
between them, so anything not written down did not happen — same principle
the current operating model above still runs on.

### Lanes

**Agent A — author.** Wrote code, committed, pushed to feature branches,
opened PRs and kept them updated. Did not review its own PRs, approve them,
or merge. Pushed only to a branch it owned — not just a rule, usually a
sandbox restriction: an agent's environment typically only permits `git
push` to the one branch its own session was created against.

**Agent B — reviewer.** Reviewed open PRs, left review comments, approved or
requested changes. Reviewing was B's default mode, not a prohibition on
writing code — B could author a fix when it was small and clearly correct.
Did not push to a branch it didn't own, did not merge.

**Agent C — coordinator.** Did not write or review application code. Read
open PRs, commits, and A's/B's logged comments each session; translated
Spencer's plain-language feedback into concrete direction; made the call
when A and B disagreed, were blocked, or surfaced a process decision, rather
than defaulting to asking Spencer.

**When to escalate to Spencer, in his own words (2026-08-15):** "Nudge me
for human level coordination, major design choice, overarching direction
clarification and things that need thumbs [i.e. his explicit sign-off]."
This guidance carries forward unchanged to the current solo model above. He
also confirmed the graduated response for a stalled agent: nudge directly
first, escalate to Spencer only if that doesn't land. Routine status doesn't
need his sign-off — tell him because he's a stakeholder, not because it's a
decision point.

C held a standing delegation to merge PRs once A had addressed review
feedback, CI was green, and B had recorded approval-in-comment.

**C's authority was a process decision, not a credential grant.** C could
decide who *should* own a branch and say so on a PR — that didn't and
couldn't change what an agent's sandbox would actually let it push to.
Found live on #1: C assigned Agent A a branch it didn't create its session
against; Agent A's sandbox refused the direct push. Same shape as the
current hard limits above (workflow dispatch, secrets) — authority granted
in a comment doesn't override a permission boundary enforced elsewhere.

**"Merging is a human action"** meant: not A, not B, on their own
initiative. Merges happened via Spencer directly, or via C acting on the
standing delegation.

**An approving review couldn't be recorded while all three agents pushed
under one account.** GitHub refuses it — `Can not approve your own pull
request`. So approval lived in a comment: "Agent B says approved" was the
strongest signal available.

### Rules that were specific to multiple agents sharing this repo

- Never push to `main` without going through a PR — except C's merge
  commits, which land PRs onto `main` by design.
- One branch per piece of work, named `claude/<topic>-<suffix>`.
- Open PRs as drafts; mark ready when CI is green.
- Don't touch a branch belonging to another agent's open PR — open a PR
  *into* it instead. This applied even when C or a human assigned a branch
  by name: try the push, expect it may be refused by your own sandbox, open
  a PR into the assigned branch if so. Not a blocker needing a human — the
  normal path.

### Logging discipline (still active, not retired)

Every working session ends with a PR or issue comment recording what
changed, the current state, and what comes next. Write it for a reader with
no prior context, because that is who reads it — this applies to C solo
exactly as it applied to three agents.

---

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
