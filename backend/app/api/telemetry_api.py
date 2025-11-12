"""
Telemetry & Evaluation API

Endpoints:
- GET /api/telemetry/campaign/{campaign_id}/eval - Full campaign evaluation
- GET /api/telemetry/conversation/{conversation_id}/eval - Conversation evaluation
- GET /api/telemetry/metrics/summary - System-wide metrics summary
"""

from fastapi import APIRouter, HTTPException
from uuid import UUID
from typing import Dict
import logging

from app.telemetry.evaluators import (
    campaign_evaluator,
    conversation_evaluator,
    human_likeness_evaluator,
    strategy_evaluator
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/telemetry/campaign/{campaign_id}/eval")
async def evaluate_campaign(campaign_id: UUID) -> Dict:
    """
    Get comprehensive campaign evaluation.
    
    Returns:
    - Overall score and grade
    - Human-likeness assessment
    - Carrier risk analysis
    - Strategy effectiveness
    - Actionable recommendations
    """
    try:
        evaluation = await campaign_evaluator.evaluate_campaign(campaign_id)
        
        return {
            "success": True,
            "campaign_id": str(campaign_id),
            "evaluation": evaluation
        }
    
    except Exception as e:
        logger.error(f"evaluate_campaign_failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/telemetry/conversation/{conversation_id}/eval")
async def evaluate_conversation(conversation_id: UUID) -> Dict:
    """
    Get conversation quality evaluation.
    
    Returns:
    - Quality score
    - Reply rate
    - Response metrics
    - Sentiment analysis
    """
    try:
        evaluation = await conversation_evaluator.evaluate_conversation(conversation_id)
        
        return {
            "success": True,
            "conversation_id": str(conversation_id),
            "evaluation": evaluation
        }
    
    except Exception as e:
        logger.error(f"evaluate_conversation_failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/telemetry/campaign/{campaign_id}/timing")
async def analyze_timing(campaign_id: UUID) -> Dict:
    """
    Analyze timing patterns for human-likeness.
    
    Returns:
    - Timing variance
    - Realism score
    - Risk level
    - Recommendations
    """
    try:
        analysis = await human_likeness_evaluator.evaluate_timing_patterns(campaign_id)
        
        return {
            "success": True,
            "campaign_id": str(campaign_id),
            "analysis": analysis
        }
    
    except Exception as e:
        logger.error(f"analyze_timing_failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/telemetry/campaign/{campaign_id}/red-flags")
async def detect_red_flags(campaign_id: UUID) -> Dict:
    """
    Detect carrier red flags.
    
    Returns:
    - List of red flags
    - Risk score
    - Risk level
    """
    try:
        red_flags = await human_likeness_evaluator.detect_carrier_red_flags(campaign_id)
        
        return {
            "success": True,
            "campaign_id": str(campaign_id),
            "red_flags": red_flags
        }
    
    except Exception as e:
        logger.error(f"detect_red_flags_failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/telemetry/campaign/{campaign_id}/strategies")
async def compare_strategies(campaign_id: UUID) -> Dict:
    """
    Compare strategy effectiveness.
    
    Returns:
    - Strategy metrics
    - Best performing strategy
    - Recommendations
    """
    try:
        comparison = await strategy_evaluator.compare_strategies(campaign_id)
        
        return {
            "success": True,
            "campaign_id": str(campaign_id),
            "comparison": comparison
        }
    
    except Exception as e:
        logger.error(f"compare_strategies_failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/telemetry/metrics/summary")
async def get_metrics_summary() -> Dict:
    """
    Get system-wide metrics summary.
    
    Returns:
    - Total campaigns
    - Total conversations
    - Average scores
    - Overall health
    """
    try:
        from app.models.database import db
        
        async with db.pool.acquire() as conn:
            # Get campaign stats
            campaign_stats = await conn.fetchrow("""
                SELECT 
                    COUNT(*) as total_campaigns,
                    COUNT(CASE WHEN status = 'active' THEN 1 END) as active_campaigns,
                    COUNT(CASE WHEN status = 'completed' THEN 1 END) as completed_campaigns
                FROM campaigns
            """)
            
            # Get conversation stats
            conv_stats = await conn.fetchrow("""
                SELECT 
                    COUNT(*) as total_conversations,
                    COUNT(CASE WHEN reply_count > 0 THEN 1 END) as engaged_conversations,
                    AVG(message_count) as avg_messages,
                    AVG(reply_count) as avg_replies
                FROM conversations
            """)
            
            # Get telemetry event counts
            event_counts = await conn.fetch("""
                SELECT event_type, COUNT(*) as count
                FROM telemetry_events
                GROUP BY event_type
            """)
        
        return {
            "success": True,
            "summary": {
                "campaigns": {
                    "total": campaign_stats['total_campaigns'],
                    "active": campaign_stats['active_campaigns'],
                    "completed": campaign_stats['completed_campaigns']
                },
                "conversations": {
                    "total": conv_stats['total_conversations'],
                    "engaged": conv_stats['engaged_conversations'],
                    "engagement_rate": conv_stats['engaged_conversations'] / conv_stats['total_conversations'] if conv_stats['total_conversations'] > 0 else 0,
                    "avg_messages": float(conv_stats['avg_messages']) if conv_stats['avg_messages'] else 0,
                    "avg_replies": float(conv_stats['avg_replies']) if conv_stats['avg_replies'] else 0
                },
                "telemetry_events": {row['event_type']: row['count'] for row in event_counts}
            }
        }
    
    except Exception as e:
        logger.error(f"get_metrics_summary_failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

