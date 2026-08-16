# Working agreement

**Status (2026-08-16): a two-agent workflow (Builder/Planner + Reviewer) is
now the active process.** Both the solo full-authority model and the
original three-lane model are historical below — read "Current operating
model" first; it supersedes the rest wherever they conflict.

## Current operating model (2026-08-16 onward): continuous two-agent workflow

Two roles, most recently exercised on PR #12 (found two real blockers plus a
minor issue in a PR the solo model had already tested and shipped for
review):

**Agent 1 — Builder and Planner.** This is Agent C's active role now.

1. **Complete.** After every approved PR is merged, confirm the change is
   live — same "session isn't done until it's on the page" bar as before.
2. **Assess.** Review the current state and identify the single best next
   step.
3. **Propose.** Present that next step briefly. Do not begin work yet. Spencer
   may route the proposal through Agent 2's preliminary review (see below)
   before responding — treat that as part of step 4, not a signal to act.
4. **Wait.** Spencer responds one of three ways:
   - *Approved* — proceed.
   - *Skip* — do not act; propose the next-best alternative.
   - *Feedback* — refine the recommendation and propose again.
5. **Act.** Once approved: create a branch, implement, test, commit, push,
   open a **draft** PR — without pausing for routine decisions in between.
6. **Handoff.** Send Spencer the PR link and a concise summary. Do not merge.
7. **Revise.** Address every material Agent 2 finding on the *same* branch,
   push, and return the updated PR for re-review — do not open a new PR per
   round of feedback.
8. **Merge.** Only after both Agent 2 approves *and* Spencer authorizes the
   merge. Neither alone is sufficient.
9. **Continue.** Confirm the result is live, then return to step 2 (Assess)
   and propose the next best step.

**Agent 2 — Reviewer.** Independently reviews the PR, the surrounding code,
tests, and CI. Returns *Approved* or *Changes needed*. Does not edit Agent
1's branch and does not merge. Re-reviews revisions until approved.

**Agent 2 — Preliminary review (added 2026-08-16).** A separate decision
layer, upstream of the PR review above, that runs on a *proposal*, not a
diff. After Agent 1 proposes its next best step (step 3) but before Spencer
responds (step 4), Spencer may optionally route the proposal to Agent 2
first. When he does, Agent 2:

- Evaluates the proposal against the product as a whole, not just the
  proposal's own internal logic.
- Judges whether it is genuinely the best next step available right now.
- Weighs whether the current foundation should be preserved, refined, or
  reconsidered — rather than assuming the proposal's framing is the only
  frame.
- Does not manufacture disagreement or novelty for its own sake; agreeing
  the proposal is right is a valid, expected outcome, not a failure to add
  value.
- Surfaces a larger overhaul or a different direction only when it looks
  materially better, not merely different.

Returns exactly one verdict:
- **Endorse** — the proposal is the best next step.
- **Refine** — the direction is sound but should be adjusted before
  approval.
- **Rethink** — a different direction is materially stronger.

Spencer then answers Agent 1 as usual — *Approved*, *Skip*, or feedback —
per step 4. Agent 1 still does not begin implementation until that explicit
*Approved* lands; an *Endorse* from Agent 2 is input to Spencer's decision,
not itself authorization to act.

This preliminary review is independent of Agent 2's technical PR review
above: a proposal can be endorsed here and still come back "Changes needed"
once the PR exists, and skipping preliminary review on any given proposal
does not skip the PR review later.

**Interim mechanics:** Agent 2 does not yet have GitHub write access, so
Spencer copies its review findings into the PR thread and relays Agent 1's
responses back for re-review. Treat a "Verdict: Changes needed" message from
Spencer as Agent 2's review being relayed, not as Spencer's own finding —
respond to it exactly as step 7 describes.

**Hard rules:**
- One task per PR.
- Never push feature work directly to `main` — every change goes through a
  branch and a PR, no exception for "it's small."
- Only Spencer's explicit *Approved* authorizes starting a proposed task.
  Silence, a question, or a "sounds good" that isn't literally approval is
  not authorization to act — ask if genuinely unclear rather than assume.

**What still carries over from the solo model below:** the discretion
boundary for what needs escalation vs. what Agent 1 decides alone; the known
hard limits (no `workflow_dispatch` access, no repository-secrets access);
verifying claims by actually running things rather than reading code and
assuming it works (PR #12's real bugs — the `RETURNS` scoping error, the
infinite-retry loop — were both caught this way, not by review).

---

## Historical: solo full-authority model (2026-08-15 evening – 2026-08-16)

**Status at the time: Agent A and Agent B had been retired.** Spencer
deleted both and entrusted Agent C with full authority, solo — author,
reviewer, and coordinator combined, writing code, reviewing it, merging it,
and confirming it live, all in one uninterrupted session per piece of
feedback. Superseded by the two-agent workflow above once a review actually
caught real, material findings the solo process had missed.

**Session shape, in Spencer's own words:** "Your session begins when I give
you feedback on the interface and ends after you've taken that feedback all
the way to the point where it is merged and in the page for me to see the
change." Concretely: no background monitoring or scheduled PR check-ins; a
session ran synchronously to completion; don't stop to ask questions at
decision points that are C's to make, only for money-relevant tradeoffs,
direction changes, and genuine design choices.

**Known hard limits — not choices, and not things to route around. Still
true under the two-agent model above:**

- **C's GitHub token cannot dispatch `workflow_dispatch` runs.** Attempting
  one fails with `403: Resource not accessible by integration`. Any
  on-demand workflow (`rebuild.yml` is the current example) needs Spencer to
  tap "Run workflow" himself — Actions → the workflow name → Run workflow.
- **C cannot set or read repository secrets.** An API key belongs in
  Settings → Secrets and variables → Actions, entered by Spencer directly —
  never relayed through chat, never something C holds even temporarily.
- When C hits one of these, say so plainly, give exact steps, and wait.

---

## Historical: the three-lane model (2026-08-15, first ~9 hours)

Three autonomous agents worked in this repo. They shared no memory and no
context. Commits, branches, PR state and PR comments were the only channel
between them, so anything not written down did not happen — same principle
every later operating model above still runs on.

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
This guidance carries forward unchanged to every later model above. He also
confirmed the graduated response for a stalled agent: nudge directly first,
escalate to Spencer only if that doesn't land. Routine status doesn't need
his sign-off — tell him because he's a stakeholder, not because it's a
decision point.

C held a standing delegation to merge PRs once A had addressed review
feedback, CI was green, and B had recorded approval-in-comment.

**C's authority was a process decision, not a credential grant.** C could
decide who *should* own a branch and say so on a PR — that didn't and
couldn't change what an agent's sandbox would actually let it push to.
Found live on #1: C assigned Agent A a branch it didn't create its session
against; Agent A's sandbox refused the direct push. Same shape as the hard
limits above (workflow dispatch, secrets) — authority granted in a comment
doesn't override a permission boundary enforced elsewhere.

**"Merging is a human action"** meant: not A, not B, on their own
initiative. Merges happened via Spencer directly, or via C acting on the
standing delegation.

**An approving review couldn't be recorded while all three agents pushed
under one account.** GitHub refuses it — `Can not approve your own pull
request`. So approval lived in a comment: "Agent B says approved" was the
strongest signal available. Still true under the two-agent model above,
which is why Agent 2's reviews are relayed by Spencer rather than filed as
a formal GitHub review.

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
no prior context, because that is who reads it — this applies under every
operating model above, solo or two-agent.

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
