import asyncio
import io
import logging
import os
import sys
import threading
import zipfile
from datetime import datetime
from pathlib import Path
from queue import Queue
from typing import Iterator, Optional

from browser_use import Agent, ChatGoogle
from dotenv import load_dotenv

load_dotenv()

# Resolve project paths relative to the workspace root (this file lives in
# <root>/scripts/bu.py) so the module works no matter the current directory.
_ROOT = Path(__file__).resolve().parent.parent
_PROMPTS_DIR = _ROOT / "prompts"
_OUTPUTS_DIR = _ROOT / "outputs"

# Sentinel pushed onto a log queue to signal "no more lines are coming".
_DONE = object()


def _build_agent(task: str, file_system_path: str) -> Agent:
    """Construct the browser-use Agent with the configuration known to work.

    ``file_system_path`` pins the agent's file system (where ``save_as_pdf``,
    ``screenshot`` and ``write_file`` write) to a known run folder, so the
    evidence lives next to the report instead of a throwaway %TEMP% dir.

    Isolated so tests can monkeypatch it without triggering a live run.
    """
    llm = ChatGoogle(model="gemini-3.1-flash-lite")
    return Agent(
        task=task,
        llm=llm,
        llm_timeout=600,
        step_timeout=600,
        use_vision=False,
        file_system_path=file_system_path,
    )


async def _run_agent(task: str, file_system_path: str) -> str:
    """Run the agent for ``task`` and return its final result as a string."""
    agent = _build_agent(task, file_system_path)
    history = await agent.run()
    return str(history.final_result())


def _new_run_dir() -> tuple[Path, str]:
    """Create and return a fresh timestamped run folder under ``./outputs``."""
    _OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    run_dir = _OUTPUTS_DIR / f"report_{stamp}"
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir, stamp


def _write_result(run_dir: Path, stamp: str, result: str) -> None:
    """Persist the agent's final text result next to its evidence."""
    (run_dir / f"report_{stamp}.txt").write_text(result, encoding="utf-8")


def run_report(task: str) -> str:
    """Run the agent synchronously for ``task`` and return the result string.

    Creates a timestamped run folder under ``./outputs``, points the agent's
    file system at it so all saved evidence (PDFs/screenshots/markdown) lands
    there, and writes the final result text alongside it.
    """
    run_dir, stamp = _new_run_dir()
    result = asyncio.run(_run_agent(task, str(run_dir)))
    _write_result(run_dir, stamp, result)
    return result


class _QueueWriter(io.TextIOBase):
    """A minimal text stream that forwards whatever is written to a queue.

    Used to tee ``stdout``/``stderr`` (which browser-use and its deps print to)
    into the same queue the log handler feeds, so the UI sees everything.
    """

    def __init__(self, queue: "Queue", also: Optional[object] = None):
        self._queue = queue
        self._also = also  # original stream, so the terminal still shows output

    def write(self, text: str) -> int:  # type: ignore[override]
        if text:
            self._queue.put(text.rstrip("\n"))
            if self._also is not None:
                try:
                    self._also.write(text)
                except Exception:
                    pass
        return len(text)

    def flush(self) -> None:  # type: ignore[override]
        if self._also is not None:
            try:
                self._also.flush()
            except Exception:
                pass


class _QueueLogHandler(logging.Handler):
    """Logging handler that pushes each formatted record onto a queue."""

    def __init__(self, queue: "Queue"):
        super().__init__()
        self._queue = queue

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self._queue.put(self.format(record))
        except Exception:
            pass


class ReportRun:
    """A background report run whose log output can be streamed to a UI.

    Runs :func:`run_report` on a worker thread while capturing both Python
    ``logging`` records and anything written to stdout/stderr into a thread-safe
    queue. The caller drains :meth:`stream` to display live progress, then reads
    :attr:`result` / :attr:`error` once :meth:`is_alive` is ``False``.

    This design is process-local (no files, no external services), so it behaves
    identically whether Streamlit runs locally or on a hosted server.
    """

    def __init__(self, task: str):
        self.task = task
        self.queue: "Queue" = Queue()
        self.result: Optional[str] = None
        self.error: Optional[BaseException] = None
        self.run_dir: Optional[Path] = None
        self._thread = threading.Thread(target=self._work, daemon=True)

    def start(self) -> "ReportRun":
        self._thread.start()
        return self

    def is_alive(self) -> bool:
        return self._thread.is_alive()

    def stream(self, timeout: float = 0.2) -> Iterator[str]:
        """Yield log lines captured so far, draining the queue without blocking long.

        Stops yielding when the sentinel is seen. Call repeatedly from the UI
        loop; it returns promptly so the UI stays responsive.
        """
        from queue import Empty

        while True:
            try:
                item = self.queue.get(timeout=timeout)
            except Empty:
                return
            if item is _DONE:
                return
            yield item  # type: ignore[misc]

    def _work(self) -> None:
        # Tee stdout/stderr so prints from browser-use/its deps are captured too.
        old_out, old_err = sys.stdout, sys.stderr
        sys.stdout = _QueueWriter(self.queue, also=old_out)
        sys.stderr = _QueueWriter(self.queue, also=old_err)

        handler = _QueueLogHandler(self.queue)
        handler.setLevel(logging.INFO)
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))

        # browser-use calls setup_logging() during Agent construction, which
        # sets `propagate = False` on its own loggers ('browser_use', 'bubus',
        # 'cdp_use'). A handler on the root logger therefore never sees their
        # records. Attach directly to those named loggers (plus root, for
        # anything else) so the UI actually receives output.
        logger_names = ["", "browser_use", "bubus", "cdp_use", "browser_use.agent"]
        touched: list[tuple[logging.Logger, int]] = []
        for name in logger_names:
            lg = logging.getLogger(name)
            touched.append((lg, lg.level))
            lg.addHandler(handler)
            if lg.level == logging.NOTSET or lg.level > logging.INFO:
                lg.setLevel(logging.INFO)

        try:
            run_dir, stamp = _new_run_dir()
            self.run_dir = run_dir
            # Inline the body of run_report so we keep the run_dir for evidence.
            result = asyncio.run(_run_agent(self.task, str(run_dir)))
            _write_result(run_dir, stamp, result)
            self.result = result
        except BaseException as exc:  # capture so the UI thread can surface it
            self.error = exc
        finally:
            for lg, prev_level in touched:
                lg.removeHandler(handler)
                lg.setLevel(prev_level)
            sys.stdout, sys.stderr = old_out, old_err
            self.queue.put(_DONE)


def start_report(task: str) -> ReportRun:
    """Start a report on a background thread and return a handle to stream it."""
    return ReportRun(task).start()


def evidence_dir(run_dir: Path) -> Path:
    """Return the folder where browser-use wrote evidence for ``run_dir``."""
    return run_dir / "browseruse_agent_data"


def zip_run_evidence(run_dir: Path) -> Path:
    """Zip a run folder (report text + evidence) to a temp file on disk.

    Streams each file into the archive so memory use stays flat regardless of
    how large the screenshot/PDF set grows. Returns the path to the created
    ``.zip``; the caller is responsible for deleting it when done (the Streamlit
    UI opens it, streams it to the browser, then removes it).
    """
    import tempfile

    fd, tmp_name = tempfile.mkstemp(prefix=f"{run_dir.name}_", suffix=".zip")
    os.close(fd)  # we reopen via ZipFile; just needed a unique path
    tmp_path = Path(tmp_name)
    with zipfile.ZipFile(tmp_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(run_dir.rglob("*")):
            if path.is_file():
                zf.write(path, arcname=path.relative_to(run_dir).as_posix())
    return tmp_path


if __name__ == "__main__":
    prompt_file = _PROMPTS_DIR / "task1.txt"
    task_text = prompt_file.read_text(encoding="utf-8")
    final = run_report(task_text)
    print(final)
