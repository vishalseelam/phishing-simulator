# Environment Configuration Template

Copy this to `backend/.env` and fill in your credentials.

```bash
# =============================================================================
# GhostEye v2 - Environment Configuration
# =============================================================================

# -----------------------------------------------------------------------------
# OpenAI Configuration (Required)
# -----------------------------------------------------------------------------
OPENAI_API_KEY=sk-...your-key-here...

# -----------------------------------------------------------------------------
# Algorithm Configuration
# -----------------------------------------------------------------------------
# Enable/disable conversation state system (for easy rollback)
USE_CONVERSATION_STATES=true

# Max messages per day (carrier safety)
MAX_MESSAGES_PER_DAY=100

# Business hours (UTC)
BUSINESS_HOURS_START=9
BUSINESS_HOURS_END=19

# -----------------------------------------------------------------------------
# Server Configuration
# -----------------------------------------------------------------------------
# Backend
HOST=0.0.0.0
PORT=8000
RELOAD=true

# -----------------------------------------------------------------------------
# Feature Flags
# -----------------------------------------------------------------------------
# Enable simulation mode (time travel for testing)
SIMULATION_MODE=true

# Enable telemetry
ENABLE_TELEMETRY=true

# Enable WebSocket updates
ENABLE_WEBSOCKET=true
```

## Quick Setup

```bash
# Backend
cp ENV_TEMPLATE.md backend/.env
# Edit backend/.env with your credentials

# Frontend
echo "NEXT_PUBLIC_API_URL=http://localhost:8000" > frontend/.env.local
```

