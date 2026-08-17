# Bootstrap

Before working on this repository, read these root documents in order:

1. `AGENTS.md` — roles, workflow, approval rules, and execution protocol.
2. `README.md` — current system and implementation truth.
3. `DESIGN.md` — durable product and design principles.

Treat those documents as authoritative.

Do not rely on prior conversational context. Each new session starts here.

`AGENTS.md` defines three agent roles. Unless an instruction assigns you a
different one, act as Agent 1 (Builder), and implement only what a current
`APPROVED TO BUILD` instruction authorizes.

When documents conflict on specifics:
- `AGENTS.md` governs workflow and authority.
- `README.md` governs current implementation facts.
- `DESIGN.md` governs product and design intent.
- A current `APPROVED TO BUILD` instruction governs the specific task to perform.
