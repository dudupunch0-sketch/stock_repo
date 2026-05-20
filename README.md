# stock-agents

`stock-agents` is a TradingAgents-inspired CLI that uses file-handoff task packages instead of direct LLM API calls.

It collects deterministic fact artifacts, renders role-specific task prompts, runs an external runner (`mock`, `hermes`, or `codex`), validates JSON outputs with Pydantic schemas, performs one bounded repair attempt, checkpoints the run, and renders a final markdown report.

This project is research assistance only, not financial advice. No claim is guaranteed; verify data independently.

## Current status

Implemented:

- Python package bootstrap and Typer CLI.
- Pydantic schemas for facts, task packages, role outputs, and checkpoint state.
- Safe run-directory path construction.
- Deterministic `MockRunner` for local tests without network, Hermes, Codex, or API keys.
- Hermes CLI runner with provider/model/executable options.
- Codex CLI runner with executable/model/reasoning-effort options and per-run logs under `logs/codex/`.
- Shallow full pipeline:
  - market analyst
  - news analyst
  - bull researcher
  - bear researcher
  - research manager
  - trader
  - aggressive risk analyst
  - conservative risk analyst
  - neutral risk analyst
  - portfolio manager
- JSON extraction, schema validation, canonical output files, and bounded repair.
- `validate`, `show-run`, and `resume` artifact commands.
- Final report rendering with a financial-advice disclaimer.

Known limitations:

- Only `--depth shallow` is implemented.
- Codex requires a working local `codex exec` login; `codex login status` alone is not enough. Use `stock-agents doctor --smoke-runner codex` to verify it.
- Resume continues from checkpointed role outputs, but does not yet rebuild missing/corrupt fact inputs.
- Market OHLCV uses `yfinance` when available, then falls back to deterministic offline fixture bars.
- News, fundamentals, and sentiment providers are placeholders in the local collector.

## Install

From the repository root:

```bash
python -m pip install -e .
```

## Check the environment

```bash
stock-agents doctor
stock-agents doctor --smoke-runner hermes
stock-agents doctor --smoke-runner codex
```

`OPENAI_API_KEY` is not required for the Hermes/Codex CLI path. Hermes auth is handled by the local Hermes Agent installation; Codex auth is handled by the local Codex CLI login.

## Run a local mock analysis

This path is deterministic and does not require network or model access:

```bash
stock-agents analyze SPY \
  --date 2026-01-15 \
  --runner mock \
  --language Korean \
  --depth shallow
```

The command prints:

1. the run directory
2. the final report path

Example layout:

```text
runs/SPY/2026-01-15/<run_id>/
  inputs/
  tasks/
  outputs/
  repairs/
  reports/final_report.md
  checkpoints/state.json
  manifest.json
```

## Run with Hermes

```bash
stock-agents analyze SPY \
  --date 2026-01-15 \
  --runner hermes \
  --provider openai-codex \
  --model gpt-5.5 \
  --timeout-seconds 240 \
  --language Korean \
  --depth shallow
```

On this machine, a real Hermes shallow run has completed successfully. Because this path spends live model calls, prefer `--runner mock` for routine regression checks.

## Run with Codex

First verify that `codex exec` works, not only that the CLI reports logged in:

```bash
stock-agents doctor --smoke-runner codex
```

Then run a shallow analysis:

```bash
stock-agents analyze SPY \
  --date 2026-01-15 \
  --runner codex \
  --model gpt-5.5 \
  --reasoning-effort medium \
  --timeout-seconds 240 \
  --language Korean \
  --depth shallow
```

Codex event streams, stderr, and final-message captures are stored under each run directory's `logs/codex/` folder.

## Build or run one task

Render a task package:

```bash
stock-agents build-tasks SPY \
  --date 2026-01-15 \
  --role market_analyst \
  --language Korean
```

Run an existing task package:

```bash
stock-agents run-task runs/SPY/2026-01-15/<run_id>/tasks/01_market_analyst.task.md \
  --runner hermes \
  --provider openai-codex \
  --model gpt-5.5 \
  --timeout-seconds 240
```

## Validate and inspect artifacts

Validate raw runner output and print canonical JSON:

```bash
stock-agents validate \
  runs/SPY/2026-01-15/<run_id>/outputs/10_portfolio_manager.attempt0.raw.txt \
  --role portfolio_manager
```

Validate and write canonical JSON to a file:

```bash
stock-agents validate \
  runs/SPY/2026-01-15/<run_id>/outputs/10_portfolio_manager.attempt0.raw.txt \
  --role portfolio_manager \
  --output /tmp/portfolio_manager.validated.json
```

Summarize a run:

```bash
stock-agents show-run runs/SPY/2026-01-15/<run_id>
```

Resume an interrupted shallow run from its checkpoint:

```bash
stock-agents resume runs/SPY/2026-01-15/<run_id> \
  --runner mock \
  --language Korean
```

## Tests

```bash
python -m pytest -q
```
