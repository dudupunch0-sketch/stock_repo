# stock-agents

`stock-agents` is a TradingAgents-inspired CLI that uses file-handoff task packages instead of direct LLM API calls.

It collects deterministic fact artifacts, renders role-specific task prompts, runs an external runner (`mock`, `hermes`, or `codex`), validates JSON outputs with Pydantic schemas, performs one bounded repair attempt, checkpoints the run, and renders a final markdown report.

This project is research assistance only, not financial advice. No claim is guaranteed. Verify data independently.

## Documentation

- `overview.html`: visual implementation overview for the current CLI, pipeline, artifacts, and limits.
- `userguide.html`: browser-friendly usage guide with copyable commands.
- `docs/architecture.md`: live implementation contract derived from the checked-in code.
- `docs/plans/2026-05-19-tradingagents-hermes-codex-port.md`: historical implementation plan with a current-status banner.

## Current status

Implemented:

- Python package bootstrap and Typer CLI.
- Pydantic schemas for facts, task packages, role outputs, and checkpoint state.
- Safe run-directory path construction for ticker, date, and run id components.
- Deterministic `MockRunner` for local tests without network, Hermes, Codex, or API keys.
- Hermes CLI runner with provider/model/executable options.
- Codex CLI runner with executable/model/reasoning-effort options and per-run logs under `logs/codex/`.
- `doctor` checks for Hermes/Codex executables and can run a local mock smoke. Hermes smoke checks command shape only. Codex smoke calls `codex exec` only when requested.
- Shallow sequential analysis pipeline with configurable analyst selection:
  - default: `market,news`
  - all analysts: `market,sentiment,news,fundamentals`
- Configurable bull/bear debate rounds with `--debate-rounds 1..3`.
- Configurable risk-team debate rounds with `--risk-rounds 1..3`.
- Role sequence for shallow runs:
  1. selected analysts
  2. bull and bear researchers, repeated when `--debate-rounds` is greater than 1
  3. research manager
  4. trader
  5. aggressive, conservative, and neutral risk analysts, repeated when `--risk-rounds` is greater than 1
  6. portfolio manager
- JSON extraction, schema validation, canonical output files, latest output aliases, and one bounded repair attempt.
- `collect`, `build-tasks`, `run-task`, `validate`, `show-run`, `analyze`, and `resume` artifact commands.
- Resume safety: `resume` reuses `analyst_roles`, `debate_rounds`, and `risk_rounds` from `manifest.json`. Explicit resume options are accepted only when they match the manifest.
- Market OHLCV collection uses `yfinance` over a 370-calendar-day lookback, which normally yields roughly one trading year of daily bars.
- Technical facts include short and longer horizon indicators: `sma_3`, `sma_5`, `sma_20`, `sma_50`, `sma_200`, `rsi_3`, and `rsi_14`.
- Final report rendering with a financial-advice disclaimer.

Known limitations:

- Only `--depth shallow` is implemented. `standard` and `deep` exist only as enum names in code, not supported CLI behavior.
- The pipeline runs sequentially. There is no implemented parallel role execution option.
- Codex requires a working local `codex exec` login. `codex login status` alone is not enough. Use `stock-agents doctor --smoke-runner codex` to verify it.
- Resume continues from checkpointed role outputs, but does not rebuild missing or corrupt fact inputs.
- Market OHLCV falls back to 252 deterministic weekday fixture bars when `yfinance` is disabled, unavailable, or returns no data.
- News, fundamentals, and sentiment collectors currently produce placeholder/local fixture facts.

## Install

From the repository root:

```bash
python -m pip install -e .
```

For the local convenience runner, use:

```bash
./run_stock_agents.sh NVDA
./run_stock_agents.sh ask
```

The runner creates `.venv` when needed, installs the package, defaults quick ticker analysis to the Codex runner, and ensures the `yfinance` dependency is present.

## Check the environment

```bash
stock-agents doctor
stock-agents doctor --smoke-runner none
stock-agents doctor --smoke-runner mock
stock-agents doctor --smoke-runner hermes
stock-agents doctor --smoke-runner codex
```

`OPENAI_API_KEY` is not required for the Hermes/Codex CLI path. Hermes auth is handled by the local Hermes Agent installation. Codex auth is handled by the local Codex CLI login.

## Run a local mock analysis

This path is deterministic and does not require network or model access:

```bash
stock-agents analyze SPY   --date 2026-01-15   --runner mock   --language Korean   --analysts market,news   --debate-rounds 1   --risk-rounds 1   --depth shallow
```

The command prints:

1. the run directory
2. the final report path

Example layout:

```text
runs/SPY/2026-01-15/<run_id>/
  inputs/
    market_facts.json
    technical_facts.json
    fundamentals_facts.json
    news_facts.json
    sentiment_facts.json
  tasks/
  outputs/
  repairs/
  reports/final_report.md
  checkpoints/state.json
  manifest.json
```

## Run with Hermes

```bash
stock-agents analyze SPY   --date 2026-01-15   --runner hermes   --provider openai-codex   --model gpt-5.5   --timeout-seconds 240   --language Korean   --analysts market,news   --debate-rounds 1   --risk-rounds 1   --depth shallow
```

Because this path spends live model calls, prefer `--runner mock` for routine regression checks.

## Run with Codex

First verify that `codex exec` works, not only that the CLI reports logged in:

```bash
stock-agents doctor --smoke-runner codex
```

Then run a shallow analysis:

```bash
stock-agents analyze SPY   --date 2026-01-15   --runner codex   --model gpt-5.5   --reasoning-effort medium   --timeout-seconds 240   --language Korean   --analysts market,news   --debate-rounds 1   --risk-rounds 1   --depth shallow
```

Codex event streams, stderr, and final-message captures are stored under each run directory's `logs/codex/` folder.

## Build or run one task

Render a task package:

```bash
stock-agents build-tasks SPY   --date 2026-01-15   --role market_analyst   --language Korean
```

Run an existing task package:

```bash
stock-agents run-task runs/SPY/2026-01-15/<run_id>/tasks/01_market_analyst.task.md   --runner hermes   --provider openai-codex   --model gpt-5.5   --timeout-seconds 240
```

## Validate and inspect artifacts

Validate raw runner output and print canonical JSON:

```bash
stock-agents validate   runs/SPY/2026-01-15/<run_id>/outputs/10_portfolio_manager.attempt0.raw.txt   --role portfolio_manager
```

Validate and write canonical JSON to a file:

```bash
stock-agents validate   runs/SPY/2026-01-15/<run_id>/outputs/10_portfolio_manager.attempt0.raw.txt   --role portfolio_manager   --output /tmp/portfolio_manager.validated.json
```

Summarize a run:

```bash
stock-agents show-run runs/SPY/2026-01-15/<run_id>
```

Resume an interrupted shallow run from its checkpoint:

```bash
stock-agents resume runs/SPY/2026-01-15/<run_id>   --runner mock   --language Korean
```

`resume` reuses `analyst_roles`, `debate_rounds`, and `risk_rounds` recorded in `manifest.json`. Explicit `--analysts`, `--debate-rounds`, or `--risk-rounds` values are accepted only when they match the manifest. Mismatches fail before new tasks run. Start a new run to change graph-shaping options.

## Round controls

```bash
stock-agents analyze SPY   --date 2026-01-15   --runner mock   --analysts all   --debate-rounds 2   --risk-rounds 2
```

Both round options are bounded to `1..3`. When a round count is greater than 1, task ids gain `_roundN` suffixes, and downstream dependency paths point at the final round's `*.latest.json` files.

## Tests

```bash
python -m pytest -q
```
