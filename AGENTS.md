# How to Work: Collaboration and Execution

This document defines how agents and team members work together on Zoomies, including approval boundaries, review processes, and workflow conventions.

## References

For context and decision-making:

- **Current System**: See [README.md](README.md) for system architecture, data flow, features, and rebuild instructions
- **Product Intent**: See [DESIGN.md](DESIGN.md) for design principles and information hierarchy
- **Workflow**: Continue reading this document for execution rules

## Approval Boundaries

### No Review Required

Claude agents can commit and push directly without review:

- Documentation updates (README, DESIGN, AGENTS, code comments)
- Configuration file updates that don't change behavior
- Build system changes (linters, test runners, build scripts)
- CI/CD workflow improvements
- Local development tooling

### Agent 2 Review Required

All code changes must be reviewed by Agent 2 before merge:

- Feature implementations
- Algorithm or scoring formula changes
- Database schema or data model changes
- API contract changes
- Performance-critical code paths

Code changes that require review:

1. Implement the feature or fix on the feature branch
2. Open a draft PR with clear description of changes
3. Request review from Agent 2
4. Address review feedback
5. Mark as ready for merge once approved

### Human Review Required

Certain changes require human review and approval:

- Architecture decisions that affect multiple systems
- Breaking changes to existing APIs or data formats
- Major product direction changes
- Decisions affecting third-party integrations
- Security or privacy policy changes

When a change requires human review, open a PR and add the `requires-human-review` label.

## Agent 2 Review Process

Agent 2 review focuses on:

- **Correctness**: Does the code do what it claims? Are there bugs or edge cases?
- **Design**: Does it follow Zoomies design principles? Does it align with product intent?
- **Quality**: Is it maintainable? Does it reuse existing patterns?
- **Tests**: Are new code paths tested? Do tests cover important behaviors?

### Code Review Workflow

1. **Claude opens PR**: Branch includes implementation and tests
2. **Agent 2 reviews**: Examines diff, runs tests locally if needed
3. **Feedback**: Comments on specific issues or suggestions
4. **Iteration**: Claude addresses feedback and pushes commits
5. **Approval**: Agent 2 approves when ready
6. **Merge**: Claude merges approved PR

### Handling Disagreements

If Claude and Agent 2 disagree:

- **Clarification first**: Ensure both sides understand the concern
- **Document intent**: Update DESIGN.md or AGENTS.md if the decision guides future work
- **Escalate if needed**: Unresolved conflicts go to humans for final decision

## Continue Behavior

When continuing a previous task or PR:

1. **Fetch latest**: `git fetch origin` to get current state
2. **Check branch**: Verify you're on the correct feature branch
3. **Review context**: Read PR description and recent comments
4. **Assess state**: Identify what's been completed vs. what remains
5. **Resume or restart**: 
   - If PR is unmerged: Continue with changes and address feedback
   - If PR is merged: Start fresh on a new branch from main
6. **Communicate**: Update PR with status or post a comment if context changed

## Workflow Conventions

### Branching

Feature branches follow the pattern: `claude/<feature-name-<random>>`

- Use descriptive feature names
- Include random suffix to avoid collisions
- Keep branch focused on one feature or fix

### Commits

Commit messages should:

- Be clear and specific about the change
- Reference the related issue or feature if applicable
- Explain the "why", not just the "what"
- Keep commits logically grouped

Example:
```
Add return and volatility sorting to ranking display

Users can now click column headers to sort by return or volatility.
Maintains sort preference across sessions using localStorage.
```

### Pull Requests

When opening a PR:

1. Use a clear, specific title
2. Describe what changed and why
3. List any breaking changes or migration steps
4. Tag appropriate reviewers or labels
5. Use draft status for work in progress

## Making Decisions

When facing a decision:

1. **Check DESIGN.md first**: Does it address this?
2. **Check README.md**: Does it describe how this should work?
3. **Check this file**: Any relevant workflow or boundary decision?
4. **Be consistent**: Match existing patterns and conventions
5. **Document if new**: Update appropriate document if this sets a precedent

## Questions and Escalation

For questions about:

- **Product direction**: Refer to DESIGN.md, then escalate to humans if unclear
- **System behavior**: Refer to README.md
- **Workflow or approval**: Refer to AGENTS.md
- **Anything else**: Use your best judgment and document the decision for next time

When in doubt, it's better to ask than to guess.
