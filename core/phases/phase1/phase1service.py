from core.gates.phase1gates.gatePhase1 import ConnectivityGate
from core.phases.phase1.mcpBootstrapper import MCPBootstrapper


class Phase1Service:
    """
    Phase 1 service:
    - run ConnectivityGate
    - boot MCP if needed
    """

    def __init__(self, mcp_manager):
        self.gate = ConnectivityGate()
        self.bootstrapper = MCPBootstrapper(mcp_manager)

    async def run(self) -> None:
        """
        Raises RuntimeError if phase 1 fails.
        """
        if not self.gate.validate_all_connections():
            raise RuntimeError("Phase 1 failed: ConnectivityGate blocked.")

        await self.bootstrapper.ensure_atlassian_connected()
