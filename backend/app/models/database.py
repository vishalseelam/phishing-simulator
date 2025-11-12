"""
Database Layer - Supabase Integration

Provides async CRUD operations for all entities.
"""

from datetime import datetime
from typing import List, Optional, Dict, Any
from uuid import UUID
import logging

try:
    from supabase import create_client, Client
    HAS_SUPABASE = True
except ImportError:
    HAS_SUPABASE = False
    print("Warning: supabase not installed")

import asyncpg

from config import settings


logger = logging.getLogger(__name__)


class Database:
    """
    Database interface for GhostEye v2.
    
    Uses Supabase for convenience + asyncpg for performance.
    """
    
    def __init__(self):
        """Initialize database connections."""
        # Supabase client (for convenience methods)
        if HAS_SUPABASE:
            try:
                self.supabase: Client = create_client(
                    settings.supabase_url,
                    settings.supabase_key
                )
            except:
                self.supabase = None
        else:
            self.supabase = None
        
        # asyncpg pool (for high-performance async queries)
        self.pool: Optional[asyncpg.Pool] = None
        
        logger.info("database_initialized")
    
    async def connect(self):
        """Create asyncpg connection pool."""
        self.pool = await asyncpg.create_pool(
            settings.database_url,
            min_size=5,
            max_size=20,
            command_timeout=60
        )
        logger.info("database_pool_created")
    
    async def disconnect(self):
        """Close database connections."""
        if self.pool:
            await self.pool.close()
        logger.info("database_pool_closed")
    
    # ============================================================
    # CAMPAIGNS
    # ============================================================
    
    async def create_campaign(
        self,
        name: str,
        topic: str,
        strategy: str = "auto",
        config: Dict = None
    ) -> UUID:
        """Create a new campaign."""
        import json
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("""
                INSERT INTO campaigns (name, topic, strategy, config)
                VALUES ($1, $2, $3, $4)
                RETURNING id
            """, name, topic, strategy, json.dumps(config or {}))
            
            campaign_id = row['id']
            logger.info(f"campaign_created: campaign_id={str(campaign_id)}, name={name}")
            return campaign_id
    
    async def get_campaign(self, campaign_id: UUID) -> Optional[Dict]:
        """Get campaign by ID."""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT * FROM campaigns WHERE id = $1
            """, campaign_id)
            
            return dict(row) if row else None
    
    async def get_all_campaigns(self) -> List[Dict]:
        """Get all campaigns."""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT * FROM campaigns
                ORDER BY created_at DESC
            """)
            
            return [dict(row) for row in rows]
    
    async def get_active_campaigns(self) -> List[Dict]:
        """Get active campaigns only."""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT * FROM campaigns
                WHERE status = 'active'
                ORDER BY created_at DESC
            """)
            
            return [dict(row) for row in rows]
    
    async def update_campaign_stats(
        self,
        campaign_id: UUID,
        **stats
    ):
        """Update campaign statistics."""
        set_clauses = []
        values = []
        param_num = 2
        
        for key, value in stats.items():
            set_clauses.append(f"{key} = ${param_num}")
            values.append(value)
            param_num += 1
        
        query = f"""
            UPDATE campaigns 
            SET {', '.join(set_clauses)}
            WHERE id = $1
        """
        
        async with self.pool.acquire() as conn:
            await conn.execute(query, campaign_id, *values)
    
    # ============================================================
    # RECIPIENTS
    # ============================================================
    
    async def create_recipient(
        self,
        phone_number: str,
        name: Optional[str] = None,
        department: Optional[str] = None,
        profile: Dict = None
    ) -> UUID:
        """Create or get existing recipient."""
        import json
        async with self.pool.acquire() as conn:
            # Try to get existing
            existing = await conn.fetchrow("""
                SELECT id FROM recipients WHERE phone_number = $1
            """, phone_number)
            
            if existing:
                return existing['id']
            
            # Create new
            row = await conn.fetchrow("""
                INSERT INTO recipients (phone_number, name, department, profile)
                VALUES ($1, $2, $3, $4)
                RETURNING id
            """, phone_number, name, department, json.dumps(profile or {}))
            
            recipient_id = row['id']
            logger.info(f"recipient_created: recipient_id={str(recipient_id)}, phone={phone_number}")
            return recipient_id
    
    async def get_recipient_by_phone(self, phone_number: str) -> Optional[Dict]:
        """Get recipient by phone number."""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT * FROM recipients WHERE phone_number = $1
            """, phone_number)
            
            return dict(row) if row else None
    
    async def update_recipient_stats(
        self,
        recipient_id: UUID,
        **stats
    ):
        """Update recipient engagement statistics."""
        set_clauses = []
        values = []
        param_num = 2
        
        for key, value in stats.items():
            set_clauses.append(f"{key} = ${param_num}")
            values.append(value)
            param_num += 1
        
        query = f"""
            UPDATE recipients 
            SET {', '.join(set_clauses)}
            WHERE id = $1
        """
        
        async with self.pool.acquire() as conn:
            await conn.execute(query, recipient_id, *values)
    
    # ============================================================
    # CONVERSATIONS
    # ============================================================
    
    async def create_conversation(
        self,
        campaign_id: UUID,
        recipient_id: UUID,
        initial_strategy: str = "build_trust"
    ) -> UUID:
        """Create a new conversation."""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("""
                INSERT INTO conversations (
                    campaign_id, 
                    recipient_id, 
                    current_strategy,
                    state,
                    priority
                )
                VALUES ($1, $2, $3, 'initiated', 'normal')
                RETURNING id
            """, campaign_id, recipient_id, initial_strategy)
            
            conversation_id = row['id']
            logger.info(
                f"conversation_created: conversation_id={str(conversation_id)}, campaign_id={str(campaign_id)}, recipient_id={str(recipient_id)}"
            )
            return conversation_id
    
    async def get_conversation(self, conversation_id: UUID) -> Optional[Dict]:
        """Get conversation by ID."""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT * FROM conversations WHERE id = $1
            """, conversation_id)
            
            return dict(row) if row else None
    
    async def get_conversation_by_phone(
        self,
        phone_number: str,
        campaign_id: Optional[UUID] = None
    ) -> Optional[Dict]:
        """Find conversation by recipient phone number."""
        async with self.pool.acquire() as conn:
            if campaign_id:
                row = await conn.fetchrow("""
                    SELECT c.* FROM conversations c
                    JOIN recipients r ON c.recipient_id = r.id
                    WHERE r.phone_number = $1 AND c.campaign_id = $2
                    AND c.state NOT IN ('completed', 'abandoned')
                    ORDER BY c.last_activity_at DESC
                    LIMIT 1
                """, phone_number, campaign_id)
            else:
                # Get most recent active conversation
                row = await conn.fetchrow("""
                    SELECT c.* FROM conversations c
                    JOIN recipients r ON c.recipient_id = r.id
                    WHERE r.phone_number = $1
                    AND c.state NOT IN ('completed', 'abandoned')
                    ORDER BY c.last_activity_at DESC
                    LIMIT 1
                """, phone_number)
            
            return dict(row) if row else None
    
    async def update_conversation(
        self,
        conversation_id: UUID,
        **updates
    ):
        """Update conversation fields."""
        set_clauses = []
        values = []
        param_num = 2
        
        for key, value in updates.items():
            set_clauses.append(f"{key} = ${param_num}")
            values.append(value)
            param_num += 1
        
        query = f"""
            UPDATE conversations 
            SET {', '.join(set_clauses)}
            WHERE id = $1
        """
        
        async with self.pool.acquire() as conn:
            await conn.execute(query, conversation_id, *values)
        
        logger.debug(f"conversation_updated: conversation_id={str(conversation_id)}")
    
    async def get_active_conversations(self) -> List[Dict]:
        """Get all active conversations."""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT * FROM v_active_conversations
                ORDER BY priority, seconds_since_activity
            """)
            
            return [dict(row) for row in rows]
    
    # ============================================================
    # MESSAGES
    # ============================================================
    
    async def create_message(
        self,
        conversation_id: UUID,
        content: str,
        sender: str = "agent",
        priority: str = "normal",
        ideal_send_time: Optional[datetime] = None,
        confidence_score: Optional[float] = None,
        jitter_components: Optional[str] = None,  # Already JSON string
        status: str = "pending",
        sent_at: Optional[datetime] = None,  # NEW: Accept sent_at parameter
        **kwargs
    ) -> UUID:
        """Create a new message."""
        import json as json_lib
        
        # If jitter_components is dict, convert to JSON string
        if jitter_components and isinstance(jitter_components, dict):
            jitter_components = json_lib.dumps(jitter_components)
        
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("""
                INSERT INTO messages (
                    conversation_id,
                    content,
                    sender,
                    priority,
                    ideal_send_time,
                    confidence_score,
                    jitter_components,
                    status,
                    sent_at
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                RETURNING id
            """, conversation_id, content, sender, priority, ideal_send_time, 
               confidence_score, jitter_components or '{}', status, sent_at)
            
            message_id = row['id']
            logger.info(
                f"message_created: message_id={str(message_id)}, conversation_id={str(conversation_id)}, sender={sender}, status={status}, sent_at={sent_at}"
            )
            return message_id
    
    async def update_message(
        self,
        message_id: UUID,
        **updates
    ):
        """Update message fields."""
        set_clauses = []
        values = []
        param_num = 2
        
        for key, value in updates.items():
            set_clauses.append(f"{key} = ${param_num}")
            values.append(value)
            param_num += 1
        
        query = f"""
            UPDATE messages 
            SET {', '.join(set_clauses)}
            WHERE id = $1
        """
        
        async with self.pool.acquire() as conn:
            await conn.execute(query, message_id, *values)
    
    async def get_message(self, message_id: UUID) -> Optional[Dict]:
        """Get message by ID."""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT * FROM messages WHERE id = $1
            """, message_id)
            
            return dict(row) if row else None
    
    async def get_conversation_messages(
        self,
        conversation_id: UUID,
        limit: int = 50
    ) -> List[Dict]:
        """Get messages in a conversation, ordered chronologically (oldest first).
        
        Shows only messages that have been sent (sent_at is not null).
        This includes:
        - Agent messages processed by time controller (marked as sent)
        - Employee messages (immediately sent when received)
        
        Excludes:
        - Scheduled future messages (sent_at is null)
        """
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT 
                    id,
                    content,
                    sender,
                    status,
                    sent_at,
                    ideal_send_time,
                    created_at
                FROM messages 
                WHERE conversation_id = $1
                AND sent_at IS NOT NULL
                ORDER BY sent_at ASC
                LIMIT $2
            """, conversation_id, limit)
            
            messages = []
            for row in rows:
                msg = dict(row)
                # Add timestamp for frontend
                msg['timestamp'] = (row['sent_at'] or row['ideal_send_time'] or row['created_at']).isoformat() if (row['sent_at'] or row['ideal_send_time'] or row['created_at']) else None
                messages.append(msg)
            
            return messages
    
    async def get_scheduled_messages(
        self,
        before_time: datetime,
        limit: int = 100
    ) -> List[Dict]:
        """Get messages scheduled to be sent before a certain time."""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT * FROM messages
                WHERE status = 'scheduled'
                AND actual_send_time <= $1
                ORDER BY priority, actual_send_time
                LIMIT $2
            """, before_time, limit)
            
            return [dict(row) for row in rows]
    
    # ============================================================
    # GLOBAL STATE
    # ============================================================
    
    async def get_global_state(self) -> Dict:
        """Get global agent state."""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT * FROM global_state WHERE id = 1
            """)
            
            return dict(row) if row else {}
    
    async def update_global_state(self, **updates):
        """Update global state."""
        set_clauses = []
        values = []
        param_num = 1
        
        for key, value in updates.items():
            set_clauses.append(f"{key} = ${param_num}")
            values.append(value)
            param_num += 1
        
        query = f"""
            UPDATE global_state 
            SET {', '.join(set_clauses)}
            WHERE id = 1
        """
        
        async with self.pool.acquire() as conn:
            await conn.execute(query, *values)
    
    # ============================================================
    # AGENTIC MEMORY
    # ============================================================
    
    async def create_success_pattern(
        self,
        recipient_id: UUID,
        conversation_id: UUID,
        outcome: str,
        strategy_sequence: List[str],
        timing_pattern: Dict,
        message_sequence: List[str],
        recipient_profile: Dict,
        time_to_success_seconds: float,
        message_count: int
    ) -> UUID:
        """Record a successful phishing pattern."""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("""
                INSERT INTO success_patterns (
                    recipient_id,
                    conversation_id,
                    outcome,
                    strategy_sequence,
                    timing_pattern,
                    message_sequence,
                    recipient_profile,
                    time_to_success_seconds,
                    message_count_to_success,
                    effectiveness_score
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, 0.8)
                RETURNING id
            """, recipient_id, conversation_id, outcome, strategy_sequence,
               timing_pattern, message_sequence, recipient_profile,
               time_to_success_seconds, message_count)
            
            pattern_id = row['id']
            logger.info(f"success_pattern_recorded: pattern_id={str(pattern_id)}, outcome={outcome}")
            return pattern_id
    
    async def get_success_patterns_for_profile(
        self,
        profile: Dict,
        limit: int = 10
    ) -> List[Dict]:
        """Get success patterns for similar profiles."""
        # For now, get most recent/effective patterns
        # TODO: Implement similarity matching
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT * FROM success_patterns
                ORDER BY effectiveness_score DESC, created_at DESC
                LIMIT $1
            """, limit)
            
            return [dict(row) for row in rows]
    
    async def get_conversation_memory(
        self,
        conversation_id: UUID
    ) -> Optional[Dict]:
        """Get conversation memory for learning."""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT * FROM conversation_memory WHERE conversation_id = $1
            """, conversation_id)
            
            return dict(row) if row else None
    
    async def update_conversation_memory(
        self,
        conversation_id: UUID,
        **updates
    ):
        """Update or create conversation memory."""
        # Upsert
        async with self.pool.acquire() as conn:
            # Check if exists
            existing = await conn.fetchrow("""
                SELECT conversation_id FROM conversation_memory 
                WHERE conversation_id = $1
            """, conversation_id)
            
            if existing:
                # Update
                set_clauses = []
                values = []
                param_num = 2
                
                for key, value in updates.items():
                    set_clauses.append(f"{key} = ${param_num}")
                    values.append(value)
                    param_num += 1
                
                query = f"""
                    UPDATE conversation_memory 
                    SET {', '.join(set_clauses)}
                    WHERE conversation_id = $1
                """
                await conn.execute(query, conversation_id, *values)
            else:
                # Insert
                await conn.execute("""
                    INSERT INTO conversation_memory (conversation_id)
                    VALUES ($1)
                """, conversation_id)
    
    # ============================================================
    # QUEUE EVENTS (For Debugging)
    # ============================================================
    
    async def log_queue_event(
        self,
        event_type: str,
        message_id: Optional[UUID] = None,
        conversation_id: Optional[UUID] = None,
        old_priority: Optional[str] = None,
        new_priority: Optional[str] = None,
        old_send_time: Optional[datetime] = None,
        new_send_time: Optional[datetime] = None,
        reason: Optional[str] = None,
        metadata: Dict = None
    ):
        """Log a queue event for debugging."""
        async with self.pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO queue_events (
                    event_type,
                    message_id,
                    conversation_id,
                    old_priority,
                    new_priority,
                    old_send_time,
                    new_send_time,
                    reason,
                    metadata
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            """, event_type, message_id, conversation_id, old_priority,
               new_priority, old_send_time, new_send_time, reason, metadata or {})
    
    async def get_recent_queue_events(self, limit: int = 50) -> List[Dict]:
        """Get recent queue events."""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT * FROM queue_events
                ORDER BY created_at DESC
                LIMIT $1
            """, limit)
            
            return [dict(row) for row in rows]
    
    # ============================================================
    # ANALYTICS QUERIES
    # ============================================================
    
    async def get_queue_visualization(self) -> List[Dict]:
        """Get queue status for visualization."""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT * FROM v_queue_status
                ORDER BY priority, actual_send_time
                LIMIT 50
            """)
            
            return [dict(row) for row in rows]
    
    async def get_campaign_statistics(self, campaign_id: UUID) -> Dict:
        """Get detailed campaign statistics."""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT * FROM v_campaign_stats WHERE id = $1
            """, campaign_id)
            
            return dict(row) if row else {}


# Global database instance
db = Database()

