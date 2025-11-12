"""
Employee Simulation API - Admin Simulates Employee Responses

Endpoints for admin to simulate employee behavior:
- Get conversation messages
- Send reply as employee (triggers CASCADE)
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from uuid import UUID
from datetime import datetime
import logging

from app.models.database import db
from app.services.conversation import conversation_manager
from app.api.websocket import connection_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/employee", tags=["employee"])


class EmployeeReplyRequest(BaseModel):
    """Request to simulate employee reply."""
    conversation_id: UUID
    message: str


@router.post("/reply")
async def simulate_employee_reply(request: EmployeeReplyRequest):
    """
    Simulate an employee replying to a phishing message.
    
    This triggers:
    1. LLM analyzes the reply
    2. LLM generates response
    3. CASCADE reorganizes queue
    4. Response scheduled with URGENT priority
    """
    try:
        # Get conversation
        conversation = await db.get_conversation(request.conversation_id)
        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")
        
        # Get recipient
        async with db.pool.acquire() as conn:
            recipient = await conn.fetchrow("""
                SELECT * FROM recipients WHERE id = $1
            """, conversation['recipient_id'])
        
        if not recipient:
            raise HTTPException(status_code=404, detail="Recipient not found")
        
        phone_number = recipient['phone_number']
        
        # Handle the reply (this triggers CASCADE)
        result = await conversation_manager.handle_employee_reply(
            phone_number=phone_number,
            reply_content=request.message,
            reply_time=datetime.now()
        )
        
        # Broadcast update via WebSocket
        await connection_manager.broadcast({
            "type": "employee_replied",
            "data": {
                "conversation_id": str(request.conversation_id),
                "message": request.message,
                "cascade_triggered": True
            }
        })
        
        await connection_manager.broadcast({
            "type": "cascade_triggered",
            "data": {
                "conversation_id": str(request.conversation_id)
            }
        })
        
        return {
            "success": True,
            "message": "Reply processed, CASCADE triggered",
            "agent_response": result.get('response_text')
        }
        
    except Exception as e:
        logger.error(f"employee_reply_failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/conversation/{conversation_id}/messages")
async def get_conversation_messages(conversation_id: UUID):
    """Get all messages in a conversation."""
    try:
        messages = await db.get_conversation_messages(conversation_id)
        
        return {
            "success": True,
            "messages": messages
        }
        
    except Exception as e:
        logger.error(f"get_messages_failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# Remove duplicate - only need one endpoint

