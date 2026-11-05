"""Tests for scripts/bu.py's run_report, with the agent mocked (no network)."""

import importlib
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_ROOT / "scripts"))


class _FakeHistory:
    def __init__(self, result):
        self._result = result

    def final_result(self):
        return self._result


class _FakeAgent:
    def __init__(self, result):
        self._result = result

    async def run(self):
        return _FakeHistory(self._result)


@pytest.fixture
def bu(monkeypatch, tmp_path):
    """Import bu with the agent and outputs dir patched so it never hits the net."""
    # browser_use import happens at module load; skip if unavailable in CI.
    bu = importlib.import_module("bu")
    importlib.reload(bu)

    outputs = tmp_path / "outputs"
    monkeypatch.setattr(bu, "_OUTPUTS_DIR", outputs)
    monkeypatch.setattr(bu, "_build_agent", lambda task: _FakeAgent(f"RESULT::{task}"))
    return bu, outputs


def test_run_report_passes_task_through(bu):
    module, _ = bu
    result = module.run_report("find the thing")
    assert result == "RESULT::find the thing"


def test_run_report_writes_output_file(bu):
    module, outputs = bu
    module.run_report("do work")
    files = list(outputs.glob("report_*.txt"))
    assert len(files) == 1
    assert files[0].read_text(encoding="utf-8") == "RESULT::do work"
