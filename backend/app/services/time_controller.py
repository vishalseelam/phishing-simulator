"""
Time Controller - Simulation Time Management

Allows:
- Setting simulation time
- Skipping to next message
- Fast forwarding
- Processing messages in time range

Critical for demo/testing without waiting for real time.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional
import logging

from app.models.database import db
from app.api.websocket import connection_manager

logger = logging.getLogger(__name__)


class TimeController:
    """
    Manages simulation time for the system.
    
    All times are stored as naive UTC datetimes.
    In simulation mode: Time can be controlled
    In real-time mode: Uses actual clock
    """
    
    def __init__(self):
        self.is_simulation_mode = True  # Default: simulation
        # Always work in UTC, store as naive
        self.current_time = datetime.now(timezone.utc).replace(tzinfo=None)
        self.time_multiplier = 1.0  # Speed multiplier
        
        logger.info("time_controller_initialized")
    
    async def get_current_time(self) -> datetime:
        """
        Get current time (simulation or real).
        
        This is THE function that all scheduling uses.
        """
        if not self.is_simulation_mode:
            return datetime.now().replace(tzinfo=None)
        
        return self.current_time
    
    async def set_time(self, new_time: datetime) -> dict:
        """
        Set simulation time and process all messages up to this time.
        
        Args:
            new_time: Target time to jump to
            
        Returns:
            Dict with messages processed
        """
        # Ensure naive datetime
        if hasattr(new_time, 'tzinfo') and new_time.tzinfo is not None:
            new_time = new_time.replace(tzinfo=None)
        
        old_time = self.current_time
        self.current_time = new_time
        
        logger.info(f"time_set: from={old_time.isoformat()}, to={new_time.isoformat()}")
        
        # Process all messages between old and new time
        processed = await self._process_messages_until(new_time)
        
        # Update global state in DB
        await db.update_global_state(
            simulation_time=new_time
        )
        
        # Broadcast time change
        await connection_manager.broadcast({
            "type": "time_changed",
            "old_time": old_time.isoformat(),
            "new_time": new_time.isoformat(),
            "messages_processed": len(processed)
        })
        
        return {
            "old_time": old_time.isoformat(),
            "new_time": new_time.isoformat(),
            "messages_processed": len(processed),
            "processed_ids": [str(m['id']) for m in processed]
        }
    
    async def skip_to_next_message(self) -> dict:
        """
        Skip to the time of next scheduled message.
        
        Delivers that message immediately.
        """
        # Get next message
        if not db.pool:
            return {"error": "Database not available"}
        
        logger.info(f"skip_to_next: current_time={self.current_time.isoformat()}")
        
        async with db.pool.acquire() as conn:
            # Get next scheduled message (regardless of current time)
            row = await conn.fetchrow("""
                SELECT id, conversation_id, ideal_send_time, content
                FROM messages
                WHERE status IN ('scheduled', 'pending')
                ORDER BY ideal_send_time
                LIMIT 1
            """)
        
        logger.info(f"next_message_query: found={row is not None}")
        
        if not row:
            return {"error": "No messages scheduled"}
        
        next_time = row['ideal_send_time']
        logger.info(f"raw_next_time: {next_time}, type={type(next_time)}, tzinfo={getattr(next_time, 'tzinfo', None)}")
        
        if hasattr(next_time, 'tzinfo') and next_time.tzinfo is not None:
            next_time = next_time.replace(tzinfo=None)
        
        logger.info(f"jumping_to_message: message_id={row['id']}, scheduled_time={next_time.isoformat()}, hour={next_time.hour}")
        
        # Set time to that message
        result = await self.set_time(next_time)
        
        return {
            "skipped_to": next_time.isoformat(),
            "message_id": str(row['id']),
            "messages_processed": result['messages_processed']
        }
    
    async def fast_forward(self, minutes: int) -> dict:
        """
        Fast forward by N minutes.
        
        Processes all messages in that time range.
        """
        new_time = self.current_time + timedelta(minutes=minutes)
        return await self.set_time(new_time)
    
    async def _process_messages_until(self, target_time: datetime) -> list:
        """
        Process (send) all messages scheduled up to target_time.
        
        Simulates message delivery.
        """
        if not db.pool:
            return []
        
        # Get all messages in time range (add 1 second buffer for microseconds)
        buffer_time = target_time + timedelta(seconds=1)
        async with db.pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT id, conversation_id, content, ideal_send_time
                FROM messages
                WHERE status = 'scheduled'
                AND ideal_send_time <= $1
                ORDER BY ideal_send_time
            """, buffer_time)
        
        logger.info(f"processing_messages: target_time={target_time.isoformat()}, found={len(rows)}")
        
        processed = []
        
        for row in rows:
            message_id = row['id']
            conversation_id = row['conversation_id']
            send_time = row['ideal_send_time']
            
            if hasattr(send_time, 'tzinfo') and send_time.tzinfo is not None:
                send_time = send_time.replace(tzinfo=None)
            
            # Mark as sent
            await db.update_message(
                message_id=message_id,
                status='sent',
                sent_at=send_time
            )
            
            logger.info(f"message_marked_sent: message_id={message_id}")
            
            # Update conversation
            await db.update_conversation(
                conversation_id=conversation_id,
                last_message_sent_at=send_time
            )
            
            # Broadcast
            await connection_manager.broadcast({
                "type": "message_sent",
                "message_id": str(message_id),
                "conversation_id": str(conversation_id),
                "sent_at": send_time.isoformat()
            })
            
            processed.append(dict(row))
            
            logger.info(f"message_sent_simulation: message_id={message_id}, time={send_time.isoformat()}")
        
        return processed
    
    async def reset_to_realtime(self):
        """Switch back to real-time mode."""
        from datetime import timezone
        self.is_simulation_mode = False
        self.current_time = datetime.now(timezone.utc).replace(tzinfo=None)
        
        await connection_manager.broadcast({
            "type": "mode_changed",
            "mode": "realtime"
        })
        
        return {"mode": "realtime"}


# Global time controller instance
time_controller = TimeController()

