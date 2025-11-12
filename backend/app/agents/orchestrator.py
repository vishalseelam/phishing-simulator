"""
Orchestrator Agent - Master AI Agent

Responsibilities:
- Converse with admin to create campaigns
- Spawn conversation agents
- Coordinate system
- Provide telemetry

Stateful: Survives restarts, loads from DB
"""

from datetime import datetime
from typing import Dict, List, Optional
import asyncio
import logging

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

from app.agents.state.orchestrator_state import OrchestratorState
from app.agents.tools.creation_tools import (
    create_campaign_async,
    add_recipient_to_campaign,
    set_orchestrator
)
from app.models.database import db
from config import settings

logger = logging.getLogger(__name__)


ORCHESTRATOR_SYSTEM_PROMPT = """You are GhostEye Orchestrator - the master AI managing phishing simulations.

YOUR ROLE:
You help admins create and manage phishing campaigns through natural conversation.

WORKFLOW FOR NEW CAMPAIGN:
1. Admin says: "Create [topic] campaign" or "Add phishing for [topic]"
2. You gather:
   - Topic (what the phishing is about)
   - Phone numbers (who to target)
   - Messages (generate or admin provides)
3. You show PLAN with all details
4. You get explicit APPROVAL ("yes")
5. You call create_campaign_async tool

TOOLS:
- create_campaign_async(topic, phone_numbers, generate_messages, custom_messages, strategy)
  Use this to CREATE NEW campaigns
  
- add_recipient_to_campaign(campaign_id, phone_number, custom_message)
  Use this to ADD to EXISTING campaigns (only if admin explicitly says "add to campaign X")

CRITICAL RULES:
1. When admin provides topic + phone numbers → This is a NEW campaign
2. ALWAYS call create_campaign_async for new campaigns (don't ask for campaign_id)
3. Only use add_recipient_to_campaign if admin explicitly mentions existing campaign
4. SHOW PLAN before executing
5. GET "yes" approval before calling tools

EXAMPLE CONVERSATION:
Admin: "Create phishing campaign"
You: "Sure! What's the topic? (e.g., password reset, account verification)"

Admin: "password reset"
You: "Got it. How many employees should I target? Provide phone numbers."

Admin: "+15555551001, +15555551002, +15555551003"
You: "Perfect, 3 recipients. Should I:
      1. Generate phishing messages (I'll create realistic ones)
      2. You provide the messages
      
      Type 1 or 2"

Admin: "1"
You: "Excellent. Here's the plan:
      
      📋 CAMPAIGN PLAN:
      - Topic: Password reset
      - Recipients: 3 employees
      - Messages: LLM-generated (realistic phishing)
      - Strategy: Adaptive
      - Scheduling: Human-realistic timing with burst-and-pause
      - Expected: ~50 messages/day capacity
      
      Approve? (yes/no)"

Admin: "yes"
You: [Calls create_campaign_async tool]
     [Shows progress updates]
     "✅ Campaign created! 3 conversations active, messages scheduled."

REMEMBER:
- You are autonomous but conversational
- Always get approval before executing
- Provide progress updates during long operations
- Explain what's happening in the system
"""


class OrchestratorAgent:
    """
    Master orchestrator agent.
    
    Stateful, persistent, autonomous.
    """
    
    def __init__(self):
        """Initialize orchestrator agent."""
        # State (persistent)
        self.state = OrchestratorState()
        
        # LLM
        self.llm = ChatOpenAI(
            model=settings.llm_model,
            api_key=settings.openai_api_key,
            temperature=0.7
        )
        
        # Tools
        self.tools = [
            create_campaign_async,
            add_recipient_to_campaign
        ]
        
        # Bind tools to LLM
        self.llm_with_tools = self.llm.bind_tools(self.tools)
        
        # Set global reference for tools
        set_orchestrator(self)
        
        # Progress callback (for async operations)
        self.progress_callback = None
        
        logger.info("orchestrator_agent_initialized")
    
    async def initialize(self):
        """
        Initialize agent (load state from DB).
        
        Call this on system startup.
        """
        await self.state.load_from_db()
        
        # Restore conversation agents
        await self._restore_conversation_agents()
        
        logger.info(f"orchestrator_initialized: campaigns={len(self.state.active_campaigns)}, agents={len(self.state.spawned_agents)}")
    
    async def _restore_conversation_agents(self):
        """
        Restore conversation agents from DB on startup.
        """
        from app.agents.conversation import ConversationAgent
        
        # Get all active conversations
        if not db.pool:
            return
        
        async with db.pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT id FROM conversations
                WHERE state NOT IN ('completed', 'abandoned')
            """)
        
        for row in rows:
            conv_id = str(row['id'])
            
            try:
                # Restore agent
                agent = await ConversationAgent.restore_from_db(conv_id)
                self.state.spawned_agents[conv_id] = agent
                
                logger.info(f"agent_restored: conv_id={conv_id}")
            
            except Exception as e:
                logger.error(f"agent_restore_failed: conv_id={conv_id}, error={str(e)}")
        
        logger.info(f"agents_restored: count={len(self.state.spawned_agents)}")
    
    async def process_admin_message(self, message: str) -> str:
        """
        Main entry point for admin interaction.
        
        Fully autonomous conversation with tool calling.
        """
        logger.info(f"admin_message_received: length={len(message)}")
        
        # Add to history
        self.state.admin_history.append({
            "role": "admin",
            "content": message,
            "timestamp": datetime.now().isoformat()
        })
        
        # Save to DB
        if db.pool:
            async with db.pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO admin_messages (role, content, timestamp)
                    VALUES ($1, $2, $3)
                """, "admin", message, datetime.now())
        
        # Build message history for LLM
        messages = [SystemMessage(content=ORCHESTRATOR_SYSTEM_PROMPT)]
        
        # Add recent history (last 20 messages)
        for msg in self.state.admin_history[-20:]:
            if msg['role'] == 'admin':
                messages.append(HumanMessage(content=msg['content']))
            else:
                messages.append(AIMessage(content=msg['content']))
        
        # Add current message
        messages.append(HumanMessage(content=message))
        
        # Call LLM with tools
        try:
            response = await self.llm_with_tools.ainvoke(messages)
            
            # Execute tools if LLM called them
            if response.tool_calls:
                for tool_call in response.tool_calls:
                    tool_name = tool_call['name']
                    tool_args = tool_call['args']
                    
                    logger.info(f"tool_called: tool={tool_name}")
                    
                    # Execute tool
                    if tool_name == 'create_campaign_async':
                        result = await create_campaign_async.ainvoke(tool_args)
                        response.content = result
                    
                    elif tool_name == 'add_recipient_to_campaign':
                        result = await add_recipient_to_campaign.ainvoke(tool_args)
                        response.content = result
                    
                    # Telemetry
                    self.state.add_trace("tool_executed", {
                        "tool": tool_name,
                        "args": tool_args
                    })
            
            # Add response to history
            self.state.admin_history.append({
                "role": "agent",
                "content": response.content,
                "timestamp": datetime.now().isoformat()
            })
            
            # Save to DB
            if db.pool:
                async with db.pool.acquire() as conn:
                    await conn.execute("""
                        INSERT INTO admin_messages (role, content, timestamp)
                        VALUES ($1, $2, $3)
                    """, "agent", response.content, datetime.now())
            
            # Periodic state sync
            await self.state.save_to_db()
            
            return response.content or "I'm ready to help. What would you like to do?"
        
        except Exception as e:
            logger.error(f"orchestrator_error: {str(e)}")
            return f"❌ Error: {str(e)}\n\nPlease try again or rephrase."
    
    async def send_progress(self, message: str):
        """
        Send progress update to admin during async operations.
        
        Called by tools during long-running operations.
        """
        if self.progress_callback:
            await self.progress_callback(message)
        
        logger.info(f"progress_update: {message}")
    
    def set_progress_callback(self, callback):
        """Set callback for progress updates."""
        self.progress_callback = callback
    
    async def update_agent_context(
        self,
        conversation_id: str,
        new_instructions: str = None,
        new_strategy: str = None
    ):
        """
        Update context for a specific conversation agent.
        
        Can be called by admin through tool or directly.
        """
        agent = self.state.spawned_agents.get(conversation_id)
        
        if not agent:
            return {"error": "Agent not found"}
        
        # Update agent
        if new_instructions:
            agent.instructions = new_instructions
        
        if new_strategy:
            agent.strategy = new_strategy
        
        # Update in DB
        await db.update_conversation(
            conversation_id=UUID(conversation_id),
            current_strategy=new_strategy,
            config={'instructions': new_instructions}
        )
        
        # Update state
        if conversation_id in self.state.agent_contexts:
            if new_instructions:
                self.state.agent_contexts[conversation_id]['instructions'] = new_instructions
            if new_strategy:
                self.state.agent_contexts[conversation_id]['strategy'] = new_strategy
        
        logger.info(f"agent_context_updated: conv_id={conversation_id}")
        
        return {"updated": True}
    
    def get_metrics(self) -> Dict:
        """Get current system metrics."""
        return {
            "metrics": self.state.metrics,
            "active_campaigns": len(self.state.active_campaigns),
            "spawned_agents": len(self.state.spawned_agents),
            "uptime": (datetime.now() - self.state.initialized_at).total_seconds()
        }


# Global orchestrator instance
orchestrator_agent: Optional[OrchestratorAgent] = None

