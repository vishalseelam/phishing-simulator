"""
Admin API - System Control and Reset

Note: The /chat endpoint is defined in main.py (uses orchestrator directly)
"""

from fastapi import APIRouter, HTTPException
import logging

from app.models.database import db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.post("/reset")
async def reset_system():
    """
    Reset the entire system - delete all data.
    
    This will:
    - Delete all campaigns
    - Delete all conversations
    - Delete all messages
    - Delete all recipients
    - Reset global state
    - Clear queue
    """
    try:
        if not db.pool:
            return {"success": True, "message": "System reset (in-memory mode)"}
        
        async with db.pool.acquire() as conn:
            # Delete in order (respecting foreign keys)
            await conn.execute("DELETE FROM queue_events")
            await conn.execute("DELETE FROM conversation_memory")
            await conn.execute("DELETE FROM success_patterns")
            await conn.execute("DELETE FROM messages")
            await conn.execute("DELETE FROM conversations")
            await conn.execute("DELETE FROM recipients")
            await conn.execute("DELETE FROM campaigns")
            
            # Reset global state
            await conn.execute("""
                UPDATE global_state 
                SET 
                    total_messages_sent_today = 0,
                    total_messages_sent_this_hour = 0,
                    last_message_sent_at = NULL,
                    active_conversation_id = NULL
                WHERE id = 1
            """)
        
        logger.info("system_reset_complete")
    
    return {
        "success": True,
            "message": "✅ System reset complete. All data cleared."
        }
        
    except Exception as e:
        logger.error(f"system_reset_failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
