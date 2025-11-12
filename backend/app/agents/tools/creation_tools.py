"""
Creation Tools for Orchestrator Agent

Tools for:
- Creating campaigns
- Generating messages
- Spawning conversation agents
- Scheduling messages
"""

from typing import List, Dict, Annotated, Optional
from uuid import UUID, uuid4
from datetime import datetime
import asyncio
import logging

from langchain_core.tools import tool

from app.models.database import db
from app.services.scheduler_service import scheduler_service
from config import settings

logger = logging.getLogger(__name__)


# Global reference to orchestrator (set on initialization)
_orchestrator = None

def set_orchestrator(orchestrator):
    """Set global orchestrator reference."""
    global _orchestrator
    _orchestrator = orchestrator


# ============================================================================
# Tool 1: Create Campaign (Async with Progress)
# ============================================================================

@tool
async def create_campaign_async(
    topic: Annotated[str, "Campaign topic (e.g., 'password reset', 'account verification')"],
    phone_numbers: Annotated[List[str], "List of phone numbers to target"],
    generate_messages: Annotated[bool, "True to generate messages with LLM, False to use custom"],
    strategy: Annotated[str, "Strategy: 'build_trust', 'urgency', 'authority', 'fear'"] = "adaptive",
    custom_messages: Annotated[Optional[List[str]], "Custom messages if generate_messages=False"] = None
) -> str:
    """
    Create a phishing campaign with async progress updates.
    
    Handles:
    - Message generation (batched if LLM)
    - Recipient creation
    - Conversation creation
    - Agent spawning
    - Message scheduling
    
    Returns: Success message with campaign details
    """
    try:
        # Create campaign in DB
        campaign_id = await db.create_campaign(
            name=f"{topic} - {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            topic=topic,
            strategy=strategy
        )
        
        logger.info(f"campaign_created: campaign_id={campaign_id}, recipients={len(phone_numbers)}")
        
        # Phase 1: Messages
        if generate_messages:
            # Send progress update
            if _orchestrator:
                await _orchestrator.send_progress(f"⏳ Generating {len(phone_numbers)} messages...")
            
            messages = await _generate_messages_batched(topic, len(phone_numbers), strategy)
            
            if _orchestrator:
                await _orchestrator.send_progress(f"✅ Messages generated!")
        
        else:
            # Use custom messages (cycle through them)
            if not custom_messages:
                custom_messages = [f"Message about {topic}"]
            
            messages = [custom_messages[i % len(custom_messages)] for i in range(len(phone_numbers))]
        
        # Phase 2: Create recipients & conversations
        if _orchestrator:
            await _orchestrator.send_progress(f"⏳ Creating {len(phone_numbers)} conversations...")
        
        conversation_data = []
        
        for phone, message in zip(phone_numbers, messages):
            # Create recipient
            recipient_id = await db.create_recipient(phone_number=phone)
            
            # Create conversation
            conv_id = await db.create_conversation(
                campaign_id=campaign_id,
                recipient_id=recipient_id,
                initial_strategy=strategy
            )
            
            conversation_data.append({
                'conversation_id': str(conv_id),
                'phone_number': phone,
                'message': message,
                'recipient_id': str(recipient_id)
            })
        
        if _orchestrator:
            await _orchestrator.send_progress(f"✅ Conversations created!")
        
        # Phase 3: Spawn agents
        if _orchestrator:
            await _orchestrator.send_progress(f"⏳ Spawning {len(conversation_data)} agents...")
        
        await _spawn_agents_batched(conversation_data, topic, strategy)
        
        if _orchestrator:
            await _orchestrator.send_progress(f"✅ Agents spawned!")
        
        # Phase 4: Schedule messages
        if _orchestrator:
            await _orchestrator.send_progress(f"⏳ Scheduling {len(messages)} messages...")
        
        # Prepare messages for scheduling
        messages_to_schedule = [
            {
                'id': str(uuid4()),
                'to': conv['phone_number'],
                'content': conv['message'],
                'conversation_id': conv['conversation_id']
            }
            for conv in conversation_data
        ]
        
        scheduled = await scheduler_service.schedule_campaign_messages(
            campaign_id=campaign_id,
            messages=messages_to_schedule
        )
        
        if _orchestrator:
            await _orchestrator.send_progress(f"✅ Messages scheduled!")
        
        # Update orchestrator state
        if _orchestrator:
            _orchestrator.state.active_campaigns[str(campaign_id)] = {
                'id': str(campaign_id),
                'topic': topic,
                'conversation_count': len(conversation_data),
                'created_at': datetime.now().isoformat()
            }
            _orchestrator.state.update_metrics('total_campaigns', 1)
            _orchestrator.state.update_metrics('total_conversations', len(conversation_data))
        
        # Return success message
        first_send_time = scheduled[0]['scheduled_time'] if scheduled else "N/A"
        
        return f"""✅ Campaign Created Successfully!

Campaign ID: {campaign_id}
Topic: {topic}
Conversations: {len(conversation_data)}
Messages scheduled: {len(scheduled)}
First message: {first_send_time}

📊 Scheduling:
- Adaptive ACTIVE/IDLE sessions
- Burst-and-pause pattern
- Expected completion: Today

Check the queue visualization →"""
        
    except Exception as e:
        logger.error(f"campaign_creation_failed: {str(e)}")
        return f"❌ Campaign creation failed: {str(e)}"


# ============================================================================
# Tool 2: Generate Messages (Batched)
# ============================================================================

async def _generate_messages_batched(
    topic: str,
    count: int,
    strategy: str
) -> List[str]:
    """
    Generate messages in batches to avoid overwhelming LLM.
    
    Generates 10 at a time with progress updates.
    """
    from app.services.llm import llm_service
    
    messages = []
    batch_size = 10
    
    for i in range(0, count, batch_size):
        batch_count = min(batch_size, count - i)
        
        # Generate batch
        batch_messages = []
        for j in range(batch_count):
            message = await llm_service.generate_initial_message(
                campaign_topic=topic,
                campaign_strategy=strategy
            )
            batch_messages.append(message)
        
        messages.extend(batch_messages)
        
        # Progress update
        if _orchestrator:
            await _orchestrator.send_progress(f"⏳ Generated {len(messages)}/{count} messages...")
        
        # Small delay to avoid rate limits
        await asyncio.sleep(0.5)
    
    return messages


# ============================================================================
# Tool 3: Spawn Agents (Batched)
# ============================================================================

async def _spawn_agents_batched(
    conversation_data: List[Dict],
    topic: str,
    strategy: str
):
    """
    Spawn conversation agents in batches.
    
    Creates 20 at a time to avoid memory issues.
    """
    from app.agents.conversation import ConversationAgent
    
    batch_size = 20
    
    for i in range(0, len(conversation_data), batch_size):
        batch = conversation_data[i:i+batch_size]
        
        for conv in batch:
            # Create agent context
            context = {
                'conversation_id': conv['conversation_id'],
                'phone_number': conv['phone_number'],
                'campaign_topic': topic,
                'strategy': strategy,
                'initial_message': conv['message'],
                'instructions': _generate_agent_instructions(
                    conv['phone_number'],
                    topic,
                    strategy,
                    conv['message']
                )
            }
            
            # Create agent
            agent = ConversationAgent(
                conversation_id=conv['conversation_id'],
                context=context
            )
            
            # Save agent state to DB (CRITICAL: stores instructions and goal in config)
            await agent.state.save_to_db()
            
            # Register with orchestrator
            if _orchestrator:
                _orchestrator.state.spawned_agents[conv['conversation_id']] = agent
                _orchestrator.state.agent_contexts[conv['conversation_id']] = context
        
        # Progress update
        if _orchestrator:
            spawned_count = min(i + batch_size, len(conversation_data))
            await _orchestrator.send_progress(f"⏳ Spawned {spawned_count}/{len(conversation_data)} agents...")
        
        # Small delay
        await asyncio.sleep(0.1)
    
    if _orchestrator:
        _orchestrator.state.update_metrics('agents_spawned', len(conversation_data))


def _generate_agent_instructions(
    phone_number: str,
    topic: str,
    strategy: str,
    initial_message: str
) -> str:
    """
    Generate instructions for conversation agent.
    """
    return f"""You are conducting a phishing simulation with {phone_number}.

CAMPAIGN: {topic}
STRATEGY: {strategy}

YOUR INITIAL MESSAGE: "{initial_message}"

ROLE:
- Impersonate: IT Support / Security Team / Management
- Goal: Get employee to click link / provide credentials / call number
- Approach: {strategy}

WHEN EMPLOYEE REPLIES:
1. Analyze their response (sentiment, trust level)
2. Generate SHORT response (max 160 chars)
3. Stay in character
4. Address their concerns if suspicious
5. Push for action if engaged

STRATEGIES:
- build_trust: Establish legitimacy, offer verification
- urgency: Create time pressure, deadlines
- authority: Use position, official tone
- fear: Security threats, account lockout

Be natural, convincing, and adaptive to their responses."""


# ============================================================================
# Tool 4: Add Recipient to Campaign
# ============================================================================

@tool
async def add_recipient_to_campaign(
    campaign_id: Annotated[str, "Campaign ID to add recipient to"],
    phone_number: Annotated[str, "Phone number to add"],
    custom_message: Annotated[str, "Optional custom message for this recipient"] = None
) -> str:
    """
    Add a recipient to existing campaign mid-stream.
    
    Message goes to END of queue.
    """
    try:
        # Get campaign
        campaign = await db.get_campaign(UUID(campaign_id))
        if not campaign:
            return f"❌ Campaign {campaign_id} not found"
        
        # Create recipient
        recipient_id = await db.create_recipient(phone_number=phone_number)
        
        # Create conversation
        conv_id = await db.create_conversation(
            campaign_id=UUID(campaign_id),
            recipient_id=recipient_id,
            initial_strategy=campaign.get('strategy', 'adaptive')
        )
        
        # Generate or use custom message
        if custom_message:
            message = custom_message
        else:
            from app.services.llm import llm_service
            message = await llm_service.generate_initial_message(
                campaign_topic=campaign['topic'],
                campaign_strategy=campaign.get('strategy', 'adaptive')
            )
        
        # Spawn agent
        context = {
            'conversation_id': str(conv_id),
            'phone_number': phone_number,
            'campaign_topic': campaign['topic'],
            'strategy': campaign.get('strategy', 'adaptive'),
            'initial_message': message,
            'instructions': _generate_agent_instructions(
                phone_number,
                campaign['topic'],
                campaign.get('strategy', 'adaptive'),
                message
            )
        }
        
        from app.agents.conversation import ConversationAgent
        agent = ConversationAgent(str(conv_id), context)
        
        if _orchestrator:
            _orchestrator.state.spawned_agents[str(conv_id)] = agent
            _orchestrator.state.agent_contexts[str(conv_id)] = context
        
        # Schedule message (goes to END)
        message_data = {
            'id': str(uuid4()),
            'to': phone_number,
            'content': message,
            'conversation_id': str(conv_id)
        }
        
        scheduled = await scheduler_service.schedule_message(message_data)
        
        return f"""✅ Recipient added to campaign!

Phone: {phone_number}
Conversation ID: {conv_id}
Scheduled: {scheduled['scheduled_time']}
Position: END of queue

Agent spawned and ready."""
        
    except Exception as e:
        logger.error(f"add_recipient_failed: {str(e)}")
        return f"❌ Failed to add recipient: {str(e)}"

