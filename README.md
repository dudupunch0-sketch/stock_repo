# stock-agents

`stock-agents` is a TradingAgents-inspired CLI skeleton that uses file-handoff task packages instead of direct LLM API calls.

Current milestone scope:

- Python package bootstrap and Typer CLI.
- Pydantic schemas for facts, task packages, and role outputs.
- Safe run-directory path construction.
- Deterministic `MockRunner` for local tests without network, Hermes, Codex, or API keys.
- Task prompt rendering that asks external agents to return exactly one JSON object.

The real market data collector, Hermes runner, repair loop, and full analysis pipeline are planned follow-up phases.

This project is research assistance only, not financial advice. No claim is guaranteed; verify data independently.
