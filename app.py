import asyncio
import streamlit as st
import os
from dotenv import load_dotenv

# Load env vars
load_dotenv()

from core.synchronizer import InterlockSynchronizer
from core.models.phase4models.CodeChangeArtifact import ExecutionArtifact
from core.models.phase2models.RequirementsArtifact import RequirementsArtifact
from core.models.phase3models.PlanArtifact import PlanArtifact

# Page Config
st.set_page_config(
    page_title="Interlock System",
    page_icon="🚀",
    layout="wide"
)

st.title("🚀 Interlock System")
st.markdown("### Autonomous Development Agent")
st.info("ℹ️ Note: When running, please check your terminal for interactive questions (Space/Branch).")

# Sidebar for settings
with st.sidebar:
    st.header("Settings")
    ticket_id = st.text_input("Jira Ticket ID", value="CKM-1")
    st.info("Ensure your .env file is configured correctly.")

# Main Area
if st.button("Run Sync Cycle", type="primary"):
    if not ticket_id:
        st.error("Please enter a Ticket ID.")
    else:
        # Create tabs for different phases
        tab_logs, tab_req, tab_plan, tab_code = st.tabs(["📜 Logs", "📋 Requirements", "🗺️ Plan", "💻 Code"])

        with tab_logs:
            log_container = st.empty()
            logs = []

        def update_logs(msg):
            logs.append(msg)
            log_container.code("\n".join(logs), language="bash")

        async def run_process():
            engine = None
            try:
                with st.spinner("Running... (Check terminal for inputs!)"):
                    engine = InterlockSynchronizer()
                    st.toast("Engine Initialized! Check terminal if it hangs.")
                
                    # Run the cycle (no user_inputs passed, so it will ask in terminal)
                    results = await engine.run_sync_cycle(
                        ticket_key=ticket_id, 
                        status_callback=update_logs
                    )
                    return results
            except Exception as e:
                st.error(f"Error: {str(e)}")
                return None
            finally:
                if engine:
                    await engine.shutdown()

        # Run Asyncio loop
        results = asyncio.run(run_process())

        # Display Results in Tabs
        if results:
            # --- Requirements Tab ---
            with tab_req:
                req_artifact = results.get("requirements")
                if req_artifact and isinstance(req_artifact, RequirementsArtifact):
                    st.header("Requirements Analysis")
                    st.markdown(f"**Ticket:** `{req_artifact.ticket_id}`")
                    st.markdown(f"**Summary:** {req_artifact.summary}")
                    
                    st.subheader("Requirements List")
                    for req in req_artifact.requirements:
                        with st.expander(f"{req.id}: {req.statement}"):
                            st.markdown(f"**Type:** `{req.type}`")
                            if req.sources:
                                st.markdown("**Sources:**")
                                for src in req.sources:
                                    st.markdown(f"- [{src.type}] {src.ref}: *{src.excerpt}*")
                    
                    st.subheader("Acceptance Criteria")
                    for ac in req_artifact.acceptance_criteria:
                        st.markdown(f"- **{ac.id}:** {ac.description} (Automated: `{ac.is_automated}`)")
                    
                    if req_artifact.unknowns:
                        st.error("Unknowns / Missing Info:")
                        for unk in req_artifact.unknowns:
                            st.markdown(f"- {unk}")
                    
                    with st.expander("View Full JSON"):
                        st.json(req_artifact.model_dump())
                else:
                    st.info("No requirements generated yet.")

            # --- Plan Tab ---
            with tab_plan:
                plan_artifact = results.get("plan")
                if plan_artifact and isinstance(plan_artifact, PlanArtifact):
                    st.header("Technical Plan")
                    st.markdown(f"**Goal:** {plan_artifact.goal}")
                    
                    st.subheader("Steps")
                    for step in plan_artifact.steps:
                        st.markdown(f"#### {step.step_id}: {step.title}")
                        st.markdown(f"_{step.description}_")
                        st.markdown(f"**Type:** `{step.type}` | **Linked Req:** `{step.linked_requirement_id}`")
                        if step.file_paths:
                            st.markdown(f"**Files:** `{', '.join(step.file_paths)}`")
                        st.divider()
                    
                    if plan_artifact.risks:
                        st.warning("Risks Identified:")
                        for risk in plan_artifact.risks:
                            st.markdown(f"- {risk}")

                    with st.expander("View Full JSON"):
                        st.json(plan_artifact.model_dump())
                else:
                    st.info("No plan generated yet.")

            # --- Code Tab ---
            with tab_code:
                exec_artifact = results.get("execution")
                if exec_artifact and isinstance(exec_artifact, ExecutionArtifact):
                    st.header("Execution Results")
                    
                    # Metrics
                    col1, col2, col3 = st.columns(3)
                    success_count = sum(1 for r in exec_artifact.results if r.status == "success")
                    failed_count = sum(1 for r in exec_artifact.results if r.status == "failed")
                    
                    col1.metric("Total Steps", len(exec_artifact.results))
                    col2.metric("Success", success_count)
                    col3.metric("Failed", failed_count, delta_color="inverse")

                    # Show Code Changes
                    st.subheader("Generated Code")
                    for step in exec_artifact.results:
                        with st.expander(f"Step {step.step_id}: {step.status.upper()}", expanded=(step.status == "failed")):
                            if step.logs:
                                st.text("Logs/Reasoning:")
                                st.info(step.logs)
                            
                            if step.changes:
                                for change in step.changes:
                                    st.markdown(f"**File:** `{change.file_path}` ({change.action})")
                                    st.code(change.content, language="python")
                            else:
                                st.warning("No code changes generated.")
                    
                    with st.expander("View Full JSON"):
                        st.json(exec_artifact.model_dump())
                else:
                    st.info("No code generated yet.")
