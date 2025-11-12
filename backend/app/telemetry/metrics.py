"""
Core Metrics Collection

Focused on:
1. Human-likeness (timing, naturalness)
2. Engagement (replies, depth)
3. Performance (speed, accuracy)
4. Success (outcomes, strategy effectiveness)
"""

from datetime import datetime, timezone
from typing import Dict, Optional, List
from uuid import UUID
import json
import logging

from app.models.database import db

logger = logging.getLogger(__name__)


class MetricsCollector:
    """
    Collects and stores metrics for telemetry.
    
    Lightweight, async, non-blocking.
    """
    
    # ========================================================================
    # 1. HUMAN-LIKENESS METRICS
    # ========================================================================
    
    @staticmethod
    async def track_jitter_quality(
        message_id: UUID,
        jitter_components: Dict,
        confidence_score: float
    ):
        """
        Track jitter algorithm quality.
        
        Metrics:
        - Typing time variance
        - Thinking time realism
        - Delay distribution
        - Confidence score
        """
        try:
            # Extract components
            typing_time = jitter_components.get('typing_time', 0)
            thinking_time = jitter_components.get('thinking_time', 0)
            base_delay = jitter_components.get('base_delay', 0)
            
            # Calculate realism score (0-1)
            # Good: typing 2-10s, thinking 5-30s
            typing_realism = 1.0 if 2 <= typing_time <= 10 else 0.5
            thinking_realism = 1.0 if 5 <= thinking_time <= 30 else 0.5
            
            realism_score = (typing_realism + thinking_realism + confidence_score) / 3
            
            # Store in database
            await db.pool.execute("""
                INSERT INTO telemetry_events (
                    event_type,
                    entity_id,
                    metrics,
                    timestamp
                )
                VALUES ($1, $2, $3, $4)
            """, 
                'jitter_quality',
                str(message_id),
                json.dumps({
                    'typing_time': typing_time,
                    'thinking_time': thinking_time,
                    'base_delay': base_delay,
                    'confidence_score': confidence_score,
                    'realism_score': realism_score
                }),
                datetime.now(timezone.utc).replace(tzinfo=None)
            )
            
            logger.info(f"jitter_quality_tracked: message_id={message_id}, realism={realism_score:.2f}")
        
        except Exception as e:
            logger.error(f"track_jitter_quality_failed: {str(e)}")
    
    @staticmethod
    async def track_llm_response_quality(
        message_id: UUID,
        response_text: str,
        analysis: Dict,
        generation_time_ms: float
    ):
        """
        Track LLM response quality.
        
        Metrics:
        - Response length
        - Character limit adherence
        - Sentiment appropriateness
        - Generation speed
        """
        try:
            length = len(response_text)
            within_limit = length <= 160
            
            # Store
            await db.pool.execute("""
                INSERT INTO telemetry_events (
                    event_type,
                    entity_id,
                    metrics,
                    timestamp
                )
                VALUES ($1, $2, $3, $4)
            """,
                'llm_response_quality',
                str(message_id),
                json.dumps({
                    'length': length,
                    'within_limit': within_limit,
                    'generation_time_ms': generation_time_ms,
                    'sentiment': analysis.get('sentiment'),
                    'trust_level': analysis.get('trust_level')
                }),
                datetime.now(timezone.utc).replace(tzinfo=None)
            )
            
            logger.info(f"llm_quality_tracked: message_id={message_id}, length={length}, time={generation_time_ms:.0f}ms")
        
        except Exception as e:
            logger.error(f"track_llm_quality_failed: {str(e)}")
    
    # ========================================================================
    # 2. ENGAGEMENT METRICS
    # ========================================================================
    
    @staticmethod
    async def track_employee_reply(
        conversation_id: UUID,
        reply_text: str,
        time_since_last_agent_message_seconds: float
    ):
        """
        Track employee engagement.
        
        Metrics:
        - Reply speed
        - Reply length
        - Engagement level
        """
        try:
            await db.pool.execute("""
                INSERT INTO telemetry_events (
                    event_type,
                    entity_id,
                    metrics,
                    timestamp
                )
                VALUES ($1, $2, $3, $4)
            """,
                'employee_reply',
                str(conversation_id),
                json.dumps({
                    'reply_length': len(reply_text),
                    'reply_speed_seconds': time_since_last_agent_message_seconds,
                    'contains_question': '?' in reply_text,
                    'is_rapid': time_since_last_agent_message_seconds < 60
                }),
                datetime.now(timezone.utc).replace(tzinfo=None)
            )
            
            logger.info(f"employee_reply_tracked: conv_id={conversation_id}, speed={time_since_last_agent_message_seconds:.0f}s")
        
        except Exception as e:
            logger.error(f"track_employee_reply_failed: {str(e)}")
    
    @staticmethod
    async def track_conversation_outcome(
        conversation_id: UUID,
        outcome: str,  # 'active', 'completed', 'abandoned'
        final_metrics: Dict
    ):
        """
        Track conversation completion.
        
        Metrics:
        - Total exchanges
        - Duration
        - Final sentiment
        - Success indicators
        """
        try:
            await db.pool.execute("""
                INSERT INTO telemetry_events (
                    event_type,
                    entity_id,
                    metrics,
                    timestamp
                )
                VALUES ($1, $2, $3, $4)
            """,
                'conversation_outcome',
                str(conversation_id),
                json.dumps({
                    'outcome': outcome,
                    'total_exchanges': final_metrics.get('message_count', 0),
                    'duration_seconds': final_metrics.get('duration_seconds', 0),
                    'final_sentiment': final_metrics.get('sentiment'),
                    'final_trust_level': final_metrics.get('trust_level'),
                    'reply_count': final_metrics.get('reply_count', 0)
                }),
                datetime.now(timezone.utc).replace(tzinfo=None)
            )
            
            logger.info(f"conversation_outcome_tracked: conv_id={conversation_id}, outcome={outcome}")
        
        except Exception as e:
            logger.error(f"track_conversation_outcome_failed: {str(e)}")
    
    # ========================================================================
    # 3. SYSTEM PERFORMANCE METRICS
    # ========================================================================
    
    @staticmethod
    async def track_cascade_performance(
        conversation_id: UUID,
        messages_rescheduled: int,
        duration_ms: float
    ):
        """
        Track CASCADE operation performance.
        
        Metrics:
        - Reschedule count
        - Operation duration
        - Efficiency
        """
        try:
            await db.pool.execute("""
                INSERT INTO telemetry_events (
                    event_type,
                    entity_id,
                    metrics,
                    timestamp
                )
                VALUES ($1, $2, $3, $4)
            """,
                'cascade_performance',
                str(conversation_id),
                json.dumps({
                    'messages_rescheduled': messages_rescheduled,
                    'duration_ms': duration_ms,
                    'efficiency_score': 1.0 if duration_ms < 500 else 0.5
                }),
                datetime.now(timezone.utc).replace(tzinfo=None)
            )
            
            logger.info(f"cascade_tracked: conv_id={conversation_id}, rescheduled={messages_rescheduled}, time={duration_ms:.0f}ms")
        
        except Exception as e:
            logger.error(f"track_cascade_failed: {str(e)}")
    
    @staticmethod
    async def track_schedule_adherence(
        message_id: UUID,
        ideal_time: datetime,
        actual_time: datetime
    ):
        """
        Track how well we adhere to schedule.
        
        Metrics:
        - Time drift (actual - ideal)
        - Adherence score
        """
        try:
            drift_seconds = (actual_time - ideal_time).total_seconds()
            adherence_score = 1.0 if abs(drift_seconds) < 5 else 0.8
            
            await db.pool.execute("""
                INSERT INTO telemetry_events (
                    event_type,
                    entity_id,
                    metrics,
                    timestamp
                )
                VALUES ($1, $2, $3, $4)
            """,
                'schedule_adherence',
                str(message_id),
                json.dumps({
                    'drift_seconds': drift_seconds,
                    'adherence_score': adherence_score
                }),
                datetime.now(timezone.utc).replace(tzinfo=None)
            )
        
        except Exception as e:
            logger.error(f"track_schedule_adherence_failed: {str(e)}")
    
    # ========================================================================
    # 4. CAMPAIGN SUCCESS METRICS
    # ========================================================================
    
    @staticmethod
    async def track_campaign_metrics(
        campaign_id: UUID,
        metrics: Dict
    ):
        """
        Track overall campaign performance.
        
        Metrics:
        - Reply rate
        - Average conversation depth
        - Strategy effectiveness
        - Completion rate
        """
        try:
            await db.pool.execute("""
                INSERT INTO telemetry_events (
                    event_type,
                    entity_id,
                    metrics,
                    timestamp
                )
                VALUES ($1, $2, $3, $4)
            """,
                'campaign_metrics',
                str(campaign_id),
                json.dumps(metrics),
                datetime.now(timezone.utc).replace(tzinfo=None)
            )
            
            logger.info(f"campaign_metrics_tracked: campaign_id={campaign_id}")
        
        except Exception as e:
            logger.error(f"track_campaign_metrics_failed: {str(e)}")


# Global instance
metrics_collector = MetricsCollector()

