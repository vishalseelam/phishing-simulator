-- Add simulation time columns to global_state

ALTER TABLE global_state
ADD COLUMN IF NOT EXISTS simulation_time TIMESTAMPTZ,
ADD COLUMN IF NOT EXISTS is_simulation_mode BOOLEAN DEFAULT true;

-- Set initial simulation time to now
UPDATE global_state
SET simulation_time = NOW(),
    is_simulation_mode = true
WHERE id = 1;

