"""
WebSocket endpoint for real-time updates.

Broadcasts:
- queue_updated
- conversation_updated
- message_scheduled
- cascade_triggered
- employee_replied
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import Set
import json
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


class ConnectionManager:
    """Manages WebSocket connections."""
    
    def __init__(self):
        self.active_connections: Set[WebSocket] = set()
        logger.info("websocket_manager_initialized")
    
    async def connect(self, websocket: WebSocket):
        """Accept new connection."""
        await websocket.accept()
        self.active_connections.add(websocket)
        logger.info(f"websocket_connected: total={len(self.active_connections)}")
    
    def disconnect(self, websocket: WebSocket):
        """Remove connection."""
        self.active_connections.discard(websocket)
        logger.info(f"websocket_disconnected: remaining={len(self.active_connections)}")
    
    async def broadcast(self, message: dict):
        """Broadcast to all connected clients."""
        disconnected = set()
        
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except:
                disconnected.add(connection)
        
        # Clean up disconnected
        for conn in disconnected:
            self.active_connections.discard(conn)


# Global connection manager
connection_manager = ConnectionManager()


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time updates."""
    await connection_manager.connect(websocket)
    
    try:
        # Send initial connection message
        await websocket.send_json({
            "type": "connected",
            "message": "Connected to GhostEye v2"
        })
        
        # Keep connection alive
        while True:
            try:
                # Wait for messages with timeout (heartbeat)
                data = await websocket.receive_text()
                # Echo back (for heartbeat)
                await websocket.send_json({
                    "type": "pong",
                    "data": data
                })
            except Exception:
                # Send heartbeat every 30 seconds
                import asyncio
                await asyncio.sleep(30)
                try:
                    await websocket.send_json({"type": "heartbeat"})
                except:
                    break
            
    except WebSocketDisconnect:
        connection_manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"websocket_error: {str(e)}")
        connection_manager.disconnect(websocket)

