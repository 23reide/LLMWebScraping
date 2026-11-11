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


def _build_agent(task: str) -> Agent:
    """Construct the browser-use Agent with the configuration known to work.

    Isolated so tests can monkeypatch it without triggering a live run.
    """
    llm = ChatGoogle(model="gemini-3.1-flash-lite")
    return Agent(
        task=task,
        llm=llm,
        llm_timeout=600,
        step_timeout=600,
        use_vision=False,
    )


async def _run_agent(task: str) -> str:
    """Run the agent for ``task`` and return its final result as a string."""
    agent = _build_agent(task)
    history = await agent.run()
    return str(history.final_result())


def run_report(task: str) -> str:
    """Run the agent synchronously for ``task``.

    Writes the result to a timestamped file under ``./outputs`` and returns the
    result string. Safe to call from Streamlit (wraps the async run).
    """
    result = asyncio.run(_run_agent(task))

    _OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    output_path = _OUTPUTS_DIR / f"report_{stamp}.txt"
    output_path.write_text(result, encoding="utf-8")

    return result


if __name__ == "__main__":
    prompt_file = _PROMPTS_DIR / "task1.txt"
    task_text = prompt_file.read_text(encoding="utf-8")
    final = run_report(task_text)
    print(final)
