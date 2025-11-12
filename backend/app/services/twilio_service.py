"""
Twilio Service - SMS Sending and Receiving

Handles:
- Sending SMS messages
- Processing delivery status
- Receiving incoming SMS (via webhooks)
"""

from typing import Optional, Dict
import logging

from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException

from config import settings


logger = logging.getLogger(__name__)


class TwilioService:
    """
    Twilio SMS service.
    
    Handles all Twilio interactions.
    """
    
    def __init__(self, mock: bool = False):
        """
        Initialize Twilio service.
        
        Args:
            mock: If True, simulate SMS sending (for testing)
        """
        self.mock = mock
        
        if not mock:
            self.client = Client(
                settings.twilio_account_sid,
                settings.twilio_auth_token
            )
            self.from_number = settings.twilio_phone_number
        
        logger.info(f"twilio_service_initialized: mock={mock}")
    
    async def send_sms(
        self,
        to_phone: str,
        message_content: str,
        message_id: str
    ) -> Dict:
        """
        Send SMS message.
        
        Args:
            to_phone: Recipient phone number
            message_content: Message text
            message_id: Message ID for tracking
            
        Returns:
            Dict with send results
        """
        if self.mock:
            # Mock sending for testing
            logger.info(
                "sms_mock_sent",
                message_id=message_id,
                to=to_phone,
                length=len(message_content)
            )
            
            return {
                "success": True,
                "mock": True,
                "message_sid": f"mock_{message_id}",
                "status": "sent",
                "to": to_phone
            }
        
        try:
            # Send via Twilio
            message = self.client.messages.create(
                to=to_phone,
                from_=self.from_number,
                body=message_content,
                # Set status callback URL (configure in production)
                # status_callback=f"{settings.base_url}/webhooks/twilio/status"
            )
            
            logger.info(
                "sms_sent",
                message_id=message_id,
                twilio_sid=message.sid,
                to=to_phone,
                status=message.status
            )
            
            return {
                "success": True,
                "message_sid": message.sid,
                "status": message.status,
                "to": to_phone,
                "price": message.price,
                "price_unit": message.price_unit
            }
            
        except TwilioRestException as e:
            logger.error(
                "sms_send_failed",
                message_id=message_id,
                to=to_phone,
                error=str(e),
                error_code=e.code
            )
            
            return {
                "success": False,
                "error": str(e),
                "error_code": e.code,
                "to": to_phone
            }
        
        except Exception as e:
            logger.error(
                "sms_send_failed",
                message_id=message_id,
                to=to_phone,
                error=str(e)
            )
            
            return {
                "success": False,
                "error": str(e),
                "to": to_phone
            }


# Global Twilio service instance
twilio_service = TwilioService(mock=settings.is_development)

