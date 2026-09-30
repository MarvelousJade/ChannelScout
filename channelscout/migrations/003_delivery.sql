ALTER TABLE outbox ADD COLUMN failed_at timestamptz;
ALTER TABLE outbox ADD COLUMN last_error_class text;
CREATE INDEX outbox_pending ON outbox (available_at) WHERE sent_at IS NULL AND failed_at IS NULL;
