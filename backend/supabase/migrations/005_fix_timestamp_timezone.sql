-- Fix timestamp columns to use TIMESTAMP instead of TIMESTAMPTZ
-- This prevents PostgreSQL from doing automatic timezone conversions
-- We manage all times as naive UTC in the application layer

-- Drop ALL views first
DROP VIEW IF EXISTS v_queue_status CASCADE;
DROP VIEW IF EXISTS v_conversation_summary CASCADE;
DROP VIEW IF EXISTS v_active_conversations CASCADE;
DROP VIEW IF EXISTS v_campaign_stats CASCADE;

-- Messages table (CRITICAL - this is where scheduling happens)
ALTER TABLE messages
ALTER COLUMN ideal_send_time TYPE TIMESTAMP,
ALTER COLUMN actual_send_time TYPE TIMESTAMP,
ALTER COLUMN sent_at TYPE TIMESTAMP,
ALTER COLUMN delivered_at TYPE TIMESTAMP;

-- Global state table - add simulation_time if it exists
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='global_state' AND column_name='simulation_time') THEN
        ALTER TABLE global_state ALTER COLUMN simulation_time TYPE TIMESTAMP;
    END IF;
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='global_state' AND column_name='state_transition_at') THEN
        ALTER TABLE global_state ALTER COLUMN state_transition_at TYPE TIMESTAMP;
    END IF;
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='global_state' AND column_name='last_message_sent_at') THEN
        ALTER TABLE global_state ALTER COLUMN last_message_sent_at TYPE TIMESTAMP;
    END IF;
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='global_state' AND column_name='last_hour_reset_at') THEN
        ALTER TABLE global_state ALTER COLUMN last_hour_reset_at TYPE TIMESTAMP;
    END IF;
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='global_state' AND column_name='last_day_reset_at') THEN
        ALTER TABLE global_state ALTER COLUMN last_day_reset_at TYPE TIMESTAMP;
    END IF;
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='global_state' AND column_name='created_at') THEN
        ALTER TABLE global_state ALTER COLUMN created_at TYPE TIMESTAMP;
    END IF;
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='global_state' AND column_name='updated_at') THEN
        ALTER TABLE global_state ALTER COLUMN updated_at TYPE TIMESTAMP;
    END IF;
END $$;
