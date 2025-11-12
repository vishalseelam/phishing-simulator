-- Add telemetry table for metrics and evaluation

CREATE TABLE IF NOT EXISTS telemetry_events (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    event_type VARCHAR(100) NOT NULL,
    entity_id VARCHAR(100) NOT NULL,  -- message_id, conversation_id, campaign_id
    metrics JSONB NOT NULL DEFAULT '{}',
    timestamp TIMESTAMP NOT NULL DEFAULT NOW(),
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Indexes for fast queries
CREATE INDEX idx_telemetry_event_type ON telemetry_events(event_type);
CREATE INDEX idx_telemetry_entity_id ON telemetry_events(entity_id);
CREATE INDEX idx_telemetry_timestamp ON telemetry_events(timestamp);
CREATE INDEX idx_telemetry_metrics ON telemetry_events USING GIN(metrics);

-- Comments
COMMENT ON TABLE telemetry_events IS 'Stores all telemetry events for metrics and evaluation';
COMMENT ON COLUMN telemetry_events.event_type IS 'Type: jitter_quality, llm_response_quality, employee_reply, cascade_performance, etc.';
COMMENT ON COLUMN telemetry_events.entity_id IS 'ID of related entity (message, conversation, campaign)';
COMMENT ON COLUMN telemetry_events.metrics IS 'JSON metrics data specific to event type';

