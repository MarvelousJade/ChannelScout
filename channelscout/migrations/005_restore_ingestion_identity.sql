-- Forward repair for databases that already applied the faulty learning migration.
-- Preserve every removed row, including ambiguous equal-version content, for inspection.
CREATE TABLE ingestion_repair_archive (
    source_table text NOT NULL,
    original_record jsonb NOT NULL,
    archived_at timestamptz NOT NULL DEFAULT now()
);

WITH ranked AS (
    SELECT ctid, row_number() OVER (
        PARTITION BY chat_id, message_id
        ORDER BY event_at DESC, event_update_id DESC, body COLLATE "C" DESC,
                 channel_name COLLATE "C" DESC, username COLLATE "C" DESC, posted_at ASC, ctid
    ) AS position
    FROM posts
), removed AS (
    DELETE FROM posts USING ranked
    WHERE posts.ctid = ranked.ctid AND ranked.position > 1
    RETURNING to_jsonb(posts) AS record
)
INSERT INTO ingestion_repair_archive(source_table, original_record)
SELECT 'posts', record FROM removed;

WITH ranked AS (
    SELECT ctid, row_number() OVER (
        PARTITION BY update_id ORDER BY processed_at ASC, ctid
    ) AS position
    FROM processed_updates
), removed AS (
    DELETE FROM processed_updates USING ranked
    WHERE processed_updates.ctid = ranked.ctid AND ranked.position > 1
    RETURNING to_jsonb(processed_updates) AS record
)
INSERT INTO ingestion_repair_archive(source_table, original_record)
SELECT 'processed_updates', record FROM removed;

ALTER TABLE posts ADD CONSTRAINT posts_pkey PRIMARY KEY (chat_id, message_id);
ALTER TABLE processed_updates ADD CONSTRAINT processed_updates_pkey PRIMARY KEY (update_id);
ALTER TABLE outbox ADD CONSTRAINT outbox_update_id_fkey
    FOREIGN KEY (update_id) REFERENCES processed_updates(update_id);
