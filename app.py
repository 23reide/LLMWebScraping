import sys
from pathlib import Path

import streamlit as st

# Make the workspace-root modules importable (prompt_store) and the agent
# module in ./scripts (bu) available for Get Report.
_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_ROOT / "scripts"))

import prompt_store as ps

TASK_FILE = _ROOT / "outputs" / "_lastTask.txt"

st.title("Contractor Due Diligence Report Builder")

company_info_input = st.text_area(
    label="Input Company details from PassPort: "
    + "\n\n •\tthe vendor's EIN, address, the information disclosed on the company's disclosure form, the company's officers information (name, EIN, DOB, home address, position and percentage ownership in company)"
    + "\n\n •\tthe name and EIN of the parent company (if any) "
    + "\n\n •\tall subsidiary/affiliated companies listed on the vendor's Disclosure Form"
    + "\n\n •\tall companies disclosed by an officer of the subcontractor on their Principal Disclosure Form.",
    key="company_info",
)

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
    if not selected_sites:
        st.warning("Select at least one source before running a report.")
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
        for site in selected_sites:
            parts.append("")
            parts.append(ps.get_prompt(site).strip())
        task = "\n".join(parts).strip() + "\n"

        # Persist the exact task that will be run.
        TASK_FILE.parent.mkdir(parents=True, exist_ok=True)
        TASK_FILE.write_text(task, encoding="utf-8")

        import bu  # imported lazily so the UI loads even if deps are missing

        with st.spinner("Running the browser agent — this can take several minutes..."):
            try:
                result = bu.run_report(task)
                st.success("Report complete. Saved to ./outputs")
                st.subheader("Report")
                st.markdown(result)
            except Exception as exc:  # surface agent/runtime errors in the UI
                st.error(f"The report run failed: {exc}")

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
