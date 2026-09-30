ALTER TABLE search_sessions ADD COLUMN results jsonb NOT NULL DEFAULT '[]'::jsonb;
