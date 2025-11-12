"""
Pydantic schemas for API requests/responses.
"""

from datetime import datetime
from typing import Optional, List, Dict
from uuid import UUID
from pydantic import BaseModel, Field


# ============================================================
# Request Schemas
# ============================================================

class CreateCampaignRequest(BaseModel):
    """Request to create a new campaign."""
    name: str = Field(..., min_length=1, max_length=255)
    topic: str = Field(..., description="Phishing topic/theme")
    strategy: str = Field(default="auto", description="Campaign strategy")
    recipients: List[Dict] = Field(..., description="List of recipient dicts")


class InjectMessageRequest(BaseModel):
    """Request to inject a message mid-campaign."""
    campaign_id: UUID
    recipient_id: Optional[UUID] = None
    message: str = Field(..., min_length=1, max_length=500)
    priority: str = Field(default="high", pattern="^(urgent|high|normal|low)$")


class AdminChatRequest(BaseModel):
    """Admin chat message."""
    message: str = Field(..., min_length=1)
    session_id: Optional[str] = None


class ImportConversationHistoryRequest(BaseModel):
    """Import conversation history."""
    conversations: List[Dict]


# ============================================================
# Response Schemas
# ============================================================

class TimingComponentsResponse(BaseModel):
    """Timing breakdown."""
    typing_time: float
    thinking_time: float
    base_delay: float
    final_delay: float
    confidence: float


class MessageResponse(BaseModel):
    """Message details."""
    id: UUID
    conversation_id: UUID
    content: str
    sender: str
    status: str
    priority: str
    actual_send_time: Optional[datetime]
    confidence_score: Optional[float]
    created_at: datetime


class ConversationResponse(BaseModel):
    """Conversation details."""
    id: UUID
    campaign_id: UUID
    recipient_id: UUID
    recipient_name: Optional[str]
    state: str
    priority: str
    message_count: int
    reply_count: int
    sentiment: Optional[str]
    last_activity_at: Optional[datetime]


class QueueStatusResponse(BaseModel):
    """Queue status."""
    total_scheduled: int
    by_priority: Dict[str, int]
    active_conversations: int
    next_send_time: Optional[str]
    messages_sent_this_hour: int
    messages_sent_today: int
    can_send_now: bool
    global_state: Dict


class CampaignResponse(BaseModel):
    """Campaign details."""
    id: UUID
    name: str
    topic: str
    status: str
    total_recipients: int
    total_messages_sent: int
    total_replies_received: int
    success_count: int
    created_at: datetime
    started_at: Optional[datetime]


class DashboardResponse(BaseModel):
    """Dashboard overview."""
    queue_status: QueueStatusResponse
    active_conversations: List[ConversationResponse]
    recent_messages: List[MessageResponse]
    statistics: Dict


class SuccessResponse(BaseModel):
    """Generic success response."""
    success: bool = True
    message: str
    data: Optional[Dict] = None

