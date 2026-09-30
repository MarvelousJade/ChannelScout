CREATE TABLE posts (
    chat_id bigint NOT NULL,
    message_id bigint NOT NULL,
    channel_name text NOT NULL,
    username text NOT NULL,
    posted_at timestamptz NOT NULL,
    body text NOT NULL,
    event_at timestamptz NOT NULL,
    event_update_id bigint NOT NULL,
    document tsvector GENERATED ALWAYS AS (to_tsvector('english', body)) STORED,
    PRIMARY KEY (chat_id, message_id)
);
CREATE INDEX posts_document_gin ON posts USING gin(document);
CREATE TABLE processed_updates (
    update_id bigint PRIMARY KEY,
    processed_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE search_sessions (
    id text PRIMARY KEY,
    owner_id bigint NOT NULL,
    query text NOT NULL,
    since_date date,
    expires_at timestamptz NOT NULL DEFAULT now() + interval '1 hour'
);
CREATE TABLE outbox (
    update_id bigint PRIMARY KEY REFERENCES processed_updates(update_id),
    payload jsonb NOT NULL,
    attempts integer NOT NULL DEFAULT 0,
    available_at timestamptz NOT NULL DEFAULT now(),
    sent_at timestamptz
);
