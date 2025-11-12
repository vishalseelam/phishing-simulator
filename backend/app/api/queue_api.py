"""
Queue API - View all scheduled messages.
"""

from fastapi import APIRouter, HTTPException
from typing import List
from datetime import datetime
import logging

from app.models.database import db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["queue"])


@router.get("/queue/all")
async def get_all_scheduled_messages():
    """
    Get all scheduled messages, sorted by time.
    """
    try:
        if not db.pool:
            return {"success": True, "messages": [], "count": 0}
        
        async with db.pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT 
                    m.id,
                    m.content,
                    m.ideal_send_time as scheduled_time,
                    m.priority,
                    m.status,
                    m.conversation_id,
                    r.phone_number
                FROM messages m
                JOIN conversations c ON m.conversation_id = c.id
                JOIN recipients r ON c.recipient_id = r.id
                WHERE m.status IN ('scheduled', 'pending')
                AND m.ideal_send_time IS NOT NULL
                ORDER BY m.ideal_send_time
                LIMIT 100
            """)
        
        messages = [dict(row) for row in rows]
        
        return {
            "success": True,
            "messages": messages,
            "count": len(messages)
        }
        
    except Exception as e:
        logger.error(f"queue_all_failed: {str(e)}")
        return {
            "success": False,
            "messages": [],
            "count": 0,
            "error": str(e)
        }


@router.get("/conversations/all")
async def get_all_conversations():
    """Get all conversations with basic info."""
    try:
        if not db.pool:
            return {"success": True, "conversations": []}
        
        async with db.pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT 
                    c.id,
                    c.state,
                    c.priority,
                    c.message_count,
                    c.reply_count,
                    r.phone_number,
                    camp.name as campaign_name
                FROM conversations c
                JOIN recipients r ON c.recipient_id = r.id
                JOIN campaigns camp ON c.campaign_id = camp.id
                WHERE c.state NOT IN ('completed', 'abandoned')
                ORDER BY c.last_activity_at DESC
            """)
        
        conversations = [dict(row) for row in rows]
        
        return {
            "success": True,
            "conversations": conversations
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

