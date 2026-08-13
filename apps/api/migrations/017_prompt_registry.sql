CREATE TABLE IF NOT EXISTS bridge_prompts (
    name TEXT PRIMARY KEY,
    draft_content TEXT,
    draft_version INTEGER NOT NULL DEFAULT 0,
    published_content TEXT,
    published_version INTEGER NOT NULL DEFAULT 0,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
