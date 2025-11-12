"""
Evaluation System

Evaluates:
1. Human-likeness of timing patterns
2. Conversation quality
3. Strategy effectiveness
4. Carrier detection risk

Focus: Actionable insights, not vanity metrics.
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional
from uuid import UUID
import statistics
import logging

from app.models.database import db

logger = logging.getLogger(__name__)


class HumanLikenessEvaluator:
    """
    Evaluates how human-like our timing patterns are.
    
    Key Question: Would a carrier flag this as automated?
    """
    
    @staticmethod
    async def evaluate_timing_patterns(campaign_id: UUID) -> Dict:
        """
        Analyze timing patterns for human-likeness.
        
        Red Flags:
        - Perfectly uniform intervals
        - Messages at exact minute marks
        - No variance in typing/thinking times
        - Unrealistic burst patterns
        """
        try:
            # Get all jitter quality metrics for campaign
            async with db.pool.acquire() as conn:
                rows = await conn.fetch("""
                    SELECT metrics
                    FROM telemetry_events
                    WHERE event_type = 'jitter_quality'
                    AND entity_id IN (
                        SELECT id::text FROM messages 
                        WHERE conversation_id IN (
                            SELECT id FROM conversations WHERE campaign_id = $1
                        )
                    )
                """, campaign_id)
            
            if not rows:
                return {'score': 0.0, 'status': 'no_data'}
            
            import json
            metrics = [json.loads(row['metrics']) for row in rows]
            
            # Calculate variance in timing
            typing_times = [m['typing_time'] for m in metrics]
            thinking_times = [m['thinking_time'] for m in metrics]
            realism_scores = [m['realism_score'] for m in metrics]
            
            typing_variance = statistics.variance(typing_times) if len(typing_times) > 1 else 0
            thinking_variance = statistics.variance(thinking_times) if len(thinking_times) > 1 else 0
            avg_realism = statistics.mean(realism_scores)
            
            # Scoring
            # High variance = good (human-like)
            # Low variance = bad (robotic)
            variance_score = min(1.0, (typing_variance + thinking_variance) / 100)
            
            # Overall human-likeness score
            human_likeness_score = (variance_score + avg_realism) / 2
            
            # Risk assessment
            risk = 'low' if human_likeness_score > 0.7 else 'medium' if human_likeness_score > 0.5 else 'high'
            
            result = {
                'score': human_likeness_score,
                'risk_level': risk,
                'typing_variance': typing_variance,
                'thinking_variance': thinking_variance,
                'avg_realism': avg_realism,
                'total_messages': len(metrics),
                'recommendation': _get_timing_recommendation(human_likeness_score)
            }
            
            logger.info(f"timing_evaluated: campaign_id={campaign_id}, score={human_likeness_score:.2f}, risk={risk}")
            
            return result
        
        except Exception as e:
            logger.error(f"evaluate_timing_failed: {str(e)}")
            return {'score': 0.0, 'status': 'error', 'error': str(e)}
    
    @staticmethod
    async def detect_carrier_red_flags(campaign_id: UUID) -> Dict:
        """
        Detect patterns that might trigger carrier flags.
        
        Red Flags:
        - Too many messages in short time
        - Identical message intervals
        - Messages at suspicious times (3am)
        - Rapid-fire replies
        """
        try:
            # Get all message send times
            async with db.pool.acquire() as conn:
                rows = await conn.fetch("""
                    SELECT sent_at
                    FROM messages
                    WHERE conversation_id IN (
                        SELECT id FROM conversations WHERE campaign_id = $1
                    )
                    AND sender = 'agent'
                    AND sent_at IS NOT NULL
                    ORDER BY sent_at
                """, campaign_id)
            
            if len(rows) < 2:
                return {'red_flags': [], 'risk_score': 0.0}
            
            send_times = [row['sent_at'] for row in rows]
            red_flags = []
            
            # Check 1: Too many messages in 1 hour
            for i in range(len(send_times) - 10):
                window = send_times[i:i+10]
                if window[-1] - window[0] < timedelta(hours=1):
                    red_flags.append({
                        'type': 'burst_detected',
                        'severity': 'high',
                        'detail': '10+ messages in 1 hour'
                    })
            
            # Check 2: Identical intervals
            intervals = [(send_times[i+1] - send_times[i]).total_seconds() 
                        for i in range(len(send_times) - 1)]
            
            if len(set(intervals)) < len(intervals) * 0.5:  # Less than 50% unique
                red_flags.append({
                    'type': 'uniform_intervals',
                    'severity': 'high',
                    'detail': 'Too many identical intervals'
                })
            
            # Check 3: Messages at suspicious hours (11pm - 6am)
            suspicious_hours = [t for t in send_times 
                              if t.hour >= 23 or t.hour < 6]
            
            if len(suspicious_hours) > len(send_times) * 0.1:  # More than 10%
                red_flags.append({
                    'type': 'suspicious_hours',
                    'severity': 'medium',
                    'detail': f'{len(suspicious_hours)} messages sent at night'
                })
            
            # Risk score (0-1)
            risk_score = min(1.0, len(red_flags) * 0.3)
            
            return {
                'red_flags': red_flags,
                'risk_score': risk_score,
                'risk_level': 'high' if risk_score > 0.7 else 'medium' if risk_score > 0.4 else 'low'
            }
        
        except Exception as e:
            logger.error(f"detect_red_flags_failed: {str(e)}")
            return {'red_flags': [], 'risk_score': 0.0, 'error': str(e)}


class ConversationQualityEvaluator:
    """
    Evaluates conversation quality and naturalness.
    
    Key Question: Do conversations feel authentic?
    """
    
    @staticmethod
    async def evaluate_conversation(conversation_id: UUID) -> Dict:
        """
        Evaluate single conversation quality.
        
        Metrics:
        - Response relevance
        - Sentiment consistency
        - Trust progression
        - Conversation flow
        """
        try:
            # Get conversation data
            async with db.pool.acquire() as conn:
                conv = await conn.fetchrow("""
                    SELECT 
                        state,
                        sentiment,
                        trust_level,
                        message_count,
                        reply_count,
                        started_at,
                        last_activity_at
                    FROM conversations
                    WHERE id = $1
                """, conversation_id)
                
                if not conv:
                    return {'score': 0.0, 'status': 'not_found'}
                
                # Get LLM quality metrics
                llm_metrics = await conn.fetch("""
                    SELECT metrics
                    FROM telemetry_events
                    WHERE event_type = 'llm_response_quality'
                    AND entity_id IN (
                        SELECT id::text FROM messages 
                        WHERE conversation_id = $1
                    )
                """, conversation_id)
            
            import json
            llm_data = [json.loads(row['metrics']) for row in llm_metrics]
            
            # Calculate metrics
            reply_rate = conv['reply_count'] / max(conv['message_count'], 1)
            avg_response_length = statistics.mean([m['length'] for m in llm_data]) if llm_data else 0
            within_limit_rate = sum(1 for m in llm_data if m['within_limit']) / len(llm_data) if llm_data else 1.0
            
            # Duration
            duration = (conv['last_activity_at'] - conv['started_at']).total_seconds() if conv['last_activity_at'] and conv['started_at'] else 0
            
            # Quality score
            quality_score = (
                reply_rate * 0.4 +  # 40% weight on engagement
                within_limit_rate * 0.3 +  # 30% weight on message quality
                (1.0 if duration > 300 else 0.5) * 0.3  # 30% weight on duration
            )
            
            return {
                'score': quality_score,
                'reply_rate': reply_rate,
                'avg_response_length': avg_response_length,
                'within_limit_rate': within_limit_rate,
                'duration_seconds': duration,
                'sentiment': conv['sentiment'],
                'trust_level': conv['trust_level'],
                'status': conv['state']
            }
        
        except Exception as e:
            logger.error(f"evaluate_conversation_failed: {str(e)}")
            return {'score': 0.0, 'status': 'error', 'error': str(e)}


class StrategyEvaluator:
    """
    Evaluates which strategies work best.
    
    Key Question: Which approach gets most engagement?
    """
    
    @staticmethod
    async def compare_strategies(campaign_id: UUID) -> Dict:
        """
        Compare strategy effectiveness.
        
        Metrics:
        - Reply rate by strategy
        - Average conversation depth
        - Success rate
        """
        try:
            async with db.pool.acquire() as conn:
                rows = await conn.fetch("""
                    SELECT 
                        current_strategy,
                        COUNT(*) as total,
                        SUM(CASE WHEN reply_count > 0 THEN 1 ELSE 0 END) as replied,
                        AVG(message_count) as avg_depth,
                        AVG(reply_count) as avg_replies
                    FROM conversations
                    WHERE campaign_id = $1
                    GROUP BY current_strategy
                """, campaign_id)
            
            strategies = {}
            for row in rows:
                strategy = row['current_strategy'] or 'adaptive'
                strategies[strategy] = {
                    'total_conversations': row['total'],
                    'reply_rate': row['replied'] / row['total'] if row['total'] > 0 else 0,
                    'avg_depth': float(row['avg_depth']) if row['avg_depth'] else 0,
                    'avg_replies': float(row['avg_replies']) if row['avg_replies'] else 0
                }
            
            # Find best strategy
            best_strategy = max(strategies.items(), 
                              key=lambda x: x[1]['reply_rate']) if strategies else None
            
            return {
                'strategies': strategies,
                'best_strategy': best_strategy[0] if best_strategy else None,
                'best_reply_rate': best_strategy[1]['reply_rate'] if best_strategy else 0
            }
        
        except Exception as e:
            logger.error(f"compare_strategies_failed: {str(e)}")
            return {'strategies': {}, 'error': str(e)}


class CampaignEvaluator:
    """
    Overall campaign evaluation.
    
    Combines all evaluators for comprehensive assessment.
    """
    
    @staticmethod
    async def evaluate_campaign(campaign_id: UUID) -> Dict:
        """
        Comprehensive campaign evaluation.
        
        Returns:
        - Overall score
        - Human-likeness assessment
        - Conversation quality
        - Strategy effectiveness
        - Carrier risk level
        - Actionable recommendations
        """
        try:
            # Run all evaluators
            timing_eval = await HumanLikenessEvaluator.evaluate_timing_patterns(campaign_id)
            red_flags = await HumanLikenessEvaluator.detect_carrier_red_flags(campaign_id)
            strategy_eval = await StrategyEvaluator.compare_strategies(campaign_id)
            
            # Get campaign stats
            async with db.pool.acquire() as conn:
                stats = await conn.fetchrow("""
                    SELECT 
                        COUNT(*) as total_conversations,
                        SUM(CASE WHEN reply_count > 0 THEN 1 ELSE 0 END) as engaged_conversations,
                        AVG(message_count) as avg_messages,
                        AVG(reply_count) as avg_replies
                    FROM conversations
                    WHERE campaign_id = $1
                """, campaign_id)
            
            # Calculate overall score
            overall_score = (
                timing_eval.get('score', 0) * 0.4 +  # 40% timing
                (1.0 - red_flags.get('risk_score', 0)) * 0.3 +  # 30% safety
                (stats['engaged_conversations'] / stats['total_conversations'] if stats['total_conversations'] > 0 else 0) * 0.3  # 30% engagement
            )
            
            # Generate recommendations
            recommendations = []
            
            if timing_eval.get('risk_level') == 'high':
                recommendations.append("⚠️ Increase timing variance to appear more human-like")
            
            if red_flags.get('risk_score', 0) > 0.5:
                recommendations.append("🚨 Reduce message frequency to avoid carrier flags")
            
            if stats['engaged_conversations'] / stats['total_conversations'] < 0.3:
                recommendations.append("📈 Try different strategies to improve engagement")
            
            return {
                'overall_score': overall_score,
                'grade': _get_grade(overall_score),
                'timing': timing_eval,
                'carrier_risk': red_flags,
                'strategy': strategy_eval,
                'stats': {
                    'total_conversations': stats['total_conversations'],
                    'engagement_rate': stats['engaged_conversations'] / stats['total_conversations'] if stats['total_conversations'] > 0 else 0,
                    'avg_messages': float(stats['avg_messages']) if stats['avg_messages'] else 0,
                    'avg_replies': float(stats['avg_replies']) if stats['avg_replies'] else 0
                },
                'recommendations': recommendations
            }
        
        except Exception as e:
            logger.error(f"evaluate_campaign_failed: {str(e)}")
            return {'overall_score': 0.0, 'status': 'error', 'error': str(e)}


# Helper functions

def _get_timing_recommendation(score: float) -> str:
    """Get recommendation based on timing score."""
    if score > 0.8:
        return "✅ Excellent timing variance - very human-like"
    elif score > 0.6:
        return "✓ Good timing patterns - minor improvements possible"
    elif score > 0.4:
        return "⚠️ Moderate timing variance - increase randomness"
    else:
        return "🚨 Low timing variance - high risk of detection"


def _get_grade(score: float) -> str:
    """Convert score to letter grade."""
    if score >= 0.9:
        return "A+"
    elif score >= 0.8:
        return "A"
    elif score >= 0.7:
        return "B"
    elif score >= 0.6:
        return "C"
    elif score >= 0.5:
        return "D"
    else:
        return "F"


# Global instances
human_likeness_evaluator = HumanLikenessEvaluator()
conversation_evaluator = ConversationQualityEvaluator()
strategy_evaluator = StrategyEvaluator()
campaign_evaluator = CampaignEvaluator()

