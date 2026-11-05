"""Headless Streamlit integration tests for app.py.

Uses streamlit's AppTest. The agent (bu.run_report) is never called live:
tests either avoid triggering it or monkeypatch it. To avoid mutating the real
./prompts folder, each test points prompt_store at a temp dir via its default.
"""

import shutil
import sys
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_ROOT / "scripts"))

APP_PATH = str(_ROOT / "app.py")


@pytest.fixture
def isolated_prompts(tmp_path, monkeypatch):
    """Redirect prompt_store's default dir to a temp copy of ./prompts."""
    import prompt_store as ps

    temp_prompts = tmp_path / "prompts"
    shutil.copytree(_ROOT / "prompts", temp_prompts)
    monkeypatch.setattr(ps, "_DEFAULT_PROMPTS_DIR", temp_prompts)
    return temp_prompts


def test_app_renders_checkbox_per_site(isolated_prompts):
    at = AppTest.from_file(APP_PATH).run()
    assert not at.exception
    labels = {cb.label for cb in at.checkbox}
    assert "NYS Incorporation" in labels
    assert "NYS Department of Taxation and Finance" in labels
    assert "NYS Department of State UCC Search" in labels
    # System prompt and task1 are never checkboxes.
    assert "systemPrompt" not in labels
    assert "task1" not in labels


def test_get_report_without_selection_warns(isolated_prompts):
    at = AppTest.from_file(APP_PATH).run()
    # Click "Get report" with nothing selected.
    report_btn = [b for b in at.button if b.label == "Get report"][0]
    report_btn.click().run()
    assert not at.exception
    assert any("at least one source" in w.value for w in at.warning)


def test_edit_system_prompt_persists(isolated_prompts):
    import prompt_store as ps

    at = AppTest.from_file(APP_PATH).run()
    at.text_area(key="edit_system_prompt").set_value("NEW SYSTEM RULES").run()
    save_btn = [b for b in at.button if b.proto.label == "Save system prompt"][0]
    save_btn.click().run()
    assert not at.exception
    assert ps.get_system_prompt().strip() == "NEW SYSTEM RULES"


def test_add_source_creates_checkbox(isolated_prompts):
    at = AppTest.from_file(APP_PATH).run()
    at.text_input(key="new_source_name").set_value("Brand New Site").run()
    add_btn = [b for b in at.button if b.proto.label == "Add source"][0]
    add_btn.click().run()
    assert not at.exception
    labels = {cb.label for cb in at.checkbox}
    assert "Brand New Site" in labels


def test_get_report_runs_with_mocked_agent(isolated_prompts, monkeypatch):
    # Patch the agent module so no live run happens.
    import bu

    monkeypatch.setattr(bu, "run_report", lambda task: f"MOCK REPORT for len={len(task)}")

    at = AppTest.from_file(APP_PATH).run()
    # Select the first site.
    at.checkbox[0].check().run()
    report_btn = [b for b in at.button if b.label == "Get report"][0]
    report_btn.click().run()
    assert not at.exception
    assert any("MOCK REPORT" in md.value for md in at.markdown)
