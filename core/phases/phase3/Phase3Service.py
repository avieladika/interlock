import json
from typing import Protocol, Optional

from core.models.phase2models.RequirementsArtifact import RequirementsArtifact
from core.models.phase3models.PlanArtifact import PlanArtifact
from core.gates.phase3gates.gatePhase3 import PlanIntegrityGate  # ✅ Import Gate
from core.utils import make_json_safe
from core.utils.knowledge_base import KnowledgeBase


class PlanSynthesizerProto(Protocol):
    async def generate(self, requirements: RequirementsArtifact, code_context: Optional[str] = None) -> PlanArtifact: ...


class Phase3Service:
    def __init__(
        self,
        plan_synthesizer: PlanSynthesizerProto,
        knowledge_base: Optional[KnowledgeBase] = None,
    ):
        self.plan_synthesizer = plan_synthesizer
        self.kb = knowledge_base

    async def run(self, requirements: RequirementsArtifact) -> PlanArtifact:
        """
        Executes Phase 3: Technical Planning.
        Takes validated requirements and produces a step-by-step plan.
        """
        print(f"🚀 Phase 3: Generating technical plan for {requirements.ticket_id}...")

        # 1. Retrieve Context from RAG (if available)
        code_context = None
        if self.kb:
            print("   🔍 Querying Knowledge Base for relevant code context...")
            query = f"Find existing code, models, or utilities relevant to: {requirements.summary}"
            try:
                code_context = self.kb.query(query, k=5)
                print(f"   ✅ Retrieved context (length: {len(code_context)} chars)")
            except Exception as e:
                print(f"   ⚠️ Failed to query Knowledge Base: {e}")

        # 2. Generate Plan
        plan = await self.plan_synthesizer.generate(requirements, code_context=code_context)

        # 3. Validate Plan (Gate)
        # Extract requirement IDs for coverage check
        req_ids = [r.id for r in requirements.requirements]
        
        # We need to serialize to JSON for the Gate (as it expects raw JSON string currently)
        # Or we can refactor the Gate to accept the object. For now, let's serialize.
        plan_json = plan.model_dump_json()
        
        is_valid, msg = PlanIntegrityGate.validate(plan_json, requirements_ids=req_ids)
        
        if not is_valid:
            raise RuntimeError(f"❌ Phase 3 Gate Failed: {msg}")
        
        print(f"   🛡️ Gate Check: {msg}")

        # 4. Print Summary
        self._print_plan_summary(plan)

        return plan

    def _print_plan_summary(self, plan: PlanArtifact):
        print(f"📊 Plan Generated for {plan.ticket_id}:")
        print(f"   - Goal: {plan.goal}")
        print(f"   - Steps: {len(plan.steps)}")
        print(f"   - Risks identified: {len(plan.risks)}")
        
        print("\n📝 FULL PLAN JSON:")
        print(plan.model_dump_json(indent=2))
        
        print("🟢 GATE OPEN: Plan is ready. Moving to Phase 4 (Execution).")
