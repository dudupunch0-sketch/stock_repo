# TradingAgents Hermes/Codex Port Implementation Plan

> Historical plan. The live implementation contract is now `README.md`, `docs/architecture.md`, `overview.html`, and `userguide.html`.
>
> Current branch status: the package, Typer CLI, file-handoff task packages, mock/Hermes/Codex runners, shallow sequential analysis, analyst selection, bounded debate/risk rounds, validation/repair, checkpoint/resume, and final report path are implemented. Only `--depth shallow` is supported. News, sentiment, and fundamentals collectors are still placeholder/local fixture sources.

## Original goal

기존 TradingAgents의 주식 데이터 수집, 다중 분석가, 토론, 리스크 검토, 최종 투자 판단 흐름을 보존하되, LLM 호출을 OpenAI API key가 아니라 Hermes Agent 또는 Codex CLI 실행으로 대체하는 새 프로젝트를 만든다.

## Current architecture summary

```text
stock-agents CLI
  -> collect deterministic fact artifacts
  -> render role-specific task packages
  -> run mock, hermes, or codex runner
  -> extract one JSON object from runner stdout
  -> validate with Pydantic role schemas
  -> create one bounded repair prompt when validation fails
  -> write checkpoint, manifest, latest output aliases, and final report
```

Current command surface:

```bash
stock-agents doctor
stock-agents collect SPY --date 2026-01-15
stock-agents build-tasks SPY --date 2026-01-15 --role market_analyst
stock-agents run-task runs/SPY/2026-01-15/<run_id>/tasks/01_market_analyst.task.md --runner hermes
stock-agents validate runs/SPY/2026-01-15/<run_id>/outputs/10_portfolio_manager.attempt0.raw.txt --role portfolio_manager
stock-agents show-run runs/SPY/2026-01-15/<run_id>
stock-agents analyze SPY --date 2026-01-15 --runner mock --depth shallow
stock-agents resume runs/SPY/2026-01-15/<run_id> --runner mock
```

Current shallow graph:

1. selected analysts, default `market,news`, or `--analysts all`
2. bull and bear researchers, repeated by `--debate-rounds 1..3`
3. research manager
4. trader
5. aggressive, conservative, and neutral risk analysts, repeated by `--risk-rounds 1..3`
6. portfolio manager

Run artifacts:

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

## What changed from the original plan

- The implemented runner interface is `run(prompt, cwd, timeout_seconds) -> RunnerResult`, not `run_task(task, context)`.
- The current package dependencies are intentionally small: Pydantic, Typer, Rich, and Jinja2 are declared. yfinance is optional at runtime and falls back to deterministic fixture bars.
- The actual command is `build-tasks`, not `build-task`.
- `doctor --smoke-runner hermes` checks Hermes command shape without calling a live model. `doctor --smoke-runner codex` is the real `codex exec` smoke path.
- `resume` is graph-shape safe: explicit `--analysts`, `--debate-rounds`, and `--risk-rounds` must match `manifest.json` before any new task runs.
- The remote repository is no longer empty. The implementation is committed on `main`.

## Still not implemented

- `standard` or `deep` analysis depth.
- Parallel role execution.
- Direct OpenAI API runner.
- Real provider-backed news, sentiment, and fundamentals collection beyond local placeholders.
- Fact-input reconstruction during resume.
- TradingAgents source parity beyond the shallow file-handoff workflow.

## Verification command

Use this as the current local verification baseline:

```bash
python -m pytest -q
stock-agents --help
stock-agents analyze SPY --date 2026-01-15 --runner mock --analysts market,news --debate-rounds 1 --risk-rounds 1 --depth shallow
```

## Historical notes retained

The original strategic intent remains valid: preserve a TradingAgents-like multi-role research workflow while avoiding direct OpenAI API key usage in the orchestrator. The live CLI now uses external Hermes/Codex CLI processes or deterministic mock output through file handoff.
