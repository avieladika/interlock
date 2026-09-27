import sys
import asyncio
from pathlib import Path
from dotenv import load_dotenv

# Explicitly find the .env file in the parent directory
env_path = Path(__file__).resolve().parent.parent / '.env'
load_dotenv(dotenv_path=env_path)

from core.synchronizer import InterlockSynchronizer


async def run_app():
    """
    Main entry point for the Interlock System.
    """
    # Initialize the engine
    engine = InterlockSynchronizer()

    print("🚀 Interlock System Initialized")
    print("-" * 40)

    try:
        ticket_to_analyze = "CKM-1"
        await engine.run_sync_cycle(ticket_key=ticket_to_analyze)

    except Exception as e:
        print(f"❌ Critical Error: {str(e)}")
        sys.exit(1)
    
    finally:
        # Ensure resources are cleaned up properly
        await engine.shutdown()


if __name__ == "__main__":
    try:
        asyncio.run(run_app())
    except KeyboardInterrupt:
        print("\n🛑 Execution stopped by user.")
