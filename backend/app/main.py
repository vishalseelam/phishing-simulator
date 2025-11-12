"""
FastAPI Application - GhostEye v2

Complete agent-based phishing orchestrator.
"""

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from pydantic import BaseModel
from uuid import UUID
import logging

from config import settings
from app.models.database import db
from app.agents.initialization import initialize_agent_system, shutdown_agent_system
import app.agents.orchestrator as orchestrator_module
from app.api.websocket import connection_manager
from app.api import time_api, telemetry_api

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager."""
    # Startup
    logger.info("starting_ghosteye_v2")
    
    # Initialize database
    await db.connect()
    logger.info("database_connected")
    
    # Initialize agent system (orchestrator + conversation agents)
    await initialize_agent_system()
    logger.info("agent_system_initialized")
    
    # Connect time controller to scheduler
    from app.services import scheduler_service
    from app.services.time_controller import time_controller
    scheduler_service.time_controller = time_controller
    logger.info("time_controller_connected")
    
    logger.info("ghosteye_v2_ready")
    
    yield
    
    # Shutdown
    logger.info("shutting_down_ghosteye_v2")
    
    # Save all agent state
    await shutdown_agent_system()
    
    # Disconnect database
    await db.disconnect()
    
    logger.info("ghosteye_v2_shutdown_complete")


# Create FastAPI app
app = FastAPI(
    title="GhostEye v2",
    description="AI-Powered Multi-Conversation Phishing Orchestrator",
    version="2.0.0",
    lifespan=lifespan
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(time_api.router)
app.include_router(telemetry_api.router, prefix="/api")


# ============================================================================
# Request/Response Models
# ============================================================================

class ChatRequest(BaseModel):
    """Admin chat request."""
    message: str


class EmployeeReplyRequest(BaseModel):
    """Employee reply simulation."""
    conversation_id: str
    message: str


# ============================================================================
# Main Endpoints
# ============================================================================

@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "service": "GhostEye v2",
        "version": "2.0.0",
        "status": "operational",
        "agents": {
            "orchestrator": "active",
            "conversations": len(orchestrator_module.orchestrator_agent.state.spawned_agents) if orchestrator_module.orchestrator_agent else 0
        }
    }


@app.get("/health")
async def health():
    """Health check."""
    return {
        "status": "healthy",
        "database": "connected" if db.pool else "disconnected",
        "agents": len(orchestrator_module.orchestrator_agent.state.spawned_agents) if orchestrator_module.orchestrator_agent else 0
    }


# ============================================================================
# Admin Chat Endpoint
# ============================================================================

@app.post("/api/admin/chat")
async def chat_with_orchestrator(request: ChatRequest):
    """
    Chat with orchestrator agent.
    
    Fully autonomous conversation.
    """
    if not orchestrator_module.orchestrator_agent:
        raise HTTPException(status_code=503, detail="Orchestrator not initialized")
    
    try:
        response = await orchestrator_module.orchestrator_agent.process_admin_message(request.message)
        
        return {
            "success": True,
            "message": response
        }
    
    except Exception as e:
        logger.error(f"chat_failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Employee Simulation Endpoint
# ============================================================================

@app.post("/api/employee/reply")
async def simulate_employee_reply(request: EmployeeReplyRequest):
    """
    Simulate employee replying.
    
    Triggers conversation agent workflow + CASCADE.
    """
    if not orchestrator_module.orchestrator_agent:
        raise HTTPException(status_code=503, detail="Orchestrator not initialized")
    
    # Get conversation agent
    agent = orchestrator_module.orchestrator_agent.state.spawned_agents.get(request.conversation_id)
    
    if not agent:
        raise HTTPException(status_code=404, detail="Conversation agent not found")
    
    try:
        # Handle reply (triggers CASCADE automatically)
        result = await agent.handle_employee_reply(request.message)
        
        return {
            "success": True,
            "response": result['response'],
            "scheduled_time": result['scheduled_time'],
            "sentiment": result.get('sentiment'),
            "cascade_triggered": True
        }
    
    except Exception as e:
        logger.error(f"employee_reply_failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Queue Endpoints
# ============================================================================

@app.get("/api/queue/all")
async def get_queue():
    """
    Get all scheduled messages (time-sorted).
    
    For left panel visualization.
    """
    try:
        if not db.pool:
            return {"messages": []}
        
        async with db.pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT 
                    m.id,
                    r.phone_number,
                    m.content,
                    m.ideal_send_time as scheduled_time,
                    m.status,
                    m.conversation_id
                FROM messages m
                JOIN conversations c ON m.conversation_id = c.id
                JOIN recipients r ON c.recipient_id = r.id
                WHERE m.status IN ('scheduled', 'pending')
                AND m.ideal_send_time IS NOT NULL
                ORDER BY m.ideal_send_time
            """)
        
        messages = [
            {
                "id": str(row['id']),
                "phone_number": row['phone_number'],
                "content": row['content'],
                "scheduled_time": row['scheduled_time'].isoformat(),
                "status": row['status'],
                "conversation_id": str(row['conversation_id'])
            }
            for row in rows
        ]
        
        return {"messages": messages}
    
    except Exception as e:
        logger.error(f"get_queue_failed: {str(e)}")
        return {"messages": []}


@app.get("/api/conversations/all")
async def get_all_conversations():
    """
    Get all conversations.
    
    For conversation list.
    """
    try:
        if not db.pool:
            return {"conversations": []}
        
        async with db.pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT 
                    c.id,
                    r.phone_number,
                    c.state,
                    c.message_count,
                    c.reply_count
                FROM conversations c
                JOIN recipients r ON c.recipient_id = r.id
                WHERE c.state NOT IN ('completed', 'abandoned')
                ORDER BY c.last_activity_at DESC
            """)
        
        conversations = [
            {
                "id": str(row['id']),
                "phone_number": row['phone_number'],
                "state": row['state'],
                "message_count": row['message_count'],
                "reply_count": row['reply_count']
            }
            for row in rows
        ]
        
        return {"conversations": conversations}
    
    except Exception as e:
        logger.error(f"get_conversations_failed: {str(e)}")
        return {"conversations": []}


@app.get("/api/conversation/{conversation_id}/messages")
async def get_conversation_messages(conversation_id: UUID):
    """
    Get messages for a conversation.
    
    For right panel (employee simulator).
    """
    try:
        messages = await db.get_conversation_messages(conversation_id)
        
        return {
            "success": True,
            "messages": messages
        }
    
    except Exception as e:
        logger.error(f"get_messages_failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/employee/conversation/{conversation_id}/messages")
async def get_employee_conversation_messages(conversation_id: UUID):
    """
    Get messages for employee simulator (alternative endpoint).
    """
    return await get_conversation_messages(conversation_id)


# ============================================================================
# WebSocket Endpoint
# ============================================================================

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket for real-time updates.
    
    Events:
    - campaign_created
    - message_scheduled
    - cascade_triggered
    - message_sent
    - progress_update
    """
    await connection_manager.connect(websocket)
    
    try:
        await websocket.send_json({"type": "connected"})
        
        # Keep alive
        while True:
            data = await websocket.receive_text()
            await websocket.send_json({"type": "pong"})
    
    except WebSocketDisconnect:
        connection_manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"websocket_error: {str(e)}")
        connection_manager.disconnect(websocket)


# ============================================================================
# Admin Endpoints
# ============================================================================

@app.post("/api/admin/reset")
async def reset_system():
    """Reset entire system."""
    try:
        if not db.pool:
            return {"success": True}
        
        async with db.pool.acquire() as conn:
            await conn.execute("DELETE FROM queue_events")
            await conn.execute("DELETE FROM conversation_memory")
            await conn.execute("DELETE FROM success_patterns")
            await conn.execute("DELETE FROM messages")
            await conn.execute("DELETE FROM conversations")
            await conn.execute("DELETE FROM recipients")
            await conn.execute("DELETE FROM campaigns")
            await conn.execute("DELETE FROM admin_messages")
            
            await conn.execute("""
                UPDATE global_state 
                SET total_messages_sent_today = 0,
                    total_messages_sent_this_hour = 0,
                    last_message_sent_at = NULL
                WHERE id = 1
            """)
        
        # Clear orchestrator state
        if orchestrator_module.orchestrator_agent:
            orchestrator_module.orchestrator_agent.state.spawned_agents.clear()
            orchestrator_module.orchestrator_agent.state.active_campaigns.clear()
            orchestrator_module.orchestrator_agent.state.admin_history.clear()
            orchestrator_module.orchestrator_agent.state.agent_contexts.clear()
            orchestrator_module.orchestrator_agent.state.metrics = {
                "total_campaigns": 0,
                "total_conversations": 0,
                "total_messages_scheduled": 0,
                "total_messages_sent": 0,
                "cascade_count": 0,
                "avg_confidence": 0.0,
                "uptime_seconds": 0,
                "agents_spawned": 0
            }
            orchestrator_module.orchestrator_agent.state.traces.clear()
        
        logger.info("system_reset_complete")
        
        return {"success": True, "message": "System reset complete"}
    
    except Exception as e:
        logger.error(f"reset_failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
