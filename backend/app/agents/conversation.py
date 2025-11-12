"""
Conversation Agent - Per-Employee AI Agent

Simple workflow (no tools):
1. Receive employee reply
2. Cancel pending reply if exists (multiple replies)
3. Analyze reply (LLM)
4. Generate response (LLM)
5. Schedule response (scheduler_service - triggers CASCADE)

Stateful: Survives restarts, loads from DB
"""

from datetime import datetime, timezone
from typing import Dict, Optional
from uuid import UUID, uuid4
import json
import logging
import time

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

from app.agents.state.conversation_state import ConversationAgentState
from app.services.scheduler_service import scheduler_service
from app.models.database import db
from app.telemetry.metrics import metrics_collector
from config import settings

logger = logging.getLogger(__name__)


class ConversationAgent:
    """
    One agent per employee conversation.
    
    Workflow-based (no tools), stateful, persistent.
    """
    
    def __init__(self, conversation_id: str, context: Dict):
        """
        Initialize conversation agent.
        
        Args:
            conversation_id: Conversation ID
            context: {
                phone_number, campaign_topic, strategy,
                initial_message, instructions
            }
        """
        self.conversation_id = conversation_id
        self.phone_number = context['phone_number']
        self.instructions = context['instructions']
        self.strategy = context.get('strategy', 'adaptive')
        self.goal = context.get('goal', 'click_link')
        
        # State (persistent)
        self.state = ConversationAgentState(
            conversation_id=conversation_id,
            phone_number=self.phone_number,
            campaign_id=context.get('campaign_id', ''),
            instructions=self.instructions,
            strategy=self.strategy,
            goal=self.goal
        )
        
        # LLM (no tools - just direct calls)
        self.llm = ChatOpenAI(
            model=settings.llm_model,
            api_key=settings.openai_api_key,
            temperature=0.7,
            max_tokens=200  # Keep responses short
        )
        
        logger.info(f"conversation_agent_created: conv_id={conversation_id}, phone={self.phone_number}")
    
    @classmethod
    async def restore_from_db(cls, conversation_id: str) -> 'ConversationAgent':
        """
        Restore agent from database on system restart.
        
        Loads all state and recreates agent.
        """
        # Load state from DB
        state = await ConversationAgentState.load_from_db(conversation_id)
        
        # Create context from state
        context = {
            'conversation_id': conversation_id,
            'phone_number': state.phone_number,
            'campaign_id': state.campaign_id,
            'strategy': state.strategy,
            'instructions': state.instructions,
            'goal': state.goal
        }
        
        # Create agent
        agent = cls(conversation_id, context)
        agent.state = state  # Use loaded state
        
        logger.info(f"conversation_agent_restored: conv_id={conversation_id}")
        
        return agent
    
    # ========================================================================
    # Main Workflow
    # ========================================================================
    
    async def handle_employee_reply(self, reply_text: str) -> Dict:
        """
        Main workflow when employee replies.
        
        Handles multiple rapid replies by cancelling pending responses and generating one new response.
        """
        logger.info(f"employee_reply_received: conv_id={self.conversation_id}, length={len(reply_text)}")
        
        # STEP 1: Cancel pending reply if exists (multiple replies edge case)
        pending_cancelled = await self._cancel_pending_reply()
        if pending_cancelled:
            logger.info(f"multiple_replies_detected: cancelled_pending, will generate new response")
        
        # STEP 2: Save employee reply to DB (mark as 'sent', not 'pending'!)
        # Use simulation time if available
        from app.services.time_controller import time_controller
        if time_controller:
            current_time = await time_controller.get_current_time()
        else:
            current_time = datetime.now(timezone.utc).replace(tzinfo=None)
        
        await db.create_message(
            conversation_id=UUID(self.conversation_id),
            content=reply_text,
            sender='employee',
            status='sent',  # Critical: employee messages are already sent!
            sent_at=current_time
        )
        
        # Update state
        self.state.employee_replies.append({
            "content": reply_text,
            "timestamp": current_time.isoformat()
        })
        self.state.reply_count += 1
        
        # Add employee message to message_history for LLM context
        self.state.message_history.append({
            "sender": "employee",
            "content": reply_text,
            "timestamp": current_time.isoformat()
        })
        
        # STEP 3: Get ALL recent unresponded employee messages
        # This handles the case where employee sent multiple messages before we replied
        recent_employee_messages = await self._get_recent_employee_messages()
        combined_employee_text = "\n".join(recent_employee_messages)
        
        logger.info(f"processing_employee_messages: count={len(recent_employee_messages)}, combined_length={len(combined_employee_text)}")
        
        # Track employee reply metrics
        try:
            # Calculate time since last agent message
            last_agent_msg_time = None
            for msg in reversed(self.state.message_history):
                if msg.get('sender') == 'agent' and msg.get('timestamp'):
                    last_agent_msg_time = datetime.fromisoformat(msg['timestamp'])
                    break
            
            time_since_last = (current_time - last_agent_msg_time).total_seconds() if last_agent_msg_time else 0
            
            await metrics_collector.track_employee_reply(
                conversation_id=UUID(self.conversation_id),
                reply_text=reply_text,
                time_since_last_agent_message_seconds=time_since_last
            )
        except Exception as e:
            logger.error(f"track_employee_reply_failed: {str(e)}")
        
        # STEP 4: Analyze ALL recent replies (LLM call 1)
        analysis = await self._analyze_reply(combined_employee_text)
        
        # Update state based on analysis
        self.state.sentiment = analysis.get('sentiment', 'neutral')
        self.state.trust_level = analysis.get('trust_level', 'low')
        
        # STEP 5: Generate response considering ALL recent messages (LLM call 2)
        llm_start_time = time.time()
        response_text = await self._generate_response(combined_employee_text, analysis)
        llm_duration_ms = (time.time() - llm_start_time) * 1000
        
        # STEP 6: Schedule response (scheduler_service - triggers CASCADE)
        message_id = uuid4()
        scheduled = await scheduler_service.schedule_message(
            message_data={
                'id': str(message_id),
                'to': self.phone_number,
                'content': response_text,
                'conversation_id': self.conversation_id,
                'is_reply': True
            },
            is_reply=True  # This triggers CASCADE automatically!
        )
        
        # Track LLM response quality
        try:
            await metrics_collector.track_llm_response_quality(
                message_id=message_id,
                response_text=response_text,
                analysis=analysis,
                generation_time_ms=llm_duration_ms
            )
        except Exception as e:
            logger.error(f"track_llm_quality_failed: {str(e)}")
        
        # Update state
        self.state.message_history.append({
            "sender": "agent",
            "content": response_text,
            "scheduled_time": scheduled['scheduled_time'],
            "timestamp": current_time.isoformat()
        })
        self.state.message_count += 1
        self.state.last_activity = current_time
        
        # Save to DB
        await self.state.save_to_db()
        
        logger.info(f"reply_handled: conv_id={self.conversation_id}, response_scheduled={scheduled['scheduled_time']}, addressed_messages={len(recent_employee_messages)}")
        
        return {
            'response': response_text,
            'scheduled_time': scheduled['scheduled_time'],
            'sentiment': self.state.sentiment,
            'trust_level': self.state.trust_level,
            'confidence': scheduled.get('confidence', 0.0)
        }
    
    # ========================================================================
    # Private Workflow Steps
    # ========================================================================
    
    async def _get_recent_employee_messages(self) -> list[str]:
        """
        Get all employee messages sent since the last agent message.
        
        This handles the case where employee sends multiple messages before we reply.
        Returns list of message contents in chronological order.
        """
        if not db.pool:
            return []
        
        async with db.pool.acquire() as conn:
            # Get the last sent agent message
            last_agent_msg = await conn.fetchrow("""
                SELECT sent_at
                FROM messages
                WHERE conversation_id = $1
                AND sender = 'agent'
                AND status = 'sent'
                ORDER BY sent_at DESC
                LIMIT 1
            """, UUID(self.conversation_id))
            
            if last_agent_msg and last_agent_msg['sent_at']:
                # Get all employee messages after the last agent message
                rows = await conn.fetch("""
                    SELECT content
                    FROM messages
                    WHERE conversation_id = $1
                    AND sender = 'employee'
                    AND sent_at > $2
                    ORDER BY sent_at ASC
                """, UUID(self.conversation_id), last_agent_msg['sent_at'])
            else:
                # No agent message yet, get all employee messages
                rows = await conn.fetch("""
                    SELECT content
                    FROM messages
                    WHERE conversation_id = $1
                    AND sender = 'employee'
                    ORDER BY sent_at ASC
                """, UUID(self.conversation_id))
            
            return [row['content'] for row in rows]
    
    async def _cancel_pending_reply(self) -> bool:
        """
        Check for pending unsent agent reply and cancel it.
        
        Handles edge case: employee sends multiple messages before we respond.
        We need to cancel the scheduled (not yet sent) agent reply and generate a new one.
        """
        if not db.pool:
            return False
        
        async with db.pool.acquire() as conn:
            # Find any scheduled agent messages in this conversation that haven't been sent yet
            rows = await conn.fetch("""
                SELECT id, content
                FROM messages
                WHERE conversation_id = $1
                AND sender = 'agent'
                AND status = 'scheduled'
                AND sent_at IS NULL
                ORDER BY created_at DESC
            """, UUID(self.conversation_id))
        
        if rows:
            # Cancel all pending agent replies (usually just 1, but could be multiple if rapid replies)
            cancelled_count = 0
            for row in rows:
                await db.update_message(
                    message_id=row['id'],
                    status='cancelled'
                )
                cancelled_count += 1
                logger.info(f"cancelled_pending_reply: message_id={row['id']}, content={row['content'][:50]}")
            
            return cancelled_count > 0
        
        return False
    
    async def _analyze_reply(self, reply_text: str) -> Dict:
        """
        Analyze employee reply (LLM call 1).
        
        Returns: {sentiment, trust_level, contains_question, recommended_action}
        """
        # Get recent employee replies (in case multiple)
        recent_replies = [r['content'] for r in self.state.employee_replies[-3:]]
        combined_context = "\n".join(recent_replies)
        
        prompt = f"""Analyze employee replies in phishing simulation:

Employee said: "{combined_context}"

Conversation history: {self._format_history()}
Strategy: {self.strategy}

Return JSON:
{{
    "sentiment": "suspicious" | "engaged" | "neutral" | "confused" | "hostile",
    "trust_level": "low" | "medium" | "high",
    "contains_question": true/false,
    "engagement_level": 0.0-1.0,
    "recommended_action": "build_trust" | "answer_question" | "push_action" | "back_off"
}}"""
        
        try:
            response = await self.llm.ainvoke([
                SystemMessage(content="You analyze phishing simulation responses. Return valid JSON only."),
                HumanMessage(content=prompt)
            ])
            
            # Parse JSON
            content = response.content.strip()
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]
            
            analysis = json.loads(content)
            
            return analysis
        
        except Exception as e:
            logger.error(f"analysis_failed: {str(e)}")
            # Fallback
            return {
                "sentiment": "neutral",
                "trust_level": "medium",
                "contains_question": "?" in reply_text,
                "engagement_level": 0.5,
                "recommended_action": "answer_question" if "?" in reply_text else "push_action"
            }
    
    async def _generate_response(self, reply_text: str, analysis: Dict) -> str:
        """
        Generate response (LLM call 2).
        
        Capped at 160 characters.
        reply_text can contain multiple messages (separated by newlines) if employee sent multiple.
        """
        # Format employee messages nicely
        if '\n' in reply_text:
            employee_messages = reply_text.split('\n')
            formatted_employee = '\n'.join([f'  - "{msg}"' for msg in employee_messages])
            prompt = f"""Generate SHORT response (max 160 chars) for phishing simulation:

Employee sent multiple messages:
{formatted_employee}

Analysis: {json.dumps(analysis)}
Strategy: {self.strategy}
Goal: {self.goal}

History: {self._format_history()}

Address ALL their messages in ONE natural, convincing response. Stay in character. Max 160 chars!"""
        else:
            prompt = f"""Generate SHORT response (max 160 chars) for phishing simulation:

Employee: "{reply_text}"
Analysis: {json.dumps(analysis)}
Strategy: {self.strategy}
Goal: {self.goal}

History: {self._format_history()}

Generate natural, convincing response. Stay in character. Max 160 chars!"""
        
        try:
            response = await self.llm.ainvoke([
                SystemMessage(content=self.instructions),
                HumanMessage(content=prompt)
            ])
            
            # Enforce 160 char limit
            response_text = response.content.strip()
            
            # Remove quotes if LLM wrapped it
            if response_text.startswith('"') and response_text.endswith('"'):
                response_text = response_text[1:-1]
            
            if len(response_text) > 160:
                response_text = response_text[:157] + "..."
            
            return response_text
        
        except Exception as e:
            logger.error(f"generation_failed: {str(e)}")
            # Fallback
            if analysis.get('contains_question'):
                return "Yes, this is legitimate. You can verify by calling our help desk."
            else:
                return "Thanks for your response. Please complete the verification."
    
    def _format_history(self) -> str:
        """Format conversation history for LLM context."""
        if not self.state.message_history:
            return "No history yet"
        
        formatted = []
        for msg in self.state.message_history[-5:]:  # Last 5 messages
            sender = "Agent" if msg.get('sender') == 'agent' else "Employee"
            formatted.append(f"{sender}: {msg.get('content', '')}")
        
        return "\n".join(formatted)
    
    async def end_conversation(self, reason: str):
        """
        End conversation (success or abandon).
        """
        self.state.status = 'completed' if 'success' in reason.lower() else 'abandoned'
        
        await db.update_conversation(
            conversation_id=UUID(self.conversation_id),
            state=self.state.status,
            completed_at=datetime.now()
        )
        
        logger.info(f"conversation_ended: conv_id={self.conversation_id}, reason={reason}")

