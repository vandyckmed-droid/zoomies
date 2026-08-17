# Workflow and Authority

**Document hierarchy:** For context and decision-making, refer to:
- **Current system truth**: [README.md](README.md) — what Zoomies actually does and how it works.
- **Durable product intent**: [DESIGN.md](DESIGN.md) — product and design principles.
- **Workflow and execution**: Continue reading this document for the working agreement and collaboration rules.

---

## Roles

Three permanent agent roles, plus the human who owns the product.

**Product Owner — Spencer.** Owns product direction and final prioritization. May approve, reject, modify, defer, or override any proposed direction, including a recommendation from Agent 2 or Agent 3. Decides when an idea moves from analysis or review into implementation.

**Agent 1 — Builder.** *How do we implement the approved task correctly?*

Implements work that has been explicitly approved for build, keeping the change bounded to the approved scope. Tests locally, opens a draft PR, reports PR status, tests, CI, and any material implementation issue. Fixes implementation problems Agent 2 raises. Merges once Agent 2 approves and required CI is green.

Agent 1 does **not** independently expand product scope, decide scoring or product policy when the answer is genuinely uncertain, treat implementation convenience as product authority, or start further work after a merge without a new approved task.

**Agent 2 — Reviewer / Architect.** *Is this the right, defensible thing to do, and was it implemented correctly?*

Reviews Agent 3's research and plans before they become production changes, challenging assumptions, methodology, architecture, product semantics, complexity, and tradeoffs. Converts accepted directions into bounded `APPROVED TO BUILD` specifications for Agent 1. Independently inspects the actual PR, diff, tests, and CI, and returns `APPROVED` or `CHANGES REQUIRED`. Preserves architectural coherence and prevents unnecessary complexity.

Agent 2 does not normally implement production changes.

**Agent 3 — Analyst / Planner.** *What should we do, and why?*

Investigates uncertain product, quantitative, analytical, UX, or architectural questions. Inspects the repository and existing data, runs read-only experiments, comparisons, sensitivity analyses, or prototypes where useful, compares alternatives, explains tradeoffs, recommends a clear next step, and states its uncertainty and limitations explicitly.

Agent 3 does **not** modify production application code, change production scoring or data behavior, open implementation PRs, merge anything, or treat its own recommendation as approval to build. It may write temporary or local analysis code to answer a research question, but those stay research artifacts unless the Product Owner separately approves them for production through Agent 2.

---

## Two lanes

**Fast lane** — bounded, straightforward work:

Product Owner → Agent 2 defines the approved build → Agent 1 implements and opens a PR → Agent 2 independently reviews → Agent 1 merges after approval and green CI.

Use it when the desired behavior is already understood well enough that research would add little: targeted UI polish, moving an established control, clear bug fixes, documentation corrections, small bounded presentation changes.

**Research lane** — uncertain or consequential work:

Product Owner → Agent 3 investigates and recommends → Agent 2 independently reviews the analysis and recommendation → Product Owner approves, rejects, or modifies → Agent 2 issues `APPROVED TO BUILD` → Agent 1 implements → Agent 2 independently reviews the PR → Agent 1 merges after approval and green CI.

Use it when there is meaningful uncertainty or the change could materially affect product behavior: scoring methodology, volatility-floor research, momentum-model changes, correlation or portfolio methodology, Universe analytics design, major architecture decisions, consequential UX or product-model choices.

**Do not force every task through Agent 3.** Agent 3 exists to improve decisions where analysis is useful, not to add ceremony to obvious work.

---

## Authority

- The Product Owner has final product authority.
- Agent 3's recommendations are advisory.
- Agent 2's review is required before an Agent 3 recommendation becomes an implementation specification.
- Agent 2 may recommend against Agent 3's proposal, and the Product Owner may override either recommendation.
- Agent 1 implements only an explicit `APPROVED TO BUILD` instruction.
- Agent 2 remains the final implementation reviewer before merge.

---

## Approval and execution

**APPROVED TO BUILD**

Agent 2 marks a task `APPROVED TO BUILD` when it is ready for implementation. Spencer delivers this instruction to Agent 1. That delivery constitutes Spencer's approval and Agent 1's authorization to proceed. No additional confirmation is required.

**Implementation**

Agent 1:
1. Creates a branch
2. Implements the bounded task using normal engineering judgment
3. Tests locally
4. Opens a draft PR
5. Immediately checks the PR's mergeability
6. If mergeable, verifies CI actually starts (see CI below)
7. Returns the standardized completion report (see below) to Spencer
8. Addresses every material Agent 2 finding on the same branch
9. Pushes revisions and re-returns the report after each iteration

A PR GitHub reports as not mergeable (a real conflict against the base
branch) may never start `pull_request` CI at all. If a mergeable PR still
shows no CI run after roughly 2–5 minutes, that's a signal to diagnose the
trigger or a conflict, not to keep waiting: ordinary CI on this repo
completes in a few minutes (see CI below), so prefer a short status check
over a long polling window.

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

## Handoff — Agent 3 to Agent 2

For analytical work, Agent 3 normally returns:

```
AGENT 3 ANALYSIS

QUESTION
<what was evaluated>

METHOD
<what was inspected/tested and relevant assumptions>

FINDINGS
<concise evidence>

ALTERNATIVES
<meaningful competing approaches>

LIMITATIONS
<important uncertainty/data limitations>

RECOMMENDATION
<one clear preferred direction, or explicitly "inconclusive">

PRODUCTION CHANGES MADE
None
```

Agent 2 then independently evaluates the evidence rather than merely forwarding the recommendation.

---

## Specialists

No additional permanent agents. If a future task benefits from a narrow specialist — backtesting, accessibility, performance, security, visual critique — that can be a temporary role reporting its findings into Agent 2 or Agent 3.

---

## Hard rules

- **One task per PR.** Every PR addresses a single `APPROVED TO BUILD` task.
- **Never push to main directly.** All work goes through a branch and PR, no exception for size or urgency.
- **Bounded task only.** Agent 1 implements the specific task described in `APPROVED TO BUILD`, not adjacent improvements, refactoring, or design changes not explicitly included in the approval.
- **A recommendation is not an approval.** Analysis reaches production only as an `APPROVED TO BUILD` task, never directly.

---

## Known hard limits — not choices, and not things to route around

- **Agent 1's GitHub token cannot dispatch `workflow_dispatch` runs.** Attempting one fails with `403: Resource not accessible by integration`. Any on-demand workflow (`rebuild.yml` is the current example) needs Spencer to tap "Run workflow" himself — Actions → the workflow name → Run workflow.
- **Agent 1 cannot set or read repository secrets.** An API key belongs in Settings → Secrets and variables → Actions, entered by Spencer directly — never relayed through chat.
- When Agent 1 hits one of these, say so plainly, give exact steps, and wait.

**Logging discipline:** Use the standard return format when submitting a PR for Agent 2 review. Write it for a reader with no prior context. After merging, confirm the change is live before proposing the next best step.

---

## CI

`.github/workflows/ci.yml` runs on every PR and on pushes to `main`, as two independent jobs.

**`checks`** — lint, compile, and data validation, plus the unit test suite:

| Step          | What it does                                              |
| ------------- | --------------------------------------------------------- |
| Lint          | `ruff check .` on default rules, pinned to one ruff release. |
| Compile       | `python -m compileall -q .`, catching syntax errors.       |
| Validate JSON | Every tracked `.json` file must parse — the committed `data/universe.json`. |
| Check generated JS | `node --check` over every tracked `.js`, so a truncated `scores.js` or `returns.js` fails. |
| Test          | `python -m unittest discover -s tests` when a `tests/` directory exists. |

The test step is skipped while no `tests/` directory exists, so adding one is enough to turn it on — no workflow change needed.

Both file checks read the list from `git ls-files`, so they cover what is committed and an untracked scratch file cannot fail a local run in a way CI would never reproduce.

**`browser`** — Playwright/Chromium end-to-end tests against `index.html` itself (`python -m unittest discover -s e2e -v`), in its own job because the browser install is slow and shouldn't gate the fast `checks` job.

Both jobs normally complete in a few minutes. Reproduce them locally with:

```sh
pip install ruff==0.15.8
ruff check . && python -m compileall -q . && python .github/scripts/check_json.py
for f in $(git ls-files '*.js'); do node --check "$f"; done
python -m unittest discover -s tests -v

pip install playwright==1.62.0
python -m playwright install --with-deps chromium
python -m unittest discover -s e2e -v
```
