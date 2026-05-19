# TradingAgents Hermes/Codex Port Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** 기존 TradingAgents의 주식 데이터 수집, 다중 분석가, 토론, 리스크 검토, 최종 투자 판단 흐름을 보존하되, LLM 호출을 OpenAI API key가 아니라 Hermes Agent 또는 Codex CLI 실행으로 대체하는 새 프로젝트를 만든다.

**Architecture:** Python CLI 오케스트레이터가 시장 데이터와 정적 fact package를 만들고, 각 agent role별 task package를 파일로 생성한다. Hermes/Codex runner는 그 package를 읽고 JSON/Markdown 결과를 작성한다. 오케스트레이터는 결과를 Pydantic schema로 검증하고, 실패 시 bounded repair task를 만들며, 최종 보고서와 checkpoint를 저장한다.

**Tech Stack:** Python 3.11+, Typer, Rich/Textual-lite CLI, Pydantic v2, yfinance, pandas, Jinja2, pytest, optional Hermes CLI, optional Codex CLI.

---

## 1. 가능 여부

가능하다. 다만 원래 TradingAgents처럼 LangChain client가 OpenAI API를 직접 호출하는 구조가 아니라, 아래처럼 바꿔야 한다.

```text
기존 TradingAgents:
  Python/LangGraph -> LangChain ChatOpenAI -> OpenAI API billing

새 프로젝트:
  Python orchestrator -> task package files -> hermes chat 또는 codex exec -> output files -> validator/reporter
```

이 방식의 장점:
- ChatGPT 구독 기반 Hermes/Codex 로그인을 활용할 수 있다.
- `OPENAI_API_KEY` 기반 별도 API 과금을 피할 수 있다.
- 각 agent의 입력/출력이 파일로 남아 재현성과 디버깅이 좋아진다.
- 실패한 agent만 재실행할 수 있다.

제약:
- Hermes/Codex CLI를 subprocess로 호출하므로 API 직접 호출보다 느리다.
- 완전한 structured output 보장이 없으므로 schema validation과 repair loop가 필수다.
- Codex/Hermes 로그인 상태, CLI 버전, sandbox 정책에 영향을 받는다.
- 실시간 병렬 실행은 가능하지만, 초기 버전은 안정성을 위해 sequential 기본값을 둔다.

현재 환경 관찰:
- 새 repo clone 위치: `/home/dudupunch0/stock/stock_repo`
- remote: `https://github.com/dudupunch0-sketch/stock_repo.git`
- remote는 현재 empty repo다.
- Hermes CLI는 `openai-codex` provider, `gpt-5.5`로 동작 확인됨.
- Codex CLI는 설치되어 있고 `codex login status`는 ChatGPT 로그인으로 보이지만, `codex exec` 실행 중 refresh token 오류가 발생했다. 실제 Codex runner는 재로그인 후 검증해야 한다.

---

## 2. 보존할 기존 TradingAgents 기능

### 2.1 분석 흐름

기존 방향성은 유지한다.

1. Analyst Team
   - Market Analyst
   - Sentiment Analyst
   - News Analyst
   - Fundamentals Analyst

2. Research Team
   - Bull Researcher
   - Bear Researcher
   - Research Manager

3. Trader
   - Buy / Hold / Sell 방향 제안

4. Risk Management
   - Aggressive Risk Analyst
   - Neutral Risk Analyst
   - Conservative Risk Analyst

5. Portfolio Manager
   - 최종 등급: Buy / Overweight / Hold / Underweight / Sell

### 2.2 데이터 기능

초기 보존 범위:
- ticker/date 입력
- Yahoo Finance 기반 OHLCV 조회
- 기본 technical indicator 계산
- fundamentals summary
- ticker news 수집
- global/macro news task package
- crypto ticker일 때 fundamentals 제외
- benchmark ticker 비교 구조

후속 확장:
- Alpha Vantage vendor option
- source별 provenance 기록
- local cache TTL
- report diff/resume

### 2.3 UX 기능

보존 또는 재구성할 UX:
- interactive CLI
- Korean output language
- analyst 선택
- research depth 선택
- checkpoint/resume
- report 저장
- logs 저장
- debug artifacts 저장

---

## 3. 새 아키텍처

### 3.1 핵심 원칙

LLM을 라이브러리 client로 import하지 않는다. LLM runner는 외부 CLI process다.

```text
stock_repo CLI
  ├─ deterministic data/fact builder
  ├─ task package generator
  ├─ Hermes/Codex runner adapter
  ├─ schema validator/importer
  ├─ debate/reconciliation orchestrator
  ├─ report renderer
  └─ checkpoint/log manager
```

### 3.2 Runner abstraction

공통 인터페이스:

```python
class AgentRunner(Protocol):
    def run_task(self, task: AgentTask, context: RunContext) -> AgentResult:
        ...
```

구현체:
- `HermesRunner`
  - 기본 추천 runner
  - 명령 예시: `hermes chat -Q --provider openai-codex -m gpt-5.5 -q <prompt>`
  - 현재 환경에서 짧은 smoke 성공

- `CodexRunner`
  - 명령 예시: `codex exec --sandbox workspace-write -m gpt-5.5 <prompt>`
  - 코드/파일 작성이 필요한 agent task에 유리
  - 현재는 재로그인 검증 필요

- `MockRunner`
  - 테스트용 deterministic fixture output

### 3.3 File handoff contract

각 agent 실행마다 아래 폴더를 만든다.

```text
runs/<ticker>/<date>/<run_id>/
  inputs/
    market_facts.json
    fundamentals_facts.json
    news_facts.json
    run_config.json
  tasks/
    01_market_analyst.task.md
    02_news_analyst.task.md
    03_fundamentals_analyst.task.md
    04_bull_researcher.task.md
    ...
  outputs/
    01_market_analyst.output.json
    02_news_analyst.output.json
    ...
  reports/
    market_report.md
    news_report.md
    final_report.md
  checkpoints/
    state.json
  logs/
    runner.log
    validation.log
```

Task file에는 반드시 포함한다.
- role name
- objective
- input files
- required output schema
- language policy
- evidence/provenance rules
- uncertainty/confidence rules
- forbidden behavior: 가격 예측 단정, 투자 조언 단정, 출처 없는 주장

### 3.4 Output schema

초기 공통 schema:

```json
{
  "role": "market_analyst",
  "ticker": "NVDA",
  "date": "2026-01-15",
  "summary": "...",
  "signals": [
    {
      "name": "trend",
      "direction": "bullish|bearish|neutral",
      "confidence": 0.0,
      "evidence": ["..."]
    }
  ],
  "risks": ["..."],
  "unknowns": ["..."],
  "report_markdown": "..."
}
```

최종 decision schema:

```json
{
  "ticker": "NVDA",
  "date": "2026-01-15",
  "rating": "Buy|Overweight|Hold|Underweight|Sell",
  "action": "Buy|Hold|Sell",
  "confidence": 0.0,
  "thesis": "...",
  "supporting_evidence": ["..."],
  "major_risks": ["..."],
  "not_financial_advice": true,
  "report_markdown": "..."
}
```

---

## 4. 제안 repo 구조

```text
stock_repo/
  pyproject.toml
  README.md
  .gitignore
  docs/
    architecture.md
    plans/
      2026-05-19-tradingagents-hermes-codex-port.md
  src/
    stock_agents/
      __init__.py
      cli.py
      config.py
      data/
        __init__.py
        yfinance_client.py
        indicators.py
        cache.py
      schemas/
        __init__.py
        tasks.py
        outputs.py
        decisions.py
      prompts/
        analyst_market.md.j2
        analyst_news.md.j2
        analyst_fundamentals.md.j2
        researcher_bull.md.j2
        researcher_bear.md.j2
        manager_research.md.j2
        trader.md.j2
        risk_aggressive.md.j2
        risk_neutral.md.j2
        risk_conservative.md.j2
        portfolio_manager.md.j2
      runners/
        __init__.py
        base.py
        hermes.py
        codex.py
        mock.py
      orchestration/
        __init__.py
        pipeline.py
        checkpoints.py
        repair.py
      reporting/
        __init__.py
        renderer.py
  tests/
    test_data_yfinance.py
    test_task_contract.py
    test_output_validation.py
    test_mock_pipeline.py
    test_cli_smoke.py
```

---

## 5. 단계별 구현 계획

### Phase 0: Project bootstrap

Objective: empty repo를 실행 가능한 Python package로 만든다.

Tasks:
1. Create `pyproject.toml` with package metadata and dependencies.
2. Create `src/stock_agents/__init__.py`.
3. Create `src/stock_agents/cli.py` with `stock-agents --help` only.
4. Add `.gitignore` for `.venv`, `runs/`, caches, secrets.
5. Add `README.md` with project purpose and non-financial-advice warning.
6. Verify: `python -m pip install -e .` and `stock-agents --help`.

### Phase 1: Data/fact layer

Objective: LLM 없이 입력 ticker/date의 facts를 생성한다.

Tasks:
1. Implement config model: ticker, date, analysts, depth, runner.
2. Implement yfinance OHLCV fetch.
3. Implement basic indicators: SMA, EMA, RSI placeholder or real calculation.
4. Implement data cache under `.stock_agents/cache` or configurable path.
5. Implement fact package writer.
6. Verify with `SPY` small date range.

Acceptance:
- `stock-agents collect SPY --date YYYY-MM-DD` creates `inputs/market_facts.json`.
- No LLM runner is invoked.

### Phase 2: Schema and task package contract

Objective: Hermes/Codex가 따라야 할 안정적인 파일 contract를 만든다.

Tasks:
1. Define `AgentTask` schema.
2. Define per-role output schemas.
3. Define final decision schema.
4. Create Jinja2 templates for market/news/fundamentals analyst.
5. Implement `build-task` command.
6. Add tests for schema validation and template required sections.

Acceptance:
- Task files include input paths, schema, evidence rules, output path.
- Malformed output JSON fails with useful validation errors.

### Phase 3: Hermes runner MVP

Objective: 현재 작동하는 Hermes `openai-codex` provider를 runner로 사용한다.

Tasks:
1. Implement `HermesRunner` with subprocess execution.
2. Use temporary prompt file to avoid shell quoting problems.
3. Capture stdout/stderr, exit code, duration.
4. Require model/provider config default: `openai-codex`, `gpt-5.5`.
5. Add `--runner hermes` CLI option.
6. Add smoke command that asks Hermes to produce a tiny valid JSON fixture.

Acceptance:
- `stock-agents run-task tasks/01_market_analyst.task.md --runner hermes` writes an output file.
- Output validates against schema or creates repair task.

### Phase 4: Mock pipeline and end-to-end orchestration

Objective: LLM 없이 전체 graph shape를 테스트한다.

Tasks:
1. Implement `MockRunner` fixtures for every role.
2. Implement pipeline order: analysts -> researchers -> trader -> risk -> portfolio.
3. Implement checkpoint state file.
4. Implement resume behavior.
5. Implement final report renderer.
6. Add `stock-agents analyze TICKER --date DATE --runner mock`.

Acceptance:
- Full pipeline passes with mock runner.
- Final report is written to `runs/<ticker>/<date>/<run_id>/reports/final_report.md`.

### Phase 5: Hermes real analysis MVP

Objective: 실제 Hermes/GPT-5.5로 얕은 분석을 한 번 끝까지 돌린다.

Tasks:
1. Limit default analysts to Market + News for first run.
2. Add `--depth shallow` with one debate round.
3. Add validation repair loop with max 1 attempt.
4. Add Korean output option.
5. Add cost/API warning: no OpenAI API key used, but ChatGPT/Hermes login required.
6. Run one ticker smoke.

Acceptance:
- `stock-agents analyze SPY --date <recent> --runner hermes --language Korean --depth shallow` completes.
- No `OPENAI_API_KEY` is required.
- Report includes non-financial-advice disclaimer.

### Phase 6: Codex runner

Objective: Codex CLI를 optional runner로 붙인다.

Precondition:
- `codex exec` must work. Current environment showed refresh token failure despite `codex login status` saying logged in.

Tasks:
1. Add Codex auth smoke command.
2. Implement `CodexRunner` command builder.
3. Use `--sandbox workspace-write`, `-m gpt-5.5`, and configurable `model_reasoning_effort`.
4. Store Codex session logs.
5. Verify with a tiny JSON task.

Acceptance:
- `stock-agents doctor` reports Codex runner usable only when `codex exec` succeeds.
- Codex failure does not break Hermes runner.

### Phase 7: Feature parity hardening

Objective: 기존 TradingAgents에 가까운 기능을 채운다.

Tasks:
1. Add all analyst roles.
2. Add bull/bear debate with configurable rounds.
3. Add risk team debate.
4. Add portfolio manager synthesis.
5. Add crypto mode behavior.
6. Add analyst concurrency option, default sequential.
7. Add saved reports equivalent to TradingAgents.
8. Add regression tests and sample fixture run.

Acceptance:
- 기존 TradingAgents의 주요 user-facing options를 새 CLI에서 제공한다.
- mock runner full suite passes.
- Hermes runner shallow path passes.

---

## 6. CLI 초안

```bash
stock-agents doctor
stock-agents collect SPY --date 2026-01-15
stock-agents build-tasks SPY --date 2026-01-15 --analysts market,news
stock-agents run-task runs/SPY/2026-01-15/<run_id>/tasks/01_market_analyst.task.md --runner hermes
stock-agents analyze SPY --date 2026-01-15 --runner hermes --language Korean --depth shallow
stock-agents analyze NVDA --date 2026-01-15 --runner codex --language Korean --depth shallow
```

Config defaults:

```toml
runner = "hermes"
model = "gpt-5.5"
provider = "openai-codex"
language = "Korean"
depth = "shallow"
max_repair_attempts = 1
```

---

## 7. Testing strategy

Required tests:
- data fetch can be mocked without network
- indicator calculations are deterministic
- task package includes schema and output path
- runner command builders do not leak secrets
- malformed JSON triggers repair task
- mock full pipeline produces final report
- CLI `--help` works
- `doctor` reports Hermes/Codex availability accurately

Commands:

```bash
python -m pytest -q
stock-agents doctor
stock-agents analyze SPY --date 2026-01-15 --runner mock --language Korean
```

Real runner tests should be opt-in:

```bash
RUN_HERMES_SMOKE=1 python -m pytest tests/test_hermes_runner_smoke.py -q
RUN_CODEX_SMOKE=1 python -m pytest tests/test_codex_runner_smoke.py -q
```

---

## 8. First milestone acceptance criteria

Milestone 1 is complete when:

1. Repo has installable Python package.
2. `stock-agents --help` works.
3. `stock-agents doctor` detects Hermes and Codex runner status.
4. `stock-agents collect SPY --date <date>` writes fact JSON.
5. `stock-agents analyze SPY --runner mock` runs full pipeline and writes final report.
6. `stock-agents run-task ... --runner hermes` can complete one simple role task.
7. The project does not require `OPENAI_API_KEY` for the Hermes path.
8. Codex path is marked unavailable until `codex exec` auth is fixed.

---

## 9. Important implementation notes

- Do not copy TradingAgents source wholesale unless license and attribution are checked. Reimplement the architecture and preserve user-facing behavior.
- Keep deterministic data collection separate from agent semantic synthesis.
- Never silently drop agent-only findings. If validator cannot reconcile them with facts, store them as `agent_only_findings`, `coverage_gaps`, or warnings with confidence.
- Repair loops must be bounded with `max_repair_attempts`.
- Previous outputs must not be mutated in place. Write corrected outputs as new attempt files.
- Logs must redact API keys/tokens and must never print Hermes/Codex auth files.
- Reports must include a non-financial-advice disclaimer.
