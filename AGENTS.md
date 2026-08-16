# Workflow and Authority

**Document hierarchy:** For context and decision-making, refer to:
- **Current system truth**: [README.md](README.md) — what Zoomies actually does and how it works.
- **Durable product intent**: [DESIGN.md](DESIGN.md) — product and design principles.
- **Workflow and execution**: Continue reading this document for the working agreement and collaboration rules.

---

## Two-agent workflow

**Agent 1 — Builder.** Receives an `APPROVED TO BUILD` instruction, implements the task, tests it, opens a draft PR, and returns a standardized completion report. Merges the PR once Agent 2 approval is obtained and CI passes.

**Agent 2 — Reviewer.** Independently reviews the PR's code, tests, surrounding context, and CI. Returns `APPROVED` or `CHANGES REQUIRED`. Does not edit Agent 1's branch. Re-reviews revisions until approved.

---

## Approval and execution

**APPROVED TO BUILD**

Agent 2 marks a task `APPROVED TO BUILD` when it is ready for implementation. Spencer delivers this instruction to Agent 1. That delivery constitutes Spencer's approval and Agent 1's authorization to proceed. No additional confirmation is required.

**Implementation**

Agent 1:
1. Creates a branch
2. Implements the bounded task using normal engineering judgment
3. Tests locally and verifies CI passes
4. Opens a draft PR
5. Returns the standardized completion report (see below) to Spencer
6. Addresses every material Agent 2 finding on the same branch
7. Pushes revisions and re-returns the report after each iteration

**Agent 2 review**

Agent 2 independently reviews the actual PR, tests, code, and CI. Returns `APPROVED` or `CHANGES REQUIRED`. Agent 1 revises until approved.

**Merge**

Once Agent 2 review is `APPROVED` AND required CI checks pass, Agent 1 merges automatically. No additional Spencer or Agent 2 authorization is required at merge time.

Failed CI or merge conflicts block merging until resolved. If resolving a blocker materially changes the implementation, Agent 1 returns the PR to Agent 2 for re-review before merging.

**Next work**

Merging one PR does not authorize Agent 1 to invent or choose the next feature. Agent 1 may propose a next best step to Spencer, but must not build until receiving another `APPROVED TO BUILD` instruction.

---

## Standard return format

Use this format when returning a PR for review:

```
PR #<number> READY FOR AGENT 2
- URL: <PR URL>
- Changed: <1–2 sentence summary>
- Tests: <local test result>
- CI: <green / running / failed>
- Notes: <material issue or "None">
```

---

## Hard rules

- **One task per PR.** Every PR addresses a single `APPROVED TO BUILD` task.
- **Never push to main directly.** All work goes through a branch and PR, no exception for size or urgency.
- **Bounded task only.** Agent 1 implements the specific task described in `APPROVED TO BUILD`, not adjacent improvements, refactoring, or design changes not explicitly included in the approval.

---

## Known hard limits — not choices, and not things to route around

- **Agent 1's GitHub token cannot dispatch `workflow_dispatch` runs.** Attempting one fails with `403: Resource not accessible by integration`. Any on-demand workflow (`rebuild.yml` is the current example) needs Spencer to tap "Run workflow" himself — Actions → the workflow name → Run workflow.
- **Agent 1 cannot set or read repository secrets.** An API key belongs in Settings → Secrets and variables → Actions, entered by Spencer directly — never relayed through chat.
- When Agent 1 hits one of these, say so plainly, give exact steps, and wait.

**Logging discipline:** Use the standard return format when submitting a PR for Agent 2 review. Write it for a reader with no prior context. After merging, confirm the change is live before proposing the next best step.

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
