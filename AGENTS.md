# Working agreement

**Document routing:** For context and decision-making, refer to:
- **Current system truth**: [README.md](README.md) — what Zoomies actually does and how it works.
- **Durable product intent**: [DESIGN.md](DESIGN.md) — product and design principles.
- **Workflow and execution**: Continue reading this document for the working agreement and collaboration rules.

---

## Current operating model: continuous two-agent workflow

Two roles:

**Agent 1 — Builder and Planner.**

1. **Complete.** After every approved PR is merged, confirm the change is live.
2. **Assess.** Review the current state and identify the single best next step.
3. **Propose.** Present that next step briefly. Do not begin work yet. Spencer may route the proposal through Agent 2's preliminary review (see below) before responding.
4. **Wait.** Spencer responds one of three ways: *Approved*, *Skip*, or *Feedback*.
5. **Act.** Once approved: create a branch, implement, test, commit, push, open a **draft** PR — without pausing for routine decisions in between.
6. **Handoff.** Send Spencer the PR link and a concise summary. Do not merge.
7. **Revise.** Address every material Agent 2 finding on the *same* branch, push, and return the updated PR for re-review — do not open a new PR per round of feedback.
8. **Merge.** Only after both Agent 2 approves *and* Spencer authorizes the merge. Neither alone is sufficient.
9. **Continue.** Confirm the result is live, then return to step 2 (Assess) and propose the next best step.

**User-directed work.** Spencer may directly define or select the next feature himself, skipping Agent 1's proposal entirely. When he does this explicitly — stating the feature outright rather than reacting to a proposal Agent 1 made — that instruction is itself the authorization to proceed straight to step 5 (Act). Everything after that point is unchanged: normal engineering judgment, testing, the draft-PR workflow, and Agent 2's review all still apply.

**Agent 2 — Reviewer.** Independently reviews the PR, the surrounding code, tests, and CI. Returns *Approved* or *Changes needed*. Does not edit Agent 1's branch and does not merge. Re-reviews revisions until approved.

**Agent 2 — Preliminary review.** A separate decision layer upstream of the PR review, that runs on a *proposal*, not a diff. After Agent 1 proposes its next best step but before Spencer responds, Spencer may optionally route the proposal to Agent 2 first. When he does, Agent 2:

- Evaluates the proposal against the product as a whole, not just the proposal's own internal logic.
- Judges whether it is genuinely the best next step available right now.
- Weighs whether the current foundation should be preserved, refined, or reconsidered.
- Does not manufacture disagreement or novelty for its own sake.
- Surfaces a larger overhaul or a different direction only when it looks materially better.

Returns exactly one verdict: **Endorse**, **Refine**, or **Rethink**. Spencer then answers Agent 1 as usual — *Approved*, *Skip*, or feedback — per step 4.

This preliminary review is independent of Agent 2's technical PR review: a proposal can be endorsed here and still come back "Changes needed" once the PR exists.

**Interim mechanics:** Agent 2 does not yet have GitHub write access, so Spencer copies its review findings into the PR thread and relays Agent 1's responses back for re-review. Treat a "Verdict: Changes needed" message from Spencer as Agent 2's review being relayed, not as Spencer's own finding.

**Hard rules:**
- One task per PR.
- Never push feature work directly to `main` — every change goes through a branch and a PR, no exception for "it's small."
- Only Spencer's explicit *Approved* authorizes starting a proposed task — or his relay of a positive Agent 2 preliminary verdict. Silence, a question, or a "sounds good" that isn't literally one of those is not authorization to act.

**Known hard limits — not choices, and not things to route around:**

- **Agent 1's GitHub token cannot dispatch `workflow_dispatch` runs.** Attempting one fails with `403: Resource not accessible by integration`. Any on-demand workflow (`rebuild.yml` is the current example) needs Spencer to tap "Run workflow" himself — Actions → the workflow name → Run workflow.
- **Agent 1 cannot set or read repository secrets.** An API key belongs in Settings → Secrets and variables → Actions, entered by Spencer directly — never relayed through chat.
- When Agent 1 hits one of these, say so plainly, give exact steps, and wait.

**Logging discipline:** Every working session ends with a PR or issue comment recording what changed, the current state, and what comes next. Write it for a reader with no prior context.

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

The test step is skipped while no `tests/` directory exists, so adding one is enough to turn it on — no workflow change needed.

Both file checks read the list from `git ls-files`, so they cover what is committed and an untracked scratch file cannot fail a local run in a way CI would never reproduce.

Reproduce the whole run locally with:

```sh
pip install ruff==0.15.8
ruff check . && python -m compileall -q . && python .github/scripts/check_json.py
for f in $(git ls-files '*.js'); do node --check "$f"; done
python -m unittest discover -s tests -v
```
