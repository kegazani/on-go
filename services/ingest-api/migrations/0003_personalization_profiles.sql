CREATE SCHEMA IF NOT EXISTS personalization;

CREATE TABLE IF NOT EXISTS personalization.user_profiles (
    subject_id TEXT PRIMARY KEY,
    physiology_baseline JSONB NOT NULL,
    adaptation_state JSONB NOT NULL DEFAULT '{}'::jsonb,
    notes TEXT,
    created_at_utc TIMESTAMPTZ NOT NULL,
    updated_at_utc TIMESTAMPTZ NOT NULL
);

CREATE INDEX IF NOT EXISTS personalization_user_profiles_updated_idx
    ON personalization.user_profiles (updated_at_utc DESC);
