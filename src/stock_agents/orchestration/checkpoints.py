from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel, Field


class CheckpointState(BaseModel):
    run_id: str
    ticker: str
    trade_date: str
    status: str
    completed_steps: list[str] = Field(default_factory=list)
    current_step: str | None = None
    outputs: dict[str, str] = Field(default_factory=dict)
    created_at: str
    updated_at: str


def new_checkpoint_state(*, run_id: str, ticker: str, trade_date: str) -> CheckpointState:
    now = datetime.now(timezone.utc).isoformat()
    return CheckpointState(
        run_id=run_id,
        ticker=ticker,
        trade_date=trade_date,
        status="running",
        current_step="collect_facts",
        created_at=now,
        updated_at=now,
    )


def read_checkpoint(run_dir: Path) -> CheckpointState:
    path = run_dir / "checkpoints" / "state.json"
    return CheckpointState.model_validate_json(path.read_text(encoding="utf-8"))


def write_checkpoint(run_dir: Path, state: CheckpointState) -> Path:
    state.updated_at = datetime.now(timezone.utc).isoformat()
    path = run_dir / "checkpoints" / "state.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(state.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return path
