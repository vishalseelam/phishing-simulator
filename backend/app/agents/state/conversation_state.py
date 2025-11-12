"""
Conversation Agent State Management

Persistent state per conversation.
"""

from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from uuid import UUID
import logging

from app.models.database import db

logger = logging.getLogger(__name__)


@dataclass
class ConversationAgentState:
    """
    Persistent state for one conversation agent.
    
    Stored in: DB (conversations, messages, conversation_memory)
    """
    
    # Identity
    conversation_id: str
    phone_number: str
    campaign_id: str
    
    # Instructions (can be updated by orchestrator)
    instructions: str = ""
    strategy: str = "adaptive"
    goal: str = "click_link"
    
    # History (loaded from DB)
    message_history: List[Dict] = field(default_factory=list)
    employee_replies: List[Dict] = field(default_factory=list)
    
    # Status
    status: str = "active"  # "active", "engaged", "stalled", "completed", "abandoned"
    sentiment: str = "neutral"  # "suspicious", "engaged", "neutral", "confused", "hostile"
    trust_level: str = "low"  # "low", "medium", "high"
    engagement_level: float = 0.0  # 0-1
    
    # Memory (learning)
    conversation_memory: Dict = field(default_factory=lambda: {
        "successful_tactics": [],
        "failed_tactics": [],
        "response_times": [],
        "preferred_approach": None
    })
    
    # Counts
    message_count: int = 0
    reply_count: int = 0
    
    # Timestamps
    created_at: datetime = field(default_factory=datetime.now)
    last_activity: datetime = field(default_factory=datetime.now)
    
    @classmethod
    async def load_from_db(cls, conversation_id: str) -> 'ConversationAgentState':
        """
        Load state from database.
        
        Used on system restart to restore agents.
        """
        # Load conversation
        conversation = await db.get_conversation(UUID(conversation_id))
        
        if not conversation:
            raise ValueError(f"Conversation {conversation_id} not found")
        
        # Load recipient
        async with db.pool.acquire() as conn:
            recipient = await conn.fetchrow("""
                SELECT phone_number FROM recipients WHERE id = $1
            """, conversation['recipient_id'])
        
        # Load messages
        messages = await db.get_conversation_messages(UUID(conversation_id))
        
        # Separate agent and employee messages
        agent_messages = [m for m in messages if m['sender'] == 'agent']
        employee_messages = [m for m in messages if m['sender'] == 'employee']
        
        # Load conversation memory
        memory = await db.get_conversation_memory(UUID(conversation_id))
        
        # Parse config
        config = {}
        if conversation.get('config'):
            try:
                import json
                config = json.loads(conversation['config']) if isinstance(conversation['config'], str) else conversation['config']
            except:
                config = {}
        
        # Create state
        state = cls(
            conversation_id=conversation_id,
            phone_number=recipient['phone_number'] if recipient else "unknown",
            campaign_id=str(conversation['campaign_id']),
            instructions=config.get('instructions', ''),
            strategy=conversation.get('current_strategy', 'adaptive'),
            goal=config.get('goal', 'click_link'),
            message_history=messages,
            employee_replies=employee_messages,
            status=conversation.get('state', 'active'),
            sentiment=conversation.get('sentiment', 'neutral'),
            trust_level=conversation.get('trust_level', 'low'),
            message_count=len(agent_messages),
            reply_count=len(employee_messages),
            created_at=conversation.get('started_at', datetime.now()),
            last_activity=conversation.get('last_activity_at', datetime.now())
        )
        
        if memory:
            state.conversation_memory = memory
        
        logger.info(f"conversation_state_loaded: conv_id={conversation_id}, messages={len(messages)}")
        
        return state
    
    async def save_to_db(self):
        """Sync state to database."""
        import json
        
        # Update conversation
        await db.update_conversation(
            conversation_id=UUID(self.conversation_id),
            state=self.status,
            current_strategy=self.strategy,
            sentiment=self.sentiment,
            trust_level=self.trust_level,
            message_count=self.message_count,
            reply_count=self.reply_count,
            last_activity_at=self.last_activity,
            config=json.dumps({
                'instructions': self.instructions,
                'goal': self.goal
            })
        )
        
        # Update conversation memory (if table has data)
        try:
            await db.update_conversation_memory(
                conversation_id=UUID(self.conversation_id),
                **self.conversation_memory
            )
        except:
            pass  # Memory table might not have entry yet
        
        logger.debug(f"conversation_state_saved: conv_id={self.conversation_id}")

