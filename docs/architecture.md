# stock-agents architecture

This document is the live implementation contract for the current branch. The code is canonical when this document and implementation disagree.

## Purpose

`stock-agents` ports the TradingAgents-style multi-role research flow to a file-handoff CLI. The orchestrator builds deterministic inputs and task packages. External agents such as Hermes or Codex run the prompts. The orchestrator then validates JSON outputs, records artifacts, and renders the final report.

The project is research assistance only. It is not financial advice.

## Command surface

The Typer CLI exposes these commands:

- `doctor`: check Hermes/Codex executables and optional runner smoke paths.
- `build-tasks`: render one role task package to stdout.
- `run-task`: run a rendered task package with `mock`, `hermes`, or `codex`.
- `validate`: extract and validate one raw runner output against a role schema.
- `show-run`: summarize checkpoint status and output artifact paths.
- `collect`: collect fact artifacts without invoking a runner.
- `analyze`: run the shallow analysis pipeline.
- `resume`: resume an existing shallow run from checkpoint state.

Run `stock-agents --help` and per-command `--help` for the exact option set.

## Runners

All runners implement the `AgentRunner` protocol from `src/stock_agents/runners/base.py`:

```python
def run(self, prompt: str, *, cwd: Path, timeout_seconds: int) -> RunnerResult:
    ...
```

Current runners:

- `MockRunner`: deterministic local fixtures for tests and offline smoke runs.
- `HermesRunner`: calls `hermes chat -Q`, optionally with `--provider` and `-m`, and sets `--source stock-agents`.
- `CodexRunner`: calls `codex exec --sandbox workspace-write`, sends the prompt on stdin, writes Codex event logs under `logs/codex/`, and returns the last message when available.

## Data and fact collection

`collect_all_facts` writes this input set:

- `inputs/market_facts.json`
- `inputs/technical_facts.json`
- `inputs/fundamentals_facts.json`
- `inputs/news_facts.json`
- `inputs/sentiment_facts.json`

Market facts use `yfinance` over a 370-calendar-day lookback, normally yielding roughly one trading year of daily OHLCV bars. If yfinance is disabled through `STOCK_AGENTS_DISABLE_YFINANCE=1`, unavailable, or returns no data, 252 deterministic weekday fixture bars are used so local tests and mock analysis remain runnable. Technical facts include `sma_3`, `sma_5`, `sma_20`, `sma_50`, `sma_200`, `rsi_3`, and `rsi_14`. News facts use `yfinance` ticker news and global macro searches over a seven-day lookback; Korean six-digit tickers fall back to Naver Finance/Search only when yfinance ticker news is missing or below the target count. Failed news calls add warnings and keep the run moving. Sentiment and fundamentals currently use local placeholder fixture data.

## Shallow graph

Only `--depth shallow` is implemented.

Analyst selection:

- default: `market,news`
- `--analysts all`: `market,sentiment,news,fundamentals`
- explicit comma-separated aliases: `market`, `sentiment`, `news`, `fundamentals`

Graph order:

1. selected analysts
2. bull researcher and bear researcher, repeated for `--debate-rounds`
3. research manager
4. trader
5. aggressive, conservative, and neutral risk analysts, repeated for `--risk-rounds`
6. portfolio manager

Round limits:

- `--debate-rounds`: valid range `1..3`
- `--risk-rounds`: valid range `1..3`

When a debate or risk round count is greater than 1, repeated task ids use `_roundN` suffixes. Latest aliases are written as `outputs/<task_id>.latest.json`. The research manager reads the final bull/bear round. The portfolio manager reads the final risk round.

## Task package contract

Each rendered task includes:

- YAML-like metadata block with `task_id`, `role`, `ticker`, `trade_date`, `language`, `output_schema`, `output_path`, input paths, dependency paths, and `max_repair_attempts`.
- role description and objective.
- input file list.
- dependency output list.
- evidence rules and forbidden claims.
- exact JSON schema for the required output model.

Common evidence rules require material claims to cite fact files or dependency outputs. Common forbidden claims prevent guaranteed returns, financial-advice framing, and unsupported outside facts.

## Output schemas

Role outputs are Pydantic models:

- `AnalystOutput`
- `DebateArgumentOutput`
- `ResearchPlanOutput`
- `TraderProposalOutput`
- `RiskArgumentOutput`
- `PortfolioDecisionOutput`

`PortfolioDecisionOutput` requires `not_financial_advice=true`. Confidence fields are bounded to `0.0..1.0`.

## Validation and repair

For each role:

1. The runner stdout is saved as `outputs/<task_id>.attemptN.raw.txt`.
2. The orchestrator extracts one JSON object from stdout.
3. The JSON object is validated against the role schema.
4. On validation failure, the orchestrator writes one repair prompt under `repairs/` and retries once by default.
5. A validated canonical JSON file is written to `outputs/<task_id>.attemptN.json`.
6. A latest alias is written to `outputs/<task_id>.latest.json`.

Runner exit failures are not repaired. They mark checkpoint state as `failed_validation` through the current pipeline error path.

## Run directory layout

```text
runs/<ticker>/<date>/<run_id>/
  inputs/
  tasks/
  outputs/
  repairs/
  reports/final_report.md
  checkpoints/state.json
  manifest.json
  logs/codex/
```

`logs/codex/` appears only for Codex runner executions.

Safe path behavior:

- ticker must be a single safe path component.
- trade date must use `YYYY-MM-DD`.
- run id must be a safe path component.

## Manifest and checkpoint

`manifest.json` records the run identity, input artifacts, completed roles, selected analyst roles, debate rounds, risk rounds, and final report path.

`checkpoints/state.json` records run status, current step, completed steps, and output aliases. `show-run` displays this checkpoint in human-readable form.

## Resume contract

`resume` loads `analyst_roles`, `debate_rounds`, and `risk_rounds` from `manifest.json`.

- If `--analysts`, `--debate-rounds`, or `--risk-rounds` is omitted, the manifest value is reused.
- If an explicit value differs from the manifest, resume fails before new tasks are scheduled.
- Missing legacy `risk_rounds` in a manifest defaults to `1`.
- Resume validates existing latest outputs. Missing or invalid role outputs are rerun from the next attempt number.
- Resume does not rebuild missing or corrupt fact input files.

## Report contract

The final report is written to `reports/final_report.md`. It includes:

- date
- rating
- action
- confidence
- executive summary
- investment thesis
- major risks
- supporting evidence
- role detail from the portfolio manager output
- non-financial-advice disclaimer

## Current limitations

- Only shallow depth is implemented.
- No parallel execution option is implemented.
- No direct OpenAI API runner exists.
- yfinance is installed as a runtime dependency, but deterministic fixture fallback remains available for offline tests and smoke runs.
- News collection depends on yfinance news endpoints and can be disabled with `STOCK_AGENTS_DISABLE_NEWS=1`.
- Sentiment and fundamentals are placeholder/local fixture collectors.
- Resume does not regenerate fact inputs.
- Real Hermes and Codex runs depend on local CLI authentication and may spend live model calls.
