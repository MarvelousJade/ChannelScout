ALTER TABLE outbox DROP CONSTRAINT outbox_update_id_fkey;
ALTER TABLE processed_updates DROP CONSTRAINT processed_updates_pkey;
ALTER TABLE posts DROP CONSTRAINT posts_pkey;
