import os
import sys
from pathlib import Path

import streamlit as st

# Make the workspace-root modules importable (prompt_store) and the agent
# module in ./scripts (bu) available for Get Report.
_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_ROOT / "scripts"))

import prompt_store as ps
import new_nys_dos_search import search_nys_dos

TASK_FILE = _ROOT / "outputs" / "_lastTask.txt"

MODEL_SITES = {"NYS Incorporation": search_nys_dos}

st.title("Contractor Due Diligence Report Builder")

company_info_input = st.text_area(
    label="Input Company details from PassPort: "
    + "\n\n •\tthe vendor's EIN, address, the information disclosed on the company's disclosure form, the company's officers information (name, EIN, DOB, home address, position and percentage ownership in company)"
    + "\n\n •\tthe name and EIN of the parent company (if any) "
    + "\n\n •\tall subsidiary/affiliated companies listed on the vendor's Disclosure Form"
    + "\n\n •\tall companies disclosed by an officer of the subcontractor on their Principal Disclosure Form.",
    key="company_info",
)

company_name = st.text_input("Company name (for module searches)", key="company_name")

# --- Site selection checkboxes (derived from ./prompts) ---------------------
sites = ps.list_sites()

if not sites:
    st.info("No sources yet. Add one in 'Edit prompts / websites' below.")

selected_sites = []
for site in sites:
    if st.checkbox(label=site, key="check_" + site):
        selected_sites.append(site)

# --- Get Report -------------------------------------------------------------
if st.button(label="Get report"):
    module_sites = [s for s in selected_sites if s in MODULE_SITES]
    agent_sites = [s for s in selected_sites if s not in MODULE_SITES]

    if not selected_sites:
        st.warning("Select at least one source before running a report.")
    elif module_sites and not company_name.strip():
        st.warning("Enter a company name for the module searches.")
    else:
        # Concatenate: system prompt, then each checked site's prompt, then the
        # company-info text area, with clear separators.
        parts = [ps.get_system_prompt().strip(), ""]
        company_info = st.session_state.get("company_info", "").strip()
        if company_info:
            parts.append("")
            parts.append("Company details:")
            parts.append(company_info)
        parts.append("Websites:")
        for site in agent_sites:
            parts.append("")
            parts.append(ps.get_prompt(site).strip())
        task = "\n".join(parts).strip() + "\n"

        # Persist the exact task that will be run.
        TASK_FILE.parent.mkdir(parents=True, exist_ok=True)
        TASK_FILE.write_text(task, encoding="utf-8")

        import bu  # imported lazily so the UI loads even if deps are missing

        # Resolve the Google API key: prefer Streamlit secrets (set in
        # .streamlit/secrets.toml locally, or the app's Secrets box when
        # deployed), then fall back to the environment / .env for plain local
        # runs. Passing it explicitly means the key is found when published,
        # where .env files are not available.
        google_api_key = None
        try:
            google_api_key = st.secrets.get("GOOGLE_API_KEY")
        except Exception:
            # st.secrets raises if no secrets file exists; fall back to env.
            google_api_key = None
        if not google_api_key:
            google_api_key = os.environ.get("GOOGLE_API_KEY")

        if not google_api_key:
            st.error(
                "No Google API key found. Add GOOGLE_API_KEY to "
                ".streamlit/secrets.toml (or the app's Secrets when deployed)."
            )
            st.stop()

        os.environ["GOOGLE_API_KEY"] = google_api_key
        for s in module_sites:
            st.subheader(s)
            with st.spinner(f"Searching {s}..."):
                st.json(MODULE_SITES[s](company_name.strip()))

        if not agent_sites:
            st.stop()

        st.info("Running the browser agent — this can take several minutes...")

        # Run the agent on a background thread and stream its console output
        # (logging + stdout/stderr) into a live-updating area. This is all
        # in-process, so it behaves the same locally or on a hosted server.
        run = bu.start_report(task, api_key=google_api_key)

        st.subheader("Console output")
        # Fixed-height, scrollable box so long logs don't push the page down.
        log_box = st.container(height=320)
        log_area = log_box.empty()
        log_lines: list[str] = []

        # Keep only the tail so the page stays responsive on long runs.
        _MAX_LINES = 500

        def _render_logs() -> None:
            if log_lines:
                log_area.code("\n".join(log_lines[-_MAX_LINES:]), language="log")

        with st.spinner("Working..."):
            while run.is_alive():
                for line in run.stream(timeout=0.2):
                    log_lines.append(line)
                _render_logs()
            # Drain anything emitted between the last check and thread exit.
            for line in run.stream(timeout=0.2):
                log_lines.append(line)
            _render_logs()

        if run.error is not None:
            st.error(f"The report run failed: {run.error}")
        else:
            st.success("Report complete. Saved to ./outputs")
            st.subheader("Report")
            st.markdown(run.result or "")

            # Offer the full run folder (report text + all evidence) as a zip.
            # The zip is built to a temp file on disk (flat memory use even for
            # large screenshot sets), then handed to the download button so the
            # browser can fetch it — this works whether Streamlit runs locally
            # or on a hosted server where the files live on the server's disk.
            if run.run_dir is not None:
                import os as _os

                try:
                    zip_path = bu.zip_run_evidence(run.run_dir)
                    try:
                        with open(zip_path, "rb") as fh:
                            archive_bytes = fh.read()
                        st.download_button(
                            label="Download report + evidence (.zip)",
                            data=archive_bytes,
                            file_name=f"{run.run_dir.name}.zip",
                            mime="application/zip",
                        )
                        st.caption(f"Evidence saved on the server at: {run.run_dir}")
                    finally:
                        # The evidence stays in ./outputs; only the throwaway
                        # temp archive is removed.
                        try:
                            _os.remove(zip_path)
                        except OSError:
                            pass
                except Exception as exc:  # don't let packaging failure hide the report
                    st.warning(f"Could not package evidence for download: {exc}")

st.divider()

# --- Edit prompts / websites ------------------------------------------------
with st.expander(label="Edit prompts / websites"):
    # System prompt: always applied, editable, never deletable, no checkbox.
    st.subheader("System prompt (always applied)")
    system_text = st.text_area(
        label="This prompt is prepended to every report and cannot be deleted.",
        value=ps.get_system_prompt(),
        key="edit_system_prompt",
        height=160,
    )
    if st.button("Save system prompt", key="save_system_prompt"):
        ps.save_system_prompt(system_text)
        st.success("System prompt saved.")

    st.divider()

    # Add a new source.
    st.subheader("Add a source")
    new_name = st.text_input("New source name", key="new_source_name")
    if st.button("Add source", key="add_source"):
        name = (new_name or "").strip()
        if not name:
            st.warning("Enter a name for the new source.")
        else:
            try:
                ps.add_site(name)
                st.success(f"Added source '{name}'.")
                st.rerun()
            except ValueError as exc:
                st.warning(str(exc))

    st.divider()

    # Per-site prompt editors with delete controls.
    st.subheader("Sources")
    if not sites:
        st.caption("No sources yet.")
    for site in sites:
        col_edit, col_delete = st.columns([0.9, 0.1])
        with col_edit:
            with st.popover(label=site):
                prompt_text = st.text_area(
                    label="Edit prompt",
                    value=ps.get_prompt(site),
                    key="edit_" + site,
                    height=200,
                )
                if st.button("Save", key="save_" + site):
                    ps.save_prompt(site, prompt_text)
                    st.success(f"Saved prompt for '{site}'.")
        with col_delete:
            if st.button("🗑️", key="delete_" + site, help=f"Delete '{site}'"):
                ps.delete_site(site)
                st.rerun()
