"""
LLM Service - Conversational Intelligence

Provides LLM capabilities for:
- Generating initial phishing messages
- Analyzing employee replies
- Generating context-aware responses
- Parsing admin commands
"""

import json
from typing import Dict, List, Optional
import logging

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

from config import settings


logger = logging.getLogger(__name__)


class LLMService:
    """
    LLM service for conversational intelligence.
    
    Uses OpenAI directly (GPT-4o-mini or GPT-4) for high-quality responses.
    """
    
    def __init__(self):
        """Initialize LLM service."""
        self.llm = ChatOpenAI(
            model=settings.llm_model,
            api_key=settings.openai_api_key,
            temperature=0.7,
            max_tokens=200  # Keep responses short for SMS
        )
        
        logger.info(f"llm_service_initialized: model={settings.llm_model}, provider=OpenAI")
    
    async def generate_initial_message(
        self,
        campaign_topic: str,
        campaign_strategy: str,
        recipient_name: Optional[str] = None,
        recipient_department: Optional[str] = None,
        success_patterns: Optional[List[Dict]] = None
    ) -> str:
        """
        Generate initial phishing message for a campaign.
        
        Args:
            campaign_topic: Topic of the phishing (e.g., "password reset")
            campaign_strategy: Strategy (e.g., "urgency", "authority", "fear")
            recipient_name: Optional recipient name for personalization
            recipient_department: Optional department for context
            success_patterns: Optional successful patterns to learn from
            
        Returns:
            Generated message text (max 160 chars)
        """
        # Build context from success patterns
        success_context = ""
        if success_patterns:
            success_context = "\n\nWhat has worked before:\n"
            for pattern in success_patterns[:3]:  # Top 3
                success_context += f"- {pattern.get('outcome')}: Used strategies {pattern.get('strategy_sequence')}\n"
        
        recipient_context = ""
        if recipient_name:
            recipient_context = f"\nRecipient: {recipient_name}"
        if recipient_department:
            recipient_context += f" ({recipient_department} department)"
        
        system_prompt = """You are a professional red team operator conducting authorized phishing simulations for security awareness training.

Your goal: Generate realistic, convincing phishing messages that test employee security awareness.

Guidelines:
1. Keep messages under 160 characters (SMS limit)
2. Create urgency or authority
3. Include a call-to-action (link, reply, etc.)
4. Sound natural and legitimate
5. Match the campaign strategy"""
        
        user_prompt = f"""Generate an initial phishing message for this campaign:

Topic: {campaign_topic}
Strategy: {campaign_strategy}{recipient_context}{success_context}

Generate a SHORT (max 160 chars), convincing SMS message:"""
        
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt)
        ]
        
        try:
            response = await self.llm.agenerate([messages])
            message_text = response.generations[0][0].text.strip()
            
            # Enforce length cap
            if len(message_text) > 160:
                message_text = message_text[:157] + "..."
            
            logger.info(
                f"initial_message_generated: topic={campaign_topic}, length={len(message_text)}"
            )
            
            return message_text
            
        except Exception as e:
            logger.error(f"llm_generation_failed: error={str(e)}")
            # Fallback to template
            return f"Hi, urgent: Please verify your account at bit.ly/verify-{campaign_topic.replace(' ', '-')}"
    
    async def analyze_reply(
        self,
        employee_reply: str,
        conversation_history: List[Dict]
    ) -> Dict:
        """
        Analyze employee reply to determine sentiment and next action.
        
        Args:
            employee_reply: What the employee said
            conversation_history: Previous messages in conversation
            
        Returns:
            Analysis dict with sentiment, trust_level, recommended_action
        """
        # Format conversation history
        history_text = "\n".join([
            f"{'Agent' if msg['sender'] == 'agent' else 'Employee'}: {msg['content']}"
            for msg in conversation_history[-5:]  # Last 5 messages
        ])
        
        system_prompt = """You are analyzing employee responses in a phishing simulation.

Analyze the reply and return JSON with:
{
    "sentiment": "suspicious" | "engaged" | "neutral" | "confused" | "hostile",
    "trust_level": "low" | "medium" | "high",
    "contains_question": true/false,
    "is_requesting_verification": true/false,
    "engagement_level": 0.0-1.0,
    "recommended_action": "build_trust" | "answer_question" | "push_action" | "back_off" | "abort"
}"""
        
        user_prompt = f"""Conversation history:
{history_text}

Employee just replied: "{employee_reply}"

Analyze this reply (return valid JSON only):"""
        
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt)
        ]
        
        try:
            response = await self.llm.agenerate([messages])
            analysis_text = response.generations[0][0].text.strip()
            
            # Parse JSON
            # Remove markdown code blocks if present
            if "```json" in analysis_text:
                analysis_text = analysis_text.split("```json")[1].split("```")[0]
            elif "```" in analysis_text:
                analysis_text = analysis_text.split("```")[1].split("```")[0]
            
            analysis = json.loads(analysis_text.strip())
            
            logger.info(
                f"reply_analyzed: sentiment={analysis.get('sentiment')}, trust_level={analysis.get('trust_level')}, recommended_action={analysis.get('recommended_action')}"
            )
            
            return analysis
            
        except Exception as e:
            logger.error(f"reply_analysis_failed: error={str(e)}")
            # Fallback analysis
            return {
                "sentiment": "neutral",
                "trust_level": "medium",
                "contains_question": "?" in employee_reply,
                "is_requesting_verification": any(word in employee_reply.lower() for word in ['verify', 'confirm', 'real', 'legitimate']),
                "engagement_level": 0.5,
                "recommended_action": "answer_question" if "?" in employee_reply else "push_action"
            }
    
    async def generate_response(
        self,
        employee_reply: str,
        conversation_history: List[Dict],
        analysis: Dict,
        current_strategy: str,
        success_patterns: Optional[List[Dict]] = None
    ) -> str:
        """
        Generate response to employee reply.
        
        Args:
            employee_reply: What employee said
            conversation_history: Previous messages
            analysis: Analysis from analyze_reply()
            current_strategy: Current conversation strategy
            success_patterns: Optional successful patterns to learn from
            
        Returns:
            Generated response text (max 160 chars)
        """
        # Format conversation history
        history_text = "\n".join([
            f"{'Agent' if msg['sender'] == 'agent' else 'Employee'}: {msg['content']}"
            for msg in conversation_history[-5:]  # Last 5 messages
        ])
        
        # Success patterns context
        success_context = ""
        if success_patterns:
            success_context = "\n\nProven tactics:\n"
            for pattern in success_patterns[:2]:  # Top 2
                success_context += f"- {pattern.get('outcome')}: {', '.join(pattern.get('message_sequence', [])[:2])}\n"
        
        system_prompt = """You are a red team operator conducting a phishing simulation.

Your goal: Generate a convincing, natural response that advances the phishing attempt.

Guidelines:
1. Keep response under 160 characters (SMS limit)
2. Stay in character (IT support, manager, etc.)
3. Address employee's concerns naturally
4. Move conversation toward goal (click link, provide info, etc.)
5. Sound human and conversational
6. Match the recommended action from analysis"""
        
        user_prompt = f"""Conversation so far:
{history_text}

Employee replied: "{employee_reply}"

Analysis: {json.dumps(analysis, indent=2)}
Current strategy: {current_strategy}
Recommended action: {analysis.get('recommended_action')}{success_context}

Generate a SHORT (max 160 chars), natural response that advances the simulation:"""
        
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt)
        ]
        
        try:
            response = await self.llm.agenerate([messages])
            response_text = response.generations[0][0].text.strip()
            
            # Remove quotes if LLM wrapped response
            if response_text.startswith('"') and response_text.endswith('"'):
                response_text = response_text[1:-1]
            
            # Enforce length cap
            if len(response_text) > 160:
                response_text = response_text[:157] + "..."
            
            logger.info(
                f"response_generated: length={len(response_text)}, strategy={current_strategy}"
            )
            
            return response_text
            
        except Exception as e:
            logger.error(f"response_generation_failed: error={str(e)}")
            # Fallback response
            if analysis.get('contains_question'):
                return "Yes, this is legitimate. You can verify by calling our help desk."
            else:
                return "Thanks for your reply. Please complete the verification at your earliest convenience."
    
    async def parse_admin_command(
        self,
        admin_message: str
    ) -> Dict:
        """
        Parse admin natural language command into structured intent.
        
        Args:
            admin_message: Admin's message
            
        Returns:
            Intent dict with action and parameters
        """
        system_prompt = """You are parsing admin commands for a phishing simulation system.

Parse the command and return JSON with:
{
    "action": "create_campaign" | "inject_message" | "pause_campaign" | "view_status" | "import_history",
    "parameters": {
        // Action-specific parameters
    }
}

Examples:
- "Start phishing about password reset for sales team" → 
  {"action": "create_campaign", "parameters": {"topic": "password reset", "department": "sales"}}
  
- "Add message 'This is urgent' to campaign X" →
  {"action": "inject_message", "parameters": {"message": "This is urgent", "campaign_id": "X"}}
"""
        
        user_prompt = f"""Parse this admin command:

"{admin_message}"

Return JSON only:"""
        
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt)
        ]
        
        try:
            response = await self.llm.agenerate([messages])
            intent_text = response.generations[0][0].text.strip()
            
            # Parse JSON
            if "```json" in intent_text:
                intent_text = intent_text.split("```json")[1].split("```")[0]
            elif "```" in intent_text:
                intent_text = intent_text.split("```")[1].split("```")[0]
            
            intent = json.loads(intent_text.strip())
            
            logger.info(f"admin_command_parsed: action={intent.get('action')}")
            
            return intent
            
        except Exception as e:
            logger.error(f"admin_command_parse_failed: error={str(e)}")
            return {
                "action": "unknown",
                "parameters": {},
                "error": str(e)
            }


# Global LLM service instance
llm_service = LLMService()

