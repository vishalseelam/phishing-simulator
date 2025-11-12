-- GhostEye v2 Initial Schema
-- Multi-conversation phishing orchestrator

-- Enable extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- ============================================================
-- ENUMS
-- ============================================================

CREATE TYPE conversation_state AS ENUM (
    'initiated',
    'active',
    'engaged',
    'stalled',
    'completed',
    'abandoned'
);

CREATE TYPE message_priority AS ENUM (
    'urgent',      -- Active conversation (employee replied)
    'high',        -- Admin-injected
    'normal',      -- Scheduled campaign
    'low',         -- Background
    'idle'         -- Can wait indefinitely
);

CREATE TYPE message_status AS ENUM (
    'pending',     -- Not yet scheduled
    'scheduled',   -- In queue
    'sending',     -- Being sent
    'sent',        -- Sent successfully
    'delivered',   -- Delivery confirmed
    'failed',      -- Send failed
    'cancelled'    -- Cancelled before send
);

CREATE TYPE agent_state AS ENUM (
    'active',      -- Human is available (messaging session)
    'idle'         -- Human is away (meeting, lunch, work)
);

CREATE TYPE campaign_status AS ENUM (
    'draft',
    'active',
    'paused',
    'completed',
    'cancelled'
);

-- ============================================================
-- CAMPAIGNS
-- ============================================================

CREATE TABLE campaigns (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    topic TEXT NOT NULL,
    strategy VARCHAR(100) NOT NULL DEFAULT 'auto',
    status campaign_status NOT NULL DEFAULT 'draft',
    
    -- Configuration
    config JSONB NOT NULL DEFAULT '{}',
    
    -- Statistics
    total_recipients INTEGER NOT NULL DEFAULT 0,
    total_messages_planned INTEGER NOT NULL DEFAULT 0,
    total_messages_sent INTEGER NOT NULL DEFAULT 0,
    total_messages_delivered INTEGER NOT NULL DEFAULT 0,
    total_replies_received INTEGER NOT NULL DEFAULT 0,
    success_count INTEGER NOT NULL DEFAULT 0,
    
    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    -- Indexes
    CONSTRAINT valid_status CHECK (
        (status = 'draft' AND started_at IS NULL) OR
        (status IN ('active', 'paused', 'completed', 'cancelled') AND started_at IS NOT NULL)
    )
);

CREATE INDEX idx_campaigns_status ON campaigns(status);
CREATE INDEX idx_campaigns_created_at ON campaigns(created_at DESC);

-- ============================================================
-- RECIPIENTS
-- ============================================================

CREATE TABLE recipients (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    phone_number VARCHAR(20) NOT NULL UNIQUE,
    name VARCHAR(255),
    department VARCHAR(100),
    
    -- Profile for targeting
    profile JSONB NOT NULL DEFAULT '{}',
    
    -- Engagement metrics
    total_messages_received INTEGER NOT NULL DEFAULT 0,
    total_replies_sent INTEGER NOT NULL DEFAULT 0,
    total_links_clicked INTEGER NOT NULL DEFAULT 0,
    avg_response_time_seconds FLOAT,
    
    -- Success tracking
    successful_phishes INTEGER NOT NULL DEFAULT 0,
    
    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_contact_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_recipients_phone ON recipients(phone_number);
CREATE INDEX idx_recipients_department ON recipients(department);

-- ============================================================
-- CONVERSATIONS
-- ============================================================

CREATE TABLE conversations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    campaign_id UUID NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    recipient_id UUID NOT NULL REFERENCES recipients(id) ON DELETE CASCADE,
    
    -- State
    state conversation_state NOT NULL DEFAULT 'initiated',
    priority message_priority NOT NULL DEFAULT 'normal',
    
    -- Current strategy
    current_strategy VARCHAR(100),
    
    -- Conversation flow
    message_count INTEGER NOT NULL DEFAULT 0,
    reply_count INTEGER NOT NULL DEFAULT 0,
    
    -- Engagement
    sentiment VARCHAR(50),  -- suspicious, engaged, neutral, confused
    trust_level VARCHAR(50), -- low, medium, high
    is_making_progress BOOLEAN NOT NULL DEFAULT TRUE,
    
    -- Success tracking
    outcome VARCHAR(100),  -- clicked_link, gave_credentials, reported, none
    
    -- Timing
    last_message_sent_at TIMESTAMPTZ,
    last_reply_received_at TIMESTAMPTZ,
    last_activity_at TIMESTAMPTZ,
    
    -- Timestamps
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    -- Unique constraint
    CONSTRAINT unique_conversation UNIQUE(campaign_id, recipient_id)
);

CREATE INDEX idx_conversations_campaign ON conversations(campaign_id);
CREATE INDEX idx_conversations_recipient ON conversations(recipient_id);
CREATE INDEX idx_conversations_state ON conversations(state);
CREATE INDEX idx_conversations_priority ON conversations(priority);
CREATE INDEX idx_conversations_last_activity ON conversations(last_activity_at DESC);

-- ============================================================
-- MESSAGES
-- ============================================================

CREATE TABLE messages (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    
    -- Content
    content TEXT NOT NULL,
    sender VARCHAR(20) NOT NULL CHECK (sender IN ('agent', 'employee')),
    
    -- Status & Priority
    status message_status NOT NULL DEFAULT 'pending',
    priority message_priority NOT NULL DEFAULT 'normal',
    
    -- Timing (for agent messages)
    ideal_send_time TIMESTAMPTZ,  -- Computed by jitter algorithm
    actual_send_time TIMESTAMPTZ, -- Computed by queue
    sent_at TIMESTAMPTZ,           -- When actually sent
    delivered_at TIMESTAMPTZ,      -- Delivery confirmation
    
    -- Jitter components (for analysis)
    typing_time_seconds FLOAT,
    thinking_time_seconds FLOAT,
    delay_seconds FLOAT,
    confidence_score FLOAT CHECK (confidence_score >= 0 AND confidence_score <= 1),
    jitter_components JSONB,
    
    -- Context
    is_reply BOOLEAN NOT NULL DEFAULT FALSE,
    is_admin_injected BOOLEAN NOT NULL DEFAULT FALSE,
    parent_message_id UUID REFERENCES messages(id),
    strategy_used VARCHAR(100),
    
    -- Twilio
    twilio_sid VARCHAR(100),
    twilio_status VARCHAR(50),
    error_message TEXT,
    error_code VARCHAR(50),
    
    -- Metadata
    metadata JSONB NOT NULL DEFAULT '{}',
    
    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_messages_conversation ON messages(conversation_id);
CREATE INDEX idx_messages_status ON messages(status);
CREATE INDEX idx_messages_priority ON messages(priority, actual_send_time);
CREATE INDEX idx_messages_sender ON messages(sender);
CREATE INDEX idx_messages_twilio_sid ON messages(twilio_sid);
CREATE INDEX idx_messages_actual_send_time ON messages(actual_send_time) WHERE status IN ('scheduled', 'pending');

-- ============================================================
-- GLOBAL STATE
-- ============================================================

CREATE TABLE global_state (
    id INTEGER PRIMARY KEY DEFAULT 1,
    
    -- Agent state (singleton)
    current_state agent_state NOT NULL DEFAULT 'idle',
    state_transition_at TIMESTAMPTZ NOT NULL,
    active_conversation_id UUID REFERENCES conversations(id),
    
    -- Statistics
    total_messages_sent_today INTEGER NOT NULL DEFAULT 0,
    total_messages_sent_this_hour INTEGER NOT NULL DEFAULT 0,
    last_message_sent_at TIMESTAMPTZ,
    last_hour_reset_at TIMESTAMPTZ NOT NULL DEFAULT DATE_TRUNC('hour', NOW()),
    last_day_reset_at TIMESTAMPTZ NOT NULL DEFAULT DATE_TRUNC('day', NOW()),
    
    -- Session tracking
    session_count INTEGER NOT NULL DEFAULT 0,
    active_session_duration_seconds FLOAT,
    idle_session_duration_seconds FLOAT,
    
    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    -- Ensure singleton
    CONSTRAINT singleton_global_state CHECK (id = 1)
);

-- Initialize global state
INSERT INTO global_state (id, current_state, state_transition_at)
VALUES (1, 'idle', NOW() + INTERVAL '30 minutes');

CREATE INDEX idx_global_state_current_state ON global_state(current_state);

-- ============================================================
-- AGENTIC MEMORY (Success Patterns)
-- ============================================================

CREATE TABLE success_patterns (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    recipient_id UUID REFERENCES recipients(id) ON DELETE CASCADE,
    conversation_id UUID REFERENCES conversations(id) ON DELETE CASCADE,
    
    -- Outcome
    outcome VARCHAR(100) NOT NULL,  -- clicked_link, gave_credentials, etc.
    
    -- Pattern data
    strategy_sequence TEXT[] NOT NULL,  -- Sequence of strategies that worked
    timing_pattern JSONB NOT NULL,      -- Timing that worked
    message_sequence TEXT[] NOT NULL,   -- Message templates that worked
    recipient_profile JSONB NOT NULL,   -- Profile of recipient
    
    -- Context
    time_to_success_seconds FLOAT,
    message_count_to_success INTEGER,
    
    -- Learning
    effectiveness_score FLOAT CHECK (effectiveness_score >= 0 AND effectiveness_score <= 1),
    times_applied INTEGER NOT NULL DEFAULT 0,
    success_rate FLOAT,
    
    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_success_patterns_recipient ON success_patterns(recipient_id);
CREATE INDEX idx_success_patterns_outcome ON success_patterns(outcome);
CREATE INDEX idx_success_patterns_effectiveness ON success_patterns(effectiveness_score DESC);

-- ============================================================
-- CONVERSATION MEMORY (Per-Conversation Context)
-- ============================================================

CREATE TABLE conversation_memory (
    conversation_id UUID PRIMARY KEY REFERENCES conversations(id) ON DELETE CASCADE,
    
    -- Learning
    learned_timing_multiplier FLOAT NOT NULL DEFAULT 1.0,
    learned_urgency_factor FLOAT NOT NULL DEFAULT 1.0,
    best_time_of_day_hours INTEGER[],
    effective_strategies TEXT[],
    
    -- Engagement tracking
    responds_to_urgency BOOLEAN,
    responds_to_authority BOOLEAN,
    responds_to_fear BOOLEAN,
    preferred_response_time_seconds FLOAT,
    
    -- Analysis
    personality_profile JSONB NOT NULL DEFAULT '{}',
    
    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================================
-- QUEUE EVENTS (For Debugging)
-- ============================================================

CREATE TABLE queue_events (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    event_type VARCHAR(100) NOT NULL,
    
    -- Event data
    message_id UUID REFERENCES messages(id),
    conversation_id UUID REFERENCES conversations(id),
    
    -- Details
    old_priority message_priority,
    new_priority message_priority,
    old_send_time TIMESTAMPTZ,
    new_send_time TIMESTAMPTZ,
    reason TEXT,
    
    -- Metadata
    metadata JSONB NOT NULL DEFAULT '{}',
    
    -- Timestamp
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_queue_events_message ON queue_events(message_id);
CREATE INDEX idx_queue_events_conversation ON queue_events(conversation_id);
CREATE INDEX idx_queue_events_created_at ON queue_events(created_at DESC);
CREATE INDEX idx_queue_events_type ON queue_events(event_type);

-- ============================================================
-- FUNCTIONS & TRIGGERS
-- ============================================================

-- Update updated_at timestamp automatically
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply to all tables
CREATE TRIGGER update_campaigns_updated_at BEFORE UPDATE ON campaigns
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_recipients_updated_at BEFORE UPDATE ON recipients
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_conversations_updated_at BEFORE UPDATE ON conversations
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_messages_updated_at BEFORE UPDATE ON messages
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_global_state_updated_at BEFORE UPDATE ON global_state
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Reset hourly/daily counters
CREATE OR REPLACE FUNCTION reset_global_state_counters()
RETURNS TRIGGER AS $$
BEGIN
    -- Reset hourly counter
    IF NEW.last_hour_reset_at < DATE_TRUNC('hour', NOW()) THEN
        NEW.total_messages_sent_this_hour = 0;
        NEW.last_hour_reset_at = DATE_TRUNC('hour', NOW());
    END IF;
    
    -- Reset daily counter
    IF NEW.last_day_reset_at < DATE_TRUNC('day', NOW()) THEN
        NEW.total_messages_sent_today = 0;
        NEW.last_day_reset_at = DATE_TRUNC('day', NOW());
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER reset_counters BEFORE UPDATE ON global_state
    FOR EACH ROW EXECUTE FUNCTION reset_global_state_counters();

-- ============================================================
-- VIEWS FOR MONITORING
-- ============================================================

-- Active conversations view
CREATE VIEW v_active_conversations AS
SELECT 
    c.id,
    c.campaign_id,
    camp.name AS campaign_name,
    c.recipient_id,
    r.name AS recipient_name,
    r.phone_number,
    c.state,
    c.priority,
    c.message_count,
    c.reply_count,
    c.sentiment,
    c.trust_level,
    c.last_activity_at,
    EXTRACT(EPOCH FROM (NOW() - c.last_activity_at)) AS seconds_since_activity
FROM conversations c
JOIN campaigns camp ON c.campaign_id = camp.id
JOIN recipients r ON c.recipient_id = r.id
WHERE c.state IN ('active', 'engaged')
ORDER BY c.priority, c.last_activity_at DESC;

-- Queue status view
CREATE VIEW v_queue_status AS
SELECT 
    m.id AS message_id,
    m.conversation_id,
    c.recipient_id,
    r.name AS recipient_name,
    r.phone_number,
    m.priority,
    m.status,
    m.ideal_send_time,
    m.actual_send_time,
    m.confidence_score,
    EXTRACT(EPOCH FROM (m.actual_send_time - NOW())) AS seconds_until_send,
    c.state AS conversation_state
FROM messages m
JOIN conversations c ON m.conversation_id = c.id
JOIN recipients r ON c.recipient_id = r.id
WHERE m.status IN ('scheduled', 'pending')
ORDER BY m.priority, m.actual_send_time;

-- Campaign statistics view
CREATE VIEW v_campaign_stats AS
SELECT 
    c.id,
    c.name,
    c.status,
    c.total_recipients,
    c.total_messages_sent,
    c.total_replies_received,
    c.success_count,
    CASE 
        WHEN c.total_messages_sent > 0 
        THEN ROUND((c.total_replies_received::FLOAT / c.total_messages_sent * 100)::NUMERIC, 2)
        ELSE 0 
    END AS reply_rate_percent,
    CASE 
        WHEN c.total_recipients > 0 
        THEN ROUND((c.success_count::FLOAT / c.total_recipients * 100)::NUMERIC, 2)
        ELSE 0 
    END AS success_rate_percent,
    c.created_at,
    c.started_at,
    c.completed_at
FROM campaigns c
ORDER BY c.created_at DESC;

-- ============================================================
-- COMMENTS
-- ============================================================

COMMENT ON TABLE campaigns IS 'Phishing simulation campaigns';
COMMENT ON TABLE recipients IS 'Target employees for phishing simulations';
COMMENT ON TABLE conversations IS 'Individual conversations between agent and employee';
COMMENT ON TABLE messages IS 'Messages exchanged in conversations';
COMMENT ON TABLE global_state IS 'Global agent state (singleton)';
COMMENT ON TABLE success_patterns IS 'Learned patterns from successful phishing attempts';
COMMENT ON TABLE conversation_memory IS 'Per-conversation learning and context';
COMMENT ON TABLE queue_events IS 'Queue reorganization events for debugging';

