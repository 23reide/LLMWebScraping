import asyncio
from datetime import datetime
from pathlib import Path

from browser_use import Agent, ChatGoogle
from dotenv import load_dotenv

load_dotenv()

# Resolve project paths relative to the workspace root (this file lives in
# <root>/scripts/bu.py) so the module works no matter the current directory.
_ROOT = Path(__file__).resolve().parent.parent
_PROMPTS_DIR = _ROOT / "prompts"
_OUTPUTS_DIR = _ROOT / "outputs"


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


def run_report(task: str) -> str:
    """Run the agent synchronously for ``task``.

    Creates a timestamped run folder under ``./outputs``, points the agent's
    file system at it so all saved evidence (PDFs/screenshots/markdown) lands
    there, writes the final result text alongside it, and returns the result
    string. Safe to call from Streamlit (wraps the async run).
    """
    _OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    run_dir = _OUTPUTS_DIR / f"report_{stamp}"
    run_dir.mkdir(parents=True, exist_ok=True)

    result = asyncio.run(_run_agent(task, str(run_dir)))

    # The agent writes evidence into <run_dir>/browseruse_agent_data. Surface
    # the final report text in the same run folder for convenience.
    (run_dir / f"report_{stamp}.txt").write_text(result, encoding="utf-8")

    return result


if __name__ == "__main__":
    prompt_file = _PROMPTS_DIR / "task1.txt"
    task_text = prompt_file.read_text(encoding="utf-8")
    final = run_report(task_text)
    print(final)
