"""
Agent System Initialization

Handles:
- System startup
- State restoration from DB
- Agent spawning
- Background tasks
"""

import asyncio
import logging

from app.agents.orchestrator import OrchestratorAgent, orchestrator_agent
from app.agents.conversation import ConversationAgent
from app.services.scheduler_service import scheduler_service
from app.models.database import db

logger = logging.getLogger(__name__)


async def initialize_agent_system():
    """
    Initialize the complete agent system.
    
    Called on FastAPI startup.
    
    Steps:
    1. Initialize orchestrator
    2. Load state from DB
    3. Restore conversation agents
    4. Start background tasks
    """
    logger.info("initializing_agent_system")
    
    # 1. Create orchestrator
    from app.agents import orchestrator as orch_module
    
    orch_module.orchestrator_agent = OrchestratorAgent()
    
    # 2. Load state from DB (restores everything)
    await orch_module.orchestrator_agent.initialize()
    
    logger.info(f"agent_system_initialized: agents={len(orch_module.orchestrator_agent.state.spawned_agents)}")
    
    return orch_module.orchestrator_agent


async def shutdown_agent_system():
    """
    Graceful shutdown.
    
    Saves all state to DB.
    """
    logger.info("shutting_down_agent_system")
    
    if orchestrator_agent:
        # Save orchestrator state
        await orchestrator_agent.state.save_to_db()
        
        # Save all conversation agent states
        for agent in orchestrator_agent.state.spawned_agents.values():
            await agent.state.save_to_db()
    
    logger.info("agent_system_shutdown_complete")

