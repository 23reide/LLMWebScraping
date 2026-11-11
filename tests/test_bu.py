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
    monkeypatch.setattr(
        bu, "_build_agent", lambda task, file_system_path: _FakeAgent(f"RESULT::{task}")
    )
    return bu, outputs


def test_run_report_passes_task_through(bu):
    module, _ = bu
    result = module.run_report("find the thing")
    assert result == "RESULT::find the thing"


def test_run_report_writes_output_file(bu):
    module, outputs = bu
    module.run_report("do work")
    files = list(outputs.glob("report_*/report_*.txt"))
    assert len(files) == 1
    assert files[0].read_text(encoding="utf-8") == "RESULT::do work"


def test_start_report_streams_and_completes(bu):
    module, outputs = bu
    run = module.start_report("stream me")

    # Drain the stream until the worker finishes (mirrors the UI loop).
    collected = []
    while run.is_alive():
        collected.extend(run.stream(timeout=0.2))
    collected.extend(run.stream(timeout=0.2))

    assert run.error is None
    assert run.result == "RESULT::stream me"
    assert run.run_dir is not None and run.run_dir.exists()
    # The final report text was written into the run folder.
    assert (run.run_dir / f"{run.run_dir.name}.txt").read_text(encoding="utf-8") == (
        "RESULT::stream me"
    )


def test_start_report_captures_errors(bu, monkeypatch):
    module, _ = bu

    class _BoomAgent:
        async def run(self):
            raise RuntimeError("agent exploded")

    monkeypatch.setattr(module, "_build_agent", lambda task, file_system_path: _BoomAgent())

    run = module.start_report("will fail")
    while run.is_alive():
        list(run.stream(timeout=0.2))
    list(run.stream(timeout=0.2))

    assert run.result is None
    assert isinstance(run.error, RuntimeError)
    assert "agent exploded" in str(run.error)


def test_start_report_captures_nonpropagating_logs(bu, monkeypatch):
    """Regression: browser-use sets propagate=False on its loggers, so a root
    handler never sees them. The run must attach to those named loggers."""
    import logging

    module, _ = bu

    # Mimic browser-use: a detached logger that does not propagate to root.
    detached = logging.getLogger("browser_use.agent")
    detached.propagate = False

    class _LoggingAgent:
        async def run(self):
            logging.getLogger("browser_use.agent").info("step 1: navigating")
            logging.getLogger("browser_use").info("agent step complete")
            return _FakeHistory("done")

    monkeypatch.setattr(module, "_build_agent", lambda task, file_system_path: _LoggingAgent())

    run = module.start_report("log please")
    collected = []
    while run.is_alive():
        collected.extend(run.stream(timeout=0.2))
    collected.extend(run.stream(timeout=0.2))

    assert run.error is None
    joined = "\n".join(collected)
    assert "step 1: navigating" in joined
    assert "agent step complete" in joined


def test_zip_run_evidence_packages_all_files(bu, monkeypatch):
    import zipfile

    module, _ = bu

    # A fake agent that also drops an "evidence" file into the run folder,
    # the way browser-use's save_as_pdf would.
    class _EvidenceAgent:
        def __init__(self, run_dir):
            self._run_dir = Path(run_dir)

        async def run(self):
            evidence = module.evidence_dir(self._run_dir)
            evidence.mkdir(parents=True, exist_ok=True)
            (evidence / "Proof.pdf").write_bytes(b"%PDF-1.4 fake")
            return _FakeHistory("done")

    monkeypatch.setattr(
        module, "_build_agent", lambda task, file_system_path: _EvidenceAgent(file_system_path)
    )

    run = module.start_report("gather")
    while run.is_alive():
        list(run.stream(timeout=0.2))
    list(run.stream(timeout=0.2))

    assert run.error is None
    zip_path = module.zip_run_evidence(run.run_dir)
    try:
        assert zip_path.exists()
        names = set(zipfile.ZipFile(zip_path).namelist())
    finally:
        zip_path.unlink(missing_ok=True)
    assert "browseruse_agent_data/Proof.pdf" in names
    assert f"{run.run_dir.name}.txt" in names
