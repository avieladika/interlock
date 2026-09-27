import json
from typing import Protocol, List

from core.models.phase2models.RequirementsArtifact import RequirementsArtifact
from core.models.phase3models.PlanArtifact import PlanArtifact, PlanStep
from core.models.phase4models.CodeChangeArtifact import ExecutionArtifact, StepExecutionResult, FileChange
from core.utils import make_json_safe


class CodeSynthesizerProto(Protocol):
    async def generate_step_code(self, step: PlanStep, requirements: RequirementsArtifact) -> StepExecutionResult: ...


class Phase4Service:
    def __init__(
        self,
        code_synthesizer: CodeSynthesizerProto,
    ):
        self.code_synthesizer = code_synthesizer

    async def run(self, plan: PlanArtifact, requirements: RequirementsArtifact) -> ExecutionArtifact:
        """
        Executes Phase 4: Code Generation.
        Iterates over the plan steps and generates code for each relevant step.
        """
        print(f"🚀 Phase 4: Executing plan for {plan.ticket_id}...")

        results: List[StepExecutionResult] = []

        for step in plan.steps:
            print(f"   ▶ Executing Step {step.step_id}: {step.title} ({step.type})")

            if step.type in ["code", "configuration"]:
                # Generate code via LLM
                try:
                    # The synthesizer internally calls CodeIntegrityGate.validate
                    result = await self.code_synthesizer.generate_step_code(step, requirements)
                    results.append(result)
                    
                    if result.status == "failed":
                        print(f"     ❌ Generation failed: {result.logs}")
                    else:
                        # Print the generated code immediately
                        self._print_step_result(result)
                    
                except Exception as e:
                    print(f"❌ Step {step.step_id} failed: {e}")
                    results.append(StepExecutionResult(
                        step_id=step.step_id,
                        status="failed",
                        logs=str(e)
                    ))
            else:
                print(f"     ℹ Skipping non-code step (type: {step.type})")
                results.append(StepExecutionResult(
                    step_id=step.step_id,
                    status="skipped",
                    logs="Non-code step skipped."
                ))

        artifact = ExecutionArtifact(
            ticket_id=plan.ticket_id,
            results=results
        )

        self._print_execution_summary(artifact)
        return artifact

    def _print_step_result(self, result: StepExecutionResult):
        if not result.changes:
            print(f"     ℹ No code changes generated for step {result.step_id}.")
            return

        print(f"     ✅ Generated {len(result.changes)} file changes:")
        for change in result.changes:
            print(f"       📄 File: {change.file_path} ({change.action})")
            print("-" * 40)
            print(change.content)  # Print the full code content
            print("-" * 40)

    def _print_execution_summary(self, artifact: ExecutionArtifact):
        success_count = sum(1 for r in artifact.results if r.status == "success")
        failed_count = sum(1 for r in artifact.results if r.status == "failed")
        skipped_count = sum(1 for r in artifact.results if r.status == "skipped")

        print(f"\n📊 Phase 4 Execution Summary for {artifact.ticket_id}:")
        print(f"   - Steps Executed: {success_count}")
        print(f"   - Steps Failed: {failed_count}")
        print(f"   - Steps Skipped: {skipped_count}")
        
        if failed_count > 0:
            print("🚩 GATE CLOSED: Some steps failed execution.")
        else:
            print("🟢 GATE OPEN: All code generated successfully.")
