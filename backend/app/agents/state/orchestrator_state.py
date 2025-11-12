"""
Orchestrator Agent State Management

Persistent state that survives restarts.
"""

from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass, field
import logging

from app.models.database import db

logger = logging.getLogger(__name__)


@dataclass
class OrchestratorState:
    """
    Persistent state for orchestrator agent.
    
    Stored in: DB + in-memory cache
    """
    
    # Admin conversation (persistent in DB)
    admin_history: List[Dict] = field(default_factory=list)
    
    # Active campaigns (cached from DB)
    active_campaigns: Dict[str, Dict] = field(default_factory=dict)
    
    # Spawned agents registry (in-memory, restored on startup)
    spawned_agents: Dict[str, 'ConversationAgent'] = field(default_factory=dict)
    
    # Agent contexts (persistent in DB)
    agent_contexts: Dict[str, Dict] = field(default_factory=dict)
    
    # Current async task (if any)
    current_task: Optional[Dict] = None
    
    # Metrics (in-memory, exported periodically)
    metrics: Dict = field(default_factory=lambda: {
        "total_campaigns": 0,
        "total_conversations": 0,
        "total_messages_scheduled": 0,
        "total_messages_sent": 0,
        "cascade_count": 0,
        "avg_confidence": 0.0,
        "uptime_seconds": 0,
        "agents_spawned": 0
    })
    
    # Telemetry traces (limited size)
    traces: List[Dict] = field(default_factory=list)
    
    # Timestamps
    initialized_at: datetime = field(default_factory=datetime.now)
    last_sync_at: datetime = field(default_factory=datetime.now)
    
    async def load_from_db(self):
        """Load state from database on startup."""
        logger.info("loading_orchestrator_state_from_db")
        
        # Load admin conversation history
        if db.pool:
            async with db.pool.acquire() as conn:
                rows = await conn.fetch("""
                    SELECT role, content, timestamp
                    FROM admin_messages
                    ORDER BY timestamp
                    LIMIT 100
                """)
                
                self.admin_history = [
                    {
                        "role": row['role'],
                        "content": row['content'],
                        "timestamp": row['timestamp'].isoformat()
                    }
                    for row in rows
                ]
        
        # Load active campaigns
        if db.pool:
            async with db.pool.acquire() as conn:
                rows = await conn.fetch("""
                    SELECT * FROM campaigns WHERE status = 'active'
                """)
                
                for row in rows:
                    self.active_campaigns[str(row['id'])] = dict(row)
        
        # Load agent contexts (stored in conversations.config)
        if db.pool:
            async with db.pool.acquire() as conn:
                rows = await conn.fetch("""
                    SELECT id, config FROM conversations
                    WHERE state NOT IN ('completed', 'abandoned')
                """)
                
                for row in rows:
                    if row['config']:
                        try:
                            import json
                            config = json.loads(row['config']) if isinstance(row['config'], str) else row['config']
                            if config:
                                self.agent_contexts[str(row['id'])] = config
                        except:
                            pass
        
        logger.info(f"orchestrator_state_loaded: campaigns={len(self.active_campaigns)}, contexts={len(self.agent_contexts)}")
    
    async def save_to_db(self):
        """Sync state to database."""
        # Save admin history (last message only, rest already saved)
        if self.admin_history and db.pool:
            last_msg = self.admin_history[-1]
            # Already saved in process_admin_message
        
        # Save metrics
        if db.pool:
            # Store in a metrics table or log
            pass
        
        self.last_sync_at = datetime.now()
    
    def add_trace(self, event_type: str, data: Dict):
        """Add telemetry trace."""
        self.traces.append({
            "timestamp": datetime.now().isoformat(),
            "event": event_type,
            "data": data
        })
        
        # Keep last 1000 traces
        if len(self.traces) > 1000:
            self.traces = self.traces[-1000:]
    
    def update_metrics(self, metric_name: str, value: any):
        """Update metric."""
        if metric_name in self.metrics:
            if isinstance(self.metrics[metric_name], (int, float)):
                self.metrics[metric_name] += value
            else:
                self.metrics[metric_name] = value

