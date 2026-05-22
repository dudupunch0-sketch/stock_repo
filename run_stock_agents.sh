#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="${STOCK_AGENTS_VENV:-"$ROOT_DIR/.venv"}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
CLI="$VENV_DIR/bin/stock-agents"

usage() {
  cat <<'USAGE'
stock-agents runner

Usage:
  ./run_stock_agents.sh
      Run the default live Codex analysis.

  ./run_stock_agents.sh TICKER [DATE]
      Quick live Codex analysis. DATE defaults to today.

  ./run_stock_agents.sh codex TICKER [DATE]
      Quick live Codex analysis. DATE defaults to today.

  ./run_stock_agents.sh ask
      Prompt for ticker, date, and runner interactively.

  ./run_stock_agents.sh doctor [ARGS...]
      Check the environment. Defaults to: doctor --smoke-runner mock

  ./run_stock_agents.sh analyze [ARGS...]
      Run stock-agents analyze. Uses the default live Codex args when ARGS are omitted.

  ./run_stock_agents.sh cli ARGS...
      Pass ARGS directly to stock-agents.

  ./run_stock_agents.sh install
      Create .venv if needed and install this project in editable mode.

Examples:
  ./run_stock_agents.sh
  ./run_stock_agents.sh NVDA
  ./run_stock_agents.sh 005930.KS 2026-05-22
  ./run_stock_agents.sh codex AAPL
  ./run_stock_agents.sh ask
  ./run_stock_agents.sh mock NVDA
  ./run_stock_agents.sh doctor --smoke-runner none
  ./run_stock_agents.sh analyze SPY --date 2026-01-15 --language Korean
  ./run_stock_agents.sh cli show-run runs/SPY/2026-01-15/<run_id>
USAGE
}

ensure_install() {
  cd "$ROOT_DIR"

  if [[ ! -x "$VENV_DIR/bin/python" ]]; then
    echo "Creating virtual environment: $VENV_DIR"
    "$PYTHON_BIN" -m venv "$VENV_DIR"
  fi

  if [[ ! -x "$CLI" ]] || ! "$VENV_DIR/bin/python" -c "import stock_agents, yfinance" >/dev/null 2>&1; then
    echo "Installing stock-agents into the virtual environment..."
    "$VENV_DIR/bin/python" -m pip install -e "$ROOT_DIR"
  fi
}

has_arg() {
  local needle="$1"
  shift
  local arg
  for arg in "$@"; do
    if [[ "$arg" == "$needle" || "$arg" == "$needle="* ]]; then
      return 0
    fi
  done
  return 1
}

run_default_analyze() {
  exec "$CLI" analyze SPY \
    --date "$(date +%F)" \
    --runner codex \
    --model "${STOCK_AGENTS_MODEL:-gpt-5.5}" \
    --reasoning-effort "${STOCK_AGENTS_REASONING_EFFORT:-medium}" \
    --timeout-seconds "${STOCK_AGENTS_TIMEOUT_SECONDS:-240}" \
    --language Korean \
    --analysts market,news \
    --debate-rounds 1 \
    --risk-rounds 1 \
    --depth shallow
}

quick_analyze() {
  local ticker="$1"
  local runner="${2:-${STOCK_AGENTS_RUNNER:-codex}}"
  local trade_date="${3:-${STOCK_AGENTS_DATE:-$(date +%F)}}"

  local args=(
    analyze "$ticker"
    --date "$trade_date"
    --runner "$runner"
    --language "${STOCK_AGENTS_LANGUAGE:-Korean}"
    --analysts "${STOCK_AGENTS_ANALYSTS:-market,news}"
    --debate-rounds "${STOCK_AGENTS_DEBATE_ROUNDS:-1}"
    --risk-rounds "${STOCK_AGENTS_RISK_ROUNDS:-1}"
    --depth "${STOCK_AGENTS_DEPTH:-shallow}"
  )

  case "$runner" in
    codex)
      args+=(
        --model "${STOCK_AGENTS_MODEL:-gpt-5.5}"
        --reasoning-effort "${STOCK_AGENTS_REASONING_EFFORT:-medium}"
        --timeout-seconds "${STOCK_AGENTS_TIMEOUT_SECONDS:-240}"
      )
      ;;
    hermes)
      args+=(
        --provider "${STOCK_AGENTS_PROVIDER:-openai-codex}"
        --model "${STOCK_AGENTS_MODEL:-gpt-5.5}"
        --timeout-seconds "${STOCK_AGENTS_TIMEOUT_SECONDS:-240}"
      )
      ;;
  esac

  exec "$CLI" "${args[@]}"
}

interactive_analyze() {
  local ticker
  local trade_date
  local runner

  read -r -p "Ticker, for example NVDA or 005930.KS: " ticker
  if [[ -z "$ticker" ]]; then
    echo "Ticker is required."
    exit 2
  fi

  read -r -p "Date [$(date +%F)]: " trade_date
  trade_date="${trade_date:-$(date +%F)}"

  read -r -p "Runner codex/mock/hermes [codex]: " runner
  runner="${runner:-codex}"

  case "$runner" in
    mock|codex|hermes) ;;
    *)
      echo "Runner must be one of: mock, codex, hermes"
      exit 2
      ;;
  esac

  quick_analyze "$ticker" "$runner" "$trade_date"
}

main() {
  local command="${1:-analyze}"
  if (($# > 0)); then
    shift
  fi

  case "$command" in
    -h|--help|help)
      usage
      ;;
    install)
      ensure_install
      echo "Ready: $CLI"
      ;;
    ask|interactive)
      ensure_install
      interactive_analyze
      ;;
    doctor)
      ensure_install
      if (($# == 0)); then
        set -- --smoke-runner mock
      fi
      exec "$CLI" doctor "$@"
      ;;
    analyze)
      ensure_install
      if (($# == 0)); then
        run_default_analyze
      fi
      if ! has_arg --runner "$@"; then
        set -- "$@" --runner codex
      fi
      if ! has_arg --model "$@"; then
        set -- "$@" --model "${STOCK_AGENTS_MODEL:-gpt-5.5}"
      fi
      if ! has_arg --reasoning-effort "$@"; then
        set -- "$@" --reasoning-effort "${STOCK_AGENTS_REASONING_EFFORT:-medium}"
      fi
      if ! has_arg --timeout-seconds "$@"; then
        set -- "$@" --timeout-seconds "${STOCK_AGENTS_TIMEOUT_SECONDS:-240}"
      fi
      exec "$CLI" analyze "$@"
      ;;
    cli|stock-agents)
      if (($# == 0)); then
        usage
        exit 2
      fi
      ensure_install
      exec "$CLI" "$@"
      ;;
    mock|codex|hermes)
      if (($# == 0)); then
        echo "Ticker is required."
        usage
        exit 2
      fi
      ensure_install
      quick_analyze "$1" "$command" "${2:-}"
      ;;
    collect|build-tasks|run-task|validate|show-run|resume)
      ensure_install
      exec "$CLI" "$command" "$@"
      ;;
    *)
      ensure_install
      quick_analyze "$command" "${STOCK_AGENTS_RUNNER:-codex}" "${1:-}"
      ;;
  esac
}

main "$@"
