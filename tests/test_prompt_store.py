"""Tests for the file-backed prompt_store module."""

import sys
from pathlib import Path

import pytest

# Make the workspace root importable when pytest runs from anywhere.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import prompt_store as ps


@pytest.fixture
def prompts_dir(tmp_path):
    """A fresh temp prompts directory per test."""
    return tmp_path / "prompts"


def test_add_and_list_sites(prompts_dir):
    ps.add_site("NYS Incorporation", prompts_dir)
    ps.add_site("UCC Search", prompts_dir)
    assert ps.list_sites(prompts_dir) == ["NYS Incorporation", "UCC Search"]


def test_list_sites_empty(prompts_dir):
    assert ps.list_sites(prompts_dir) == []


def test_save_and_get_prompt(prompts_dir):
    ps.add_site("Site A", prompts_dir)
    ps.save_prompt("Site A", "hello world", prompts_dir)
    assert ps.get_prompt("Site A", prompts_dir) == "hello world"


def test_get_prompt_missing_returns_empty(prompts_dir):
    assert ps.get_prompt("Does Not Exist", prompts_dir) == ""


def test_save_prompt_creates_file(prompts_dir):
    ps.save_prompt("Fresh Site", "content", prompts_dir)
    assert ps.get_prompt("Fresh Site", prompts_dir) == "content"
    assert "Fresh Site" in ps.list_sites(prompts_dir)


def test_delete_site(prompts_dir):
    ps.add_site("Temp", prompts_dir)
    assert "Temp" in ps.list_sites(prompts_dir)
    ps.delete_site("Temp", prompts_dir)
    assert "Temp" not in ps.list_sites(prompts_dir)


def test_add_duplicate_rejected(prompts_dir):
    ps.add_site("Dup", prompts_dir)
    with pytest.raises(ValueError):
        ps.add_site("Dup", prompts_dir)


def test_add_empty_name_rejected(prompts_dir):
    with pytest.raises(ValueError):
        ps.add_site("   ", prompts_dir)


def test_system_prompt_not_listed(prompts_dir):
    ps.save_system_prompt("system rules", prompts_dir)
    ps.add_site("Real Site", prompts_dir)
    sites = ps.list_sites(prompts_dir)
    assert "systemPrompt" not in sites
    assert "Real Site" in sites


def test_system_prompt_save_and_get(prompts_dir):
    ps.save_system_prompt("be careful", prompts_dir)
    assert ps.get_system_prompt(prompts_dir) == "be careful"


def test_get_system_prompt_missing_returns_empty(prompts_dir):
    assert ps.get_system_prompt(prompts_dir) == ""


def test_cannot_add_site_named_system_prompt(prompts_dir):
    with pytest.raises(ValueError):
        ps.add_site("systemPrompt", prompts_dir)


def test_cannot_delete_system_prompt(prompts_dir):
    ps.save_system_prompt("rules", prompts_dir)
    with pytest.raises(ValueError):
        ps.delete_site("systemPrompt", prompts_dir)
    # Still present after the failed delete attempt.
    assert ps.get_system_prompt(prompts_dir) == "rules"


def test_sanitize_strips_illegal_chars(prompts_dir):
    stem = ps.add_site('Weird/Name:With*Chars', prompts_dir)
    assert stem == "WeirdNameWithChars"
    assert stem in ps.list_sites(prompts_dir)


def test_names_with_spaces_roundtrip(prompts_dir):
    ps.add_site("NYS Department of Taxation and Finance", prompts_dir)
    ps.save_prompt("NYS Department of Taxation and Finance", "tax", prompts_dir)
    assert ps.get_prompt("NYS Department of Taxation and Finance", prompts_dir) == "tax"


def test_task1_excluded_from_sites(prompts_dir):
    # task1.txt is a reserved standalone example, not a selectable site.
    (prompts_dir).mkdir(parents=True, exist_ok=True)
    (prompts_dir / "task1.txt").write_text("example", encoding="utf-8")
    ps.add_site("Real Site", prompts_dir)
    sites = ps.list_sites(prompts_dir)
    assert "task1" not in sites
    assert "Real Site" in sites


def test_cannot_delete_task1(prompts_dir):
    (prompts_dir).mkdir(parents=True, exist_ok=True)
    (prompts_dir / "task1.txt").write_text("example", encoding="utf-8")
    with pytest.raises(ValueError):
        ps.delete_site("task1", prompts_dir)


def test_real_prompts_dir_seeded():
    # Against the actual ./prompts folder seeded in Task 2.
    sites = ps.list_sites()
    for expected in (
        "NYS Incorporation",
        "NYS Department of Taxation and Finance",
        "NYS Department of State UCC Search",
    ):
        assert expected in sites
    assert "task1" not in sites
    assert "systemPrompt" not in sites
    assert ps.get_system_prompt().strip() != ""
