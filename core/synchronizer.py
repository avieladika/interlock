from datetime import datetime, timezone
import json
import os
import shutil
import asyncio
from typing import Optional, Callable, Dict, Any

from core.mcp_Manager import MCPManager
from core.phases.phase1 import Phase1Service
from core.phases.phase1_5.Phase1_5Service import Phase1_5Service
from core.phases.phase2 import Phase2Service
from core.phases.phase3.Phase3Service import Phase3Service
from core.phases.phase4.Phase4Service import Phase4Service
from core.models.phase1_5models.ContextArtifact import ContextArtifact
from core.models.phase2models.RequirementsArtifact import RequirementsArtifact
from core.models.phase3models.PlanArtifact import PlanArtifact
from core.models.phase4models.CodeChangeArtifact import ExecutionArtifact

from core.synthesizers.phase1_5synthesizers.ContextSynthesizer import ContextSynthesizer
from core.synthesizers.phase2synthesizers import (
    RequirementsSynthesizer,
    ConfluencePlanSynthesizer,
)
from core.synthesizers.phase3synthesizers.PlanSynthesizer import PlanSynthesizer
from core.synthesizers.phase4synthesizers.CodeSynthesizer import CodeSynthesizer
from core.utils.knowledge_base import KnowledgeBase
from core.utils.git_manager import GitManager


class InterlockSynchronizer:
    def __init__(self):
        # print("DEBUG: Initializing MCPManager...")
        self.mcp = MCPManager()

        self.allowed_confluence_spaces = {"ENG", "ARCH", "INT"}
        self.default_confluence_expand = "body.storage"

        # --- Data Directories ---
        # Use absolute path relative to project root
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        
        # Define .data directory
        self.data_dir = os.path.join(project_root, ".data")
        
        # Define subdirectories
        self.sources_dir = os.path.join(self.data_dir, "sources")
        self.github_dir = os.path.join(self.sources_dir, "github_repo")
        self.confluence_dir = os.path.join(self.sources_dir, "confluence_docs")
        self.chroma_dir = os.path.join(self.data_dir, "chroma_db")
        
        # Ensure dirs exist
        os.makedirs(self.confluence_dir, exist_ok=True)
        os.makedirs(self.chroma_dir, exist_ok=True)
        
        # print(f"DEBUG: Data directory set to: {self.data_dir}")
        
        # print("DEBUG: Initializing KnowledgeBase...")
        self.kb = KnowledgeBase(persist_dir=self.chroma_dir)
        
        # LLM roles
        self.context_synthesizer = ContextSynthesizer()
        self.requirements_synthesizer = RequirementsSynthesizer()
        self.confluence_planner = ConfluencePlanSynthesizer()
        self.plan_synthesizer = PlanSynthesizer()
        self.code_synthesizer = CodeSynthesizer()

        # Phase services
        self.phase1 = Phase1Service(mcp_manager=self.mcp)
        self.phase1_5 = Phase1_5Service(mcp=self.mcp, context_synthesizer=self.context_synthesizer)
        self.phase2 = Phase2Service(
            mcp=self.mcp,
            requirements_synthesizer=self.requirements_synthesizer,
            confluence_planner=self.confluence_planner,
            allowed_confluence_spaces=self.allowed_confluence_spaces,
            default_confluence_expand=self.default_confluence_expand,
            knowledge_base=self.kb,
            confluence_output_dir=self.confluence_dir
        )
        self.phase3 = Phase3Service(
            plan_synthesizer=self.plan_synthesizer,
            knowledge_base=self.kb
        )
        self.phase4 = Phase4Service(
            code_synthesizer=self.code_synthesizer
        )

        self.last_sync_timestamp = datetime.now(timezone.utc)

    async def run_sync_cycle(
        self, 
        ticket_key: str, 
        status_callback: Optional[Callable[[str], None]] = None,
        user_inputs: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        Runs the full sync cycle.
        """
        def log(msg: str):
            print(msg)
            if status_callback:
                status_callback(msg)

        log(f"🕒 Sync cycle started at: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}")
        
        results = {
            "context": None,
            "requirements": None,
            "plan": None,
            "execution": None
        }

        try:
            # --- Phase 1: Infrastructure ---
            log("🔍 [Phase 1] Validating infrastructure...")
            await self.phase1.run()
            log("✅ Phase 1 Passed: Infrastructure is ready.")
            log("-" * 40)

            # --- Phase 1.5: Context Discovery ---
            log("🕵️ [Phase 1.5] Discovering context...")
            context_artifact: ContextArtifact = await self.phase1_5.run(ticket_key)
            results["context"] = context_artifact
            
            if not context_artifact.is_usable():
                log("🛑 Stopping cycle: Context discovery failed.")
                return results
            
            log(f"   🎯 Target Branch: {context_artifact.target_branch}")
            log(f"   📚 Confluence Space: {context_artifact.confluence_space_key}")
            log("-" * 40)

            # --- Intermediate Step: Git Clone/Checkout & Indexing ---
            repo_url = os.getenv("GITHUB_REPO_URL")
            if repo_url:
                log(f"🔄 [Git] Syncing repo from {repo_url}...")
                git_mgr = GitManager(repo_url=repo_url, local_path=self.github_dir)
                
                # 1. Clone/Fetch
                await asyncio.to_thread(git_mgr.ensure_repo)
                
                # 2. Checkout Target Branch
                await asyncio.to_thread(git_mgr.checkout_branch, context_artifact.target_branch)
                
                # 3. Index Code
                log(f"📚 [Indexing] Indexing code from {self.github_dir}...")
                self.kb.index_codebase(self.github_dir)
                log("✅ Code indexing complete.")
            else:
                log("⚠️ GITHUB_REPO_URL not set. Skipping Git sync & indexing.")

            # --- Phase 2: Requirements ---
            log(f"🚀 [Phase 2] Collecting evidence & generating requirements for {ticket_key}...")
            requirements_artifact: RequirementsArtifact = await self.phase2.run(
                ticket_key, 
                context_artifact=context_artifact
            )
            results["requirements"] = requirements_artifact

            self._print_artifact_summary(requirements_artifact, log)

            if not requirements_artifact.is_usable():
                log("🛑 Stopping cycle: Requirements are not usable.")
                return results

            # --- Phase 3: Planning ---
            log("-" * 40)
            log(f"🚀 [Phase 3] Generating technical plan for {ticket_key}...")
            plan_artifact: PlanArtifact = await self.phase3.run(requirements_artifact)
            results["plan"] = plan_artifact

            self._print_plan_summary(plan_artifact, log)

            if not plan_artifact.is_usable():
                log("🛑 Stopping cycle: Plan is not usable.")
                return results

            # --- Phase 4: Execution (Code Generation) ---
            log("-" * 40)
            log(f"🚀 [Phase 4] Executing plan (generating code) for {ticket_key}...")
            execution_artifact: ExecutionArtifact = await self.phase4.run(plan_artifact, requirements_artifact)
            results["execution"] = execution_artifact

            self._print_execution_summary(execution_artifact, log)
            
            return results

        except Exception as e:
            log(f"❌ Sync cycle failed: {str(e)}")
            raise e

        finally:
            self.last_sync_timestamp = datetime.now(timezone.utc)
            log("-" * 40)
            log("✅ Sync cycle completed.")

    async def shutdown(self):
        print("🛑 Shutting down Interlock Synchronizer...")
        await self.mcp.shutdown()

    def _print_artifact_summary(self, artifact: RequirementsArtifact, log_fn):
        ticket_id = getattr(artifact, "ticket_id", "UNKNOWN")
        ac = getattr(artifact, "acceptance_criteria", []) or []
        unknowns = getattr(artifact, "unknowns", []) or []
        requirements = getattr(artifact, "requirements", []) or []

        log_fn(f"📊 Requirements Results for {ticket_id}:")
        log_fn(f"   - Requirements: {len(requirements)}")
        log_fn(f"   - Acceptance Criteria: {len(ac)}")
        log_fn(f"   - Unknowns identified: {len(unknowns)}")

        if hasattr(artifact, "is_usable") and callable(getattr(artifact, "is_usable")) and not artifact.is_usable():
            log_fn("🚩 GATE CLOSED: Requirements incomplete. Need more context.")
        else:
            log_fn("🟢 GATE OPEN: Requirements are clear. Moving to Phase 3.")

    def _print_plan_summary(self, plan: PlanArtifact, log_fn):
        log_fn(f"📊 Plan Results for {plan.ticket_id}:")
        log_fn(f"   - Goal: {plan.goal}")
        log_fn(f"   - Steps: {len(plan.steps)}")
        log_fn(f"   - Risks: {len(plan.risks)}")

    def _print_execution_summary(self, artifact: ExecutionArtifact, log_fn):
        success_count = sum(1 for r in artifact.results if r.status == "success")
        failed_count = sum(1 for r in artifact.results if r.status == "failed")
        
        log_fn(f"\n📊 Execution Results for {artifact.ticket_id}:")
        log_fn(f"   - Steps Executed: {success_count}")
        log_fn(f"   - Steps Failed: {failed_count}")
        
        if failed_count > 0:
            log_fn("🚩 GATE CLOSED: Some steps failed execution.")
        else:
            log_fn("🟢 GATE OPEN: All code generated successfully.")
