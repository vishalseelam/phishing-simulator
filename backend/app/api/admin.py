"""
Admin API - System Control and Reset
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import logging

from app.models.database import db
import app.services.admin_agent as admin_agent_module

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin", tags=["admin"])


class AdminChatRequest(BaseModel):
    """Admin chat message."""
    message: str
    session_id: str = "default"


@router.post("/chat")
async def chat_with_admin(request: AdminChatRequest):
    """Chat with admin agent."""
    if not admin_agent_module.admin_agent:
        raise HTTPException(status_code=503, detail="Admin agent not initialized")
    
    response = await admin_agent_module.admin_agent.process_command(
        admin_message=request.message,
        session_id=request.session_id
    )
    
    return {
        "success": True,
        "message": response,
        "data": {"session_id": request.session_id}
    }


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
