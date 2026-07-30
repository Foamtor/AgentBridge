ALTER TABLE approval_records
    ADD COLUMN IF NOT EXISTS execution_token TEXT;
ALTER TABLE approval_records
    ADD COLUMN IF NOT EXISTS last_sequence INTEGER NOT NULL DEFAULT 0;
ALTER TABLE approval_records
    ADD COLUMN IF NOT EXISTS approval_expires_at TIMESTAMPTZ;
ALTER TABLE approval_records
    ADD COLUMN IF NOT EXISTS query TEXT;

UPDATE approval_records
SET last_sequence = GREATEST(last_sequence, COALESCE(sequence, 0));

CREATE INDEX IF NOT EXISTS approval_records_pending_expiry_idx
    ON approval_records (approval_expires_at)
    WHERE status = 'pending';
