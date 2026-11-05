"""File-backed CRUD for report sources (websites) and their prompts.

The ``./prompts`` folder is the source of truth:

* Each site is one ``.txt`` file whose stem is the site's display name.
* ``systemPrompt.txt`` is reserved: it is always applied, never listed as a
  selectable site, and cannot be deleted.

All functions are pure file operations with no Streamlit or agent
dependencies so they can be unit tested in isolation.
"""

from __future__ import annotations

import re
from pathlib import Path

# Reserved file for the always-applied system prompt.
SYSTEM_PROMPT_FILENAME = "systemPrompt.txt"

# Files that live in ./prompts but are not user-selectable sites. The system
# prompt is always applied; task1.txt is the standalone example task consumed
# by scripts/bu.py's __main__ path.
_RESERVED_FILENAMES = {SYSTEM_PROMPT_FILENAME.lower(), "task1.txt"}

# Default prompts directory, resolved relative to this file's location so it
# works regardless of the current working directory.
_DEFAULT_PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"


def _prompts_dir(prompts_dir: str | Path | None = None) -> Path:
    """Resolve the prompts directory, creating it if necessary.

    ``prompts_dir`` is configurable so tests can point at a temp directory.
    """
    directory = Path(prompts_dir) if prompts_dir is not None else _DEFAULT_PROMPTS_DIR
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def sanitize_name(name: str) -> str:
    """Turn a display name into a safe filename stem.

    Strips path separators and characters illegal on Windows, collapses
    whitespace, and trims. Raises ``ValueError`` for empty results.
    """
    cleaned = name.strip()
    # Remove characters that are illegal in Windows filenames.
    cleaned = re.sub(r'[<>:"/\\|?*]', "", cleaned)
    # Collapse internal whitespace runs to single spaces.
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    if not cleaned:
        raise ValueError("Site name is empty after sanitization.")
    return cleaned


def _site_path(name: str, prompts_dir: str | Path | None = None) -> Path:
    stem = sanitize_name(name)
    return _prompts_dir(prompts_dir) / f"{stem}.txt"


def list_sites(prompts_dir: str | Path | None = None) -> list[str]:
    """Return sorted display names of all sites (excludes the system prompt)."""
    directory = _prompts_dir(prompts_dir)
    names = [
        path.stem
        for path in directory.glob("*.txt")
        if path.name.lower() not in _RESERVED_FILENAMES
    ]
    return sorted(names)


def get_prompt(site: str, prompts_dir: str | Path | None = None) -> str:
    """Return the prompt text for ``site`` (empty string if the file is missing)."""
    path = _site_path(site, prompts_dir)
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def save_prompt(site: str, text: str, prompts_dir: str | Path | None = None) -> None:
    """Write ``text`` as the prompt for ``site``, creating the file if needed."""
    path = _site_path(site, prompts_dir)
    path.write_text(text, encoding="utf-8")


def add_site(name: str, prompts_dir: str | Path | None = None) -> str:
    """Create a new empty prompt file for ``name``.

    Returns the sanitized site name. Raises ``ValueError`` if the name is
    reserved (resolves to the system prompt) or already exists.
    """
    stem = sanitize_name(name)
    if f"{stem}.txt".lower() in _RESERVED_FILENAMES:
        raise ValueError("That name is reserved and cannot be used for a source.")
    path = _site_path(stem, prompts_dir)
    if path.exists():
        raise ValueError(f"A source named '{stem}' already exists.")
    path.write_text("", encoding="utf-8")
    return stem


def delete_site(name: str, prompts_dir: str | Path | None = None) -> None:
    """Delete the prompt file for ``name``.

    Raises ``ValueError`` if asked to delete the reserved system prompt.
    """
    stem = sanitize_name(name)
    if f"{stem}.txt".lower() in _RESERVED_FILENAMES:
        raise ValueError("That file is reserved and cannot be deleted.")
    path = _site_path(stem, prompts_dir)
    if path.exists():
        path.unlink()


def get_system_prompt(prompts_dir: str | Path | None = None) -> str:
    """Return the system prompt text (empty string if not yet created)."""
    path = _prompts_dir(prompts_dir) / SYSTEM_PROMPT_FILENAME
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def save_system_prompt(text: str, prompts_dir: str | Path | None = None) -> None:
    """Write the system prompt text."""
    path = _prompts_dir(prompts_dir) / SYSTEM_PROMPT_FILENAME
    path.write_text(text, encoding="utf-8")
