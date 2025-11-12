-- Add admin_messages table for orchestrator state

CREATE TABLE IF NOT EXISTS admin_messages (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    role VARCHAR(20) NOT NULL CHECK (role IN ('admin', 'agent')),
    content TEXT NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    metadata JSONB DEFAULT '{}'
);

CREATE INDEX idx_admin_messages_timestamp ON admin_messages(timestamp DESC);
CREATE INDEX idx_admin_messages_role ON admin_messages(role);

COMMENT ON TABLE admin_messages IS 'Admin conversation with orchestrator agent';

