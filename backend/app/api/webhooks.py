"""
Webhook Handlers - Twilio Callbacks

Handles:
- Incoming SMS from employees
- Delivery status callbacks
"""

from fastapi import APIRouter, Request, Form
from typing import Optional
from datetime import datetime
import logging

from app.services.conversation import conversation_manager
from app.models.database import db


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post("/twilio/incoming")
async def handle_incoming_sms(
    From: str = Form(...),
    To: str = Form(...),
    Body: str = Form(...),
    MessageSid: str = Form(...),
    NumMedia: str = Form(default="0")
):
    """
    Handle incoming SMS from employee (Twilio webhook).
    
    This is THE CRITICAL PATH that triggers:
    1. Find conversation by phone
    2. Analyze reply
    3. Generate response
    4. CASCADE: Reorganize entire queue
    """
    logger.info(
        "incoming_sms_received",
        from_phone=From,
        message_sid=MessageSid,
        length=len(Body)
    )
    
    try:
        # Handle employee reply
        result = await conversation_manager.handle_employee_reply(
            phone_number=From,
            reply_content=Body,
            reply_time=datetime.now()
        )
        
        if result['success']:
            logger.info(
                "incoming_sms_processed",
                conversation_id=result['conversation_id'],
                response_generated=True,
                queue_reorganized=True
            )
            
            # Return TwiML response (optional)
            return {
                "status": "ok",
                "message": "Reply processed"
            }
        else:
            logger.warning(
                "incoming_sms_no_conversation",
                from_phone=From,
                error=result.get('error')
            )
            
            return {
                "status": "ok",
                "message": "No active conversation"
            }
    
    except Exception as e:
        logger.error(f"incoming_sms_processing_failed: error={str(e)}", exc_info=True)
        
        return {
            "status": "error",
            "message": str(e)
        }


@router.post("/twilio/status")
async def handle_delivery_status(
    MessageSid: str = Form(...),
    MessageStatus: str = Form(...),
    ErrorCode: Optional[str] = Form(default=None),
    ErrorMessage: Optional[str] = Form(default=None)
):
    """
    Handle delivery status callback from Twilio.
    
    Updates message status when delivered/failed.
    """
    logger.info(
        "delivery_status_received",
        message_sid=MessageSid,
        status=MessageStatus
    )
    
    try:
        # Find message by Twilio SID
        async with db.pool.acquire() as conn:
            message = await conn.fetchrow("""
                SELECT id, conversation_id FROM messages
                WHERE twilio_sid = $1
            """, MessageSid)
        
        if not message:
            logger.warning(f"message_not_found_for_sid: sid={MessageSid}")
            return {"status": "ok"}
        
        # Update message status
        updates = {
            "twilio_status": MessageStatus
        }
        
        if MessageStatus == "delivered":
            updates["status"] = "delivered"
            updates["delivered_at"] = datetime.now()
        
        elif MessageStatus in ["failed", "undelivered"]:
            updates["status"] = "failed"
            if ErrorCode:
                updates["error_code"] = ErrorCode
            if ErrorMessage:
                updates["error_message"] = ErrorMessage
        
        await db.update_message(
            message_id=message['id'],
            **updates
        )
        
        # Update campaign stats if delivered
        if MessageStatus == "delivered":
            conversation = await db.get_conversation(message['conversation_id'])
            if conversation:
                campaign = await db.get_campaign(conversation['campaign_id'])
                if campaign:
                    await db.update_campaign_stats(
                        campaign_id=conversation['campaign_id'],
                        total_messages_delivered=campaign.get('total_messages_delivered', 0) + 1
                    )
        
        logger.info(
            "delivery_status_processed",
            message_id=str(message['id']),
            status=MessageStatus
        )
        
        return {"status": "ok"}
    
    except Exception as e:
        logger.error(f"delivery_status_processing_failed: error={str(e)}", exc_info=True)
        return {"status": "error", "message": str(e)}


# Include router in main app

