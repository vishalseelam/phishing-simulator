"""
Scheduler Service - Database-Integrated Jitter Algorithm

This is the FOUNDATION of the system.

Pure logic (no LLM):
- Wraps jitter_production algorithm
- Loads context from database
- Stores results in database
- Handles CASCADE automatically
- Processes queue
- Broadcasts updates

Both agents (Orchestrator and Conversation) call this service.
"""

from datetime import datetime
from typing import List, Dict, Optional
from uuid import UUID
import logging
import time

from app.core.jitter_production import (
    schedule_messages,
    reschedule_from_current,
    import_conversation_history,
    schedule_additional_message,
    update_conversation_learning
)
from app.models.database import db
from app.api.websocket import connection_manager
from app.telemetry.metrics import metrics_collector

logger = logging.getLogger(__name__)

# Import time controller (will be set after initialization)
time_controller = None


class SchedulerService:
    """
    Self-contained scheduler service.
    
    Handles all scheduling logic without needing orchestrator coordination.
    """
    
    def __init__(self):
        logger.info("scheduler_service_initialized")
    
    # ========================================================================
    # Core Scheduling
    # ========================================================================
    
    async def schedule_message(
        self,
        message_data: Dict,
        is_reply: bool = False,
        extra_delay: float = 0.0
    ) -> Dict:
        """
        Schedule a single message.
        
        If is_reply=True, automatically handles CASCADE.
        
        Args:
            message_data: {id, to, content, conversation_id}
            is_reply: True if responding to employee
            extra_delay: Optional extra delay from LLM (lookup time)
            
        Returns:
            Scheduled message with timing
        """
        conversation_id = message_data['conversation_id']
        
        # If this is a reply, we need to reschedule EVERYTHING (CASCADE)
        if is_reply:
            return await self._handle_reply_with_cascade(message_data, extra_delay)
        
        # Otherwise, just add to queue
        return await self._add_to_queue(message_data, extra_delay)
    
    async def _add_to_queue(
        self,
        message_data: Dict,
        extra_delay: float = 0.0
    ) -> Dict:
        """
        Add message to queue (non-reply).
        
        Loads all pending, reschedules with new message included.
        """
        # Load all pending messages
        all_pending = await self._load_pending_messages()
        
        # Add this new message
        all_messages = all_pending + [message_data]
        
        # Load contexts
        contexts = await self._load_all_contexts()
        global_state = await self._load_global_state()
        
        # Extra delays
        extra_delays = {message_data['id']: extra_delay} if extra_delay > 0 else {}
        
        # Call jitter algorithm
        from datetime import timezone
        from app.services.time_controller import time_controller
        
        # Use simulation time if available
        if time_controller:
            current_time = await time_controller.get_current_time()
        else:
            current_time = datetime.now(timezone.utc).replace(tzinfo=None)
        
        scheduled = schedule_messages(
            messages=all_messages,
            current_time=current_time,
            global_state=global_state,
            conversation_contexts=contexts,
            extra_delays=extra_delays
        )
        
        # Store in DB (CREATE new message)
        await self._store_scheduled_messages(scheduled, [message_data], is_new=True)
        
        # Broadcast
        await connection_manager.broadcast({
            "type": "message_scheduled",
            "message_id": message_data['id'],
            "conversation_id": message_data['conversation_id']
        })
        
        logger.info(f"message_scheduled: message_id={message_data['id']}")
        
        # Return just this message's schedule
        for s in scheduled:
            if s['message_id'] == message_data['id']:
                return s
        
        return scheduled[-1]  # Fallback
    
    async def _handle_reply_with_cascade(
        self,
        reply_message_data: Dict,
        extra_delay: float = 0.0
    ) -> Dict:
        """
        Handle reply message with automatic CASCADE.
        
        This is the key function: CASCADE happens automatically here.
        """
        conversation_id = reply_message_data['conversation_id']
        
        # Start timing CASCADE operation
        cascade_start_time = time.time()
        
        logger.info(f"cascade_triggered: conversation_id={conversation_id}")
        
        # Load all pending messages (OTHER conversations)
        all_pending = await self._load_pending_messages()
        
        # Add reply message (NEW message to be created)
        all_messages = all_pending + [reply_message_data]
        
        # Load contexts
        contexts = await self._load_all_contexts()
        
        # Mark this conversation as ACTIVE (critical!)
        # Use simulation time if available
        if time_controller:
            current_time = await time_controller.get_current_time()
        else:
            from datetime import timezone
            current_time = datetime.now(timezone.utc).replace(tzinfo=None)
        
        contexts[conversation_id]['is_active'] = True
        contexts[conversation_id]['last_reply_time'] = current_time.isoformat()
        
        # Update in DB (is_active is computed from state, not stored)
        await db.update_conversation(
            conversation_id=UUID(conversation_id),
            state='active',
            priority='urgent',
            last_reply_received_at=current_time
        )
        
        # Load global state
        global_state = await self._load_global_state()
        
        # Extra delays
        extra_delays = {reply_message_data['id']: extra_delay} if extra_delay > 0 else {}
        
        # Call jitter algorithm (handles CASCADE automatically!)
        # Active conversation will be prioritized, all others rescheduled
        rescheduled = schedule_messages(
            messages=all_messages,
            current_time=current_time,
            global_state=global_state,
            conversation_contexts=contexts,
            extra_delays=extra_delays
        )
        
        # Split into NEW (reply) and EXISTING (others) messages
        reply_scheduled = None
        existing_scheduled = []
        
        for s in rescheduled:
            if s['message_id'] == reply_message_data['id']:
                reply_scheduled = s
            else:
                existing_scheduled.append(s)
        
        # CREATE the reply message
        if reply_scheduled:
            await self._store_scheduled_messages([reply_scheduled], [reply_message_data], is_new=True)
        
        # UPDATE existing pending messages (CASCADE effect)
        if existing_scheduled:
            await self._store_scheduled_messages(existing_scheduled, all_pending, is_new=False)
        
        # Broadcast CASCADE event
        await connection_manager.broadcast({
            "type": "cascade_triggered",
            "conversation_id": conversation_id,
            "rescheduled_count": len(rescheduled)
        })
        
        # Track CASCADE performance
        cascade_duration_ms = (time.time() - cascade_start_time) * 1000
        try:
            await metrics_collector.track_cascade_performance(
                conversation_id=UUID(conversation_id),
                messages_rescheduled=len(rescheduled),
                duration_ms=cascade_duration_ms
            )
        except Exception as e:
            logger.error(f"track_cascade_failed: {str(e)}")
        
        logger.info(f"cascade_complete: conversation_id={conversation_id}, rescheduled={len(rescheduled)}, duration_ms={cascade_duration_ms:.0f}")
        
        # Return just the reply message's schedule
        for s in rescheduled:
            if s['message_id'] == reply_message_data['id']:
                return s
        
        return rescheduled[0]  # Fallback
    
    # ========================================================================
    # Batch Scheduling (For Campaign Creation)
    # ========================================================================
    
    async def schedule_campaign_messages(
        self,
        campaign_id: UUID,
        messages: List[Dict]
    ) -> List[Dict]:
        """
        Schedule all messages for a new campaign.
        
        Called by Orchestrator when creating campaign.
        """
        try:
            # Load contexts
            contexts = await self._load_all_contexts()
            global_state = await self._load_global_state()
            
            # Call jitter algorithm
            from app.core.jitter_production import schedule_messages
            
               # Use simulation time if available
            if time_controller:
                current_time = await time_controller.get_current_time()
            else:
                from datetime import timezone
                # Use UTC consistently
                current_time = datetime.now(timezone.utc).replace(tzinfo=None)
            
            scheduled = schedule_messages(
                messages=messages,
                current_time=current_time,
                global_state=global_state,
                conversation_contexts=contexts
            )
            
            # Store in DB (CREATE new messages for campaign)
            await self._store_scheduled_messages(scheduled, messages, is_new=True)
            
            # Broadcast
            await connection_manager.broadcast({
                "type": "campaign_scheduled",
                "campaign_id": str(campaign_id),
                "message_count": len(scheduled)
            })
            
            logger.info(f"campaign_scheduled: campaign_id={campaign_id}, count={len(scheduled)}")
            
            return scheduled
        
        except Exception as e:
            logger.error(f"schedule_campaign_failed: {str(e)}")
            raise
    
    # ========================================================================
    # Queue Processing
    # ========================================================================
    
    async def get_next_due_message(self) -> Optional[Dict]:
        """
        Get next message that should be sent NOW.
        
        Checks:
        - Is it time?
        - Is state ACTIVE?
        - Returns message or None
        """
        # Load global state
        global_state = await self._load_global_state()
        
        # Check if ACTIVE
        if global_state.get('current_availability') != 'ACTIVE':
            return None
        
        # Get next due message from DB
        async with db.pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT 
                    m.id, m.content, m.conversation_id,
                    r.phone_number,
                    m.scheduled_time
                FROM messages m
                JOIN conversations c ON m.conversation_id = c.id
                JOIN recipients r ON c.recipient_id = r.id
                WHERE m.status = 'scheduled'
                AND m.ideal_send_time <= $1
                ORDER BY m.ideal_send_time
                LIMIT 1
            """, datetime.now())
        
        if not row:
            return None
        
        return dict(row)
    
    async def mark_message_sent(self, message_id: UUID):
        """Mark message as sent and update global state."""
        await db.update_message(
            message_id=message_id,
            status='sent',
            sent_at=datetime.now()
        )
        
        # Update global state
        await db.update_global_state(
            total_messages_sent_today=db.global_state.get('total_messages_sent_today', 0) + 1,
            last_message_sent_at=datetime.now()
        )
        
        logger.info(f"message_sent: message_id={message_id}")
    
    # ========================================================================
    # History Import
    # ========================================================================
    
    async def import_history(
        self,
        phone_number: str,
        history_json: Dict
    ) -> Dict:
        """
        Import conversation history and store learned patterns.
        """
        # Call jitter algorithm function
        patterns = import_conversation_history(phone_number, history_json)
        
        # Find or create recipient
        recipient = await db.get_recipient_by_phone(phone_number)
        if not recipient:
            recipient_id = await db.create_recipient(phone_number=phone_number)
        else:
            recipient_id = recipient['id']
        
        # Store patterns in conversation_memory
        # (Assuming conversation exists or will be created)
        # For now, just return patterns
        
        logger.info(f"history_imported: phone={phone_number}")
        
        return patterns
    
    # ========================================================================
    # Private: Database Loading
    # ========================================================================
    
    async def _load_pending_messages(self) -> List[Dict]:
        """Load all pending/scheduled messages from DB (excluding sent messages)."""
        async with db.pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT 
                    m.id, m.content, m.conversation_id,
                    r.phone_number as to,
                    m.is_reply, m.sender, m.status
                FROM messages m
                JOIN conversations c ON m.conversation_id = c.id
                JOIN recipients r ON c.recipient_id = r.id
                WHERE m.status IN ('pending', 'scheduled')
                AND m.sender = 'agent'
                ORDER BY m.ideal_send_time
            """)
        
        pending_list = [
            {
                'id': str(row['id']),
                'to': row['to'],
                'content': row['content'],
                'conversation_id': str(row['conversation_id']),
                'is_reply': row.get('is_reply', False)
            }
            for row in rows
        ]
        
        logger.info(f"loaded_pending_messages: count={len(pending_list)}, ids={[p['id'] for p in pending_list]}")
        return pending_list
    
    async def _load_all_contexts(self) -> Dict[str, Dict]:
        """Load all conversation contexts from DB."""
        contexts = {}
        
        async with db.pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT 
                    c.id,
                    c.state,
                    c.priority,
                    c.last_message_sent_at,
                    c.last_reply_received_at,
                    r.phone_number,
                    cm.learned_timing_multiplier,
                    cm.best_time_of_day_hours
                FROM conversations c
                JOIN recipients r ON c.recipient_id = r.id
                LEFT JOIN conversation_memory cm ON c.id = cm.conversation_id
                WHERE c.state NOT IN ('completed', 'abandoned')
            """)
            
            for row in rows:
                conv_id = str(row['id'])
                
                # Load message history (within same connection)
                msg_history = await conn.fetch("""
                    SELECT sent_at FROM messages
                    WHERE conversation_id = $1 AND sent_at IS NOT NULL
                    ORDER BY sent_at
                """, row['id'])
                
                # Convert to naive datetimes
                history_times = []
                for m in msg_history:
                    if m['sent_at']:
                        dt = m['sent_at']
                        if hasattr(dt, 'tzinfo') and dt.tzinfo is not None:
                            dt = dt.replace(tzinfo=None)
                        history_times.append(dt.isoformat())
                
                # Convert last times to naive
                last_send = row['last_message_sent_at']
                if last_send and hasattr(last_send, 'tzinfo') and last_send.tzinfo is not None:
                    last_send = last_send.replace(tzinfo=None)
                
                last_reply = row['last_reply_received_at']
                if last_reply and hasattr(last_reply, 'tzinfo') and last_reply.tzinfo is not None:
                    last_reply = last_reply.replace(tzinfo=None)
            
                contexts[conv_id] = {
                    'is_active': (row['state'] in ['active', 'engaged']),
                    'state': row['state'],
                    'message_history': history_times,
                    'last_send_time': last_send.isoformat() if last_send else None,
                    'last_reply_time': last_reply.isoformat() if last_reply else None,
                    'learned_preferences': {
                        'timing_multiplier': row['learned_timing_multiplier'] or 1.0,
                        'preferred_hours': row['best_time_of_day_hours'] or []
                    }
                }
        
        return contexts
    
    async def _load_global_state(self) -> Dict:
        """Load global state from DB."""
        state_row = await db.get_global_state()
        
        if not state_row:
            # Default state
            return {
                'current_availability': 'ACTIVE',
                'next_state_transition': datetime.now().isoformat(),
                'historical_send_times': [],
                'messages_sent_today': 0,
                'max_messages_per_day': 100,
                'current_time': datetime.now().isoformat()
            }
        
        # Load historical times
        async with db.pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT sent_at FROM messages
                WHERE sent_at IS NOT NULL
                ORDER BY sent_at DESC
                LIMIT 50
            """)
        
        # Convert to naive datetimes (remove timezone)
        historical_times = []
        for row in rows:
            if row['sent_at']:
                dt = row['sent_at']
                if hasattr(dt, 'tzinfo') and dt.tzinfo is not None:
                    dt = dt.replace(tzinfo=None)
                historical_times.append(dt.isoformat())
        
        # Get next transition time (naive)
        next_transition = state_row.get('state_transition_at', datetime.now())
        if hasattr(next_transition, 'tzinfo') and next_transition.tzinfo is not None:
            next_transition = next_transition.replace(tzinfo=None)
        
        return {
            'current_availability': state_row.get('current_state', 'ACTIVE'),
            'next_state_transition': next_transition.isoformat(),
            'historical_send_times': historical_times,
            'messages_sent_today': state_row.get('total_messages_sent_today', 0),
            'max_messages_per_day': 100,
            'current_time': datetime.now().isoformat()
        }
    
    async def _store_scheduled_messages(self, scheduled: List[Dict], original_messages: List[Dict] = None, is_new: bool = False):
        """
        Store or update scheduled messages in DB.
        
        - If is_new=True: CREATE new messages (for campaigns)
        - If is_new=False: UPDATE existing messages (for CASCADE)
        """
        import json
        
        if is_new:
            # CREATE new messages (for campaign creation)
            content_lookup = {}
            if original_messages:
                for msg in original_messages:
                    content_lookup[msg['id']] = msg['content']
            
            for s in scheduled:
                conversation_id = UUID(s['conversation_id'])
                content = content_lookup.get(s['message_id'], s.get('content', 'Message'))
                
                # Create new message
                message_id = await db.create_message(
                    conversation_id=conversation_id,
                    content=content,
                    sender='agent',
                    priority='normal',
                    ideal_send_time=datetime.fromisoformat(s['scheduled_time']),
                    confidence_score=s['confidence'],
                    jitter_components=json.dumps(s.get('components', {})),
                    status='scheduled'
                )
                
                # Track jitter quality
                try:
                    await metrics_collector.track_jitter_quality(
                        message_id=message_id,
                        jitter_components=s.get('components', {}),
                        confidence_score=s['confidence']
                    )
                except Exception as e:
                    logger.error(f"track_jitter_quality_failed: {str(e)}")
            
            logger.info(f"created_scheduled_messages: count={len(scheduled)}")
        else:
            # UPDATE existing messages (for CASCADE)
            for s in scheduled:
                message_id = UUID(s['message_id'])
                
                await db.update_message(
                    message_id=message_id,
                    ideal_send_time=datetime.fromisoformat(s['scheduled_time']),
                    confidence_score=s['confidence'],
                    jitter_components=json.dumps(s.get('components', {})),
                    status='scheduled'
                )
            
            logger.info(f"updated_scheduled_messages: count={len(scheduled)}")
    
    # ========================================================================
    # Queue Processing
    # ========================================================================
    
    async def process_queue(self):
        """
        Process queue - send messages that are due.
        
        Called by background task every 5 seconds.
        """
        # Get next due message
        message = await self.get_next_due_message()
        
        if not message:
            return None
        
        # Send message (mock for now, Twilio in production)
        logger.info(f"sending_message: id={message['id']}, to={message['phone_number']}")
        
        # Mark as sent
        await self.mark_message_sent(UUID(message['id']))
        
        # Update conversation
        await db.update_conversation(
            conversation_id=UUID(message['conversation_id']),
            last_message_sent_at=datetime.now()
        )
        
        # Broadcast
        await connection_manager.broadcast({
            "type": "message_sent",
            "message_id": str(message['id']),
            "conversation_id": str(message['conversation_id'])
        })
        
        return message


# Global scheduler service instance
scheduler_service = SchedulerService()

