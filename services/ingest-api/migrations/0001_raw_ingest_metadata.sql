-- C1: базовая схема метаданных raw ingest в Postgres.
-- Шаг C2 должен добавить runtime-интеграцию с MinIO/S3 и выполнение upload lifecycle.

CREATE SCHEMA IF NOT EXISTS ingest;
CREATE EXTENSION IF NOT EXISTS pgcrypto;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_type t
        JOIN pg_namespace n ON n.oid = t.typnamespace
        WHERE t.typname = 'raw_session_status' AND n.nspname = 'ingest'
    ) THEN
        CREATE TYPE ingest.raw_session_status AS ENUM ('completed', 'partial', 'failed', 'exported');
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM pg_type t
        JOIN pg_namespace n ON n.oid = t.typnamespace
        WHERE t.typname = 'ingest_status' AND n.nspname = 'ingest'
    ) THEN
        CREATE TYPE ingest.ingest_status AS ENUM ('accepted', 'uploading', 'uploaded', 'validating', 'ingested', 'failed', 'cancelled');
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM pg_type t
        JOIN pg_namespace n ON n.oid = t.typnamespace
        WHERE t.typname = 'device_role' AND n.nspname = 'ingest'
    ) THEN
        CREATE TYPE ingest.device_role AS ENUM ('coordinator_phone', 'polar_h10', 'apple_watch');
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM pg_type t
        JOIN pg_namespace n ON n.oid = t.typnamespace
        WHERE t.typname = 'stream_name' AND n.nspname = 'ingest'
    ) THEN
        CREATE TYPE ingest.stream_name AS ENUM (
            'polar_ecg',
            'polar_rr',
            'polar_hr',
            'polar_acc',
            'watch_heart_rate',
            'watch_accelerometer',
            'watch_gyroscope',
            'watch_activity_context',
            'watch_hrv'
        );
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM pg_type t
        JOIN pg_namespace n ON n.oid = t.typnamespace
        WHERE t.typname = 'artifact_role' AND n.nspname = 'ingest'
    ) THEN
        CREATE TYPE ingest.artifact_role AS ENUM (
            'manifest_session',
            'manifest_subject',
            'manifest_devices',
            'manifest_streams',
            'manifest_segments',
            'stream_metadata',
            'stream_samples',
            'session_events',
            'self_report',
            'quality_report',
            'checksums',
            'other'
        );
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM pg_type t
        JOIN pg_namespace n ON n.oid = t.typnamespace
        WHERE t.typname = 'artifact_upload_status' AND n.nspname = 'ingest'
    ) THEN
        CREATE TYPE ingest.artifact_upload_status AS ENUM ('pending', 'uploaded', 'verified', 'failed');
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM pg_type t
        JOIN pg_namespace n ON n.oid = t.typnamespace
        WHERE t.typname = 'quality_status' AND n.nspname = 'ingest'
    ) THEN
        CREATE TYPE ingest.quality_status AS ENUM ('pass', 'warning', 'fail');
    END IF;
END $$;

CREATE OR REPLACE FUNCTION ingest.set_updated_at()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$;

CREATE TABLE IF NOT EXISTS ingest.subjects (
    subject_id TEXT PRIMARY KEY,
    cohort TEXT,
    study_group TEXT,
    sex TEXT,
    age_range TEXT,
    consent_version TEXT NOT NULL,
    baseline_notes TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS ingest.raw_sessions (
    session_id TEXT PRIMARY KEY,
    subject_id TEXT NOT NULL REFERENCES ingest.subjects(subject_id),
    schema_version TEXT NOT NULL,
    protocol_version TEXT NOT NULL,
    session_type TEXT NOT NULL,
    session_status ingest.raw_session_status NOT NULL,
    started_at_utc TIMESTAMPTZ NOT NULL,
    ended_at_utc TIMESTAMPTZ NOT NULL,
    timezone TEXT NOT NULL,
    coordinator_device_id TEXT,
    capture_app_version TEXT NOT NULL,
    operator_mode TEXT,
    session_environment JSONB NOT NULL DEFAULT '{}'::jsonb,
    notes TEXT,
    planned_segment_count INTEGER CHECK (planned_segment_count IS NULL OR planned_segment_count >= 0),
    observed_segment_count INTEGER CHECK (observed_segment_count IS NULL OR observed_segment_count >= 0),
    stream_count INTEGER CHECK (stream_count IS NULL OR stream_count >= 0),
    export_completed_at_utc TIMESTAMPTZ,
    ingest_status ingest.ingest_status NOT NULL DEFAULT 'accepted',
    ingest_requested_at_utc TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ingest_finalized_at_utc TIMESTAMPTZ,
    ingested_at_utc TIMESTAMPTZ,
    storage_root_prefix TEXT NOT NULL,
    checksum_file_path TEXT,
    package_checksum_sha256 TEXT CHECK (package_checksum_sha256 IS NULL OR package_checksum_sha256 ~ '^[0-9a-f]{64}$'),
    last_error_code TEXT,
    last_error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT raw_sessions_time_order CHECK (ended_at_utc >= started_at_utc)
);

CREATE TABLE IF NOT EXISTS ingest.session_devices (
    session_id TEXT NOT NULL REFERENCES ingest.raw_sessions(session_id) ON DELETE CASCADE,
    device_id TEXT NOT NULL,
    device_role ingest.device_role NOT NULL,
    manufacturer TEXT NOT NULL,
    model TEXT NOT NULL,
    firmware_version TEXT,
    source_name TEXT NOT NULL,
    connection_started_at_utc TIMESTAMPTZ,
    connection_ended_at_utc TIMESTAMPTZ,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (session_id, device_id),
    CONSTRAINT session_devices_time_order CHECK (
        connection_ended_at_utc IS NULL
        OR connection_started_at_utc IS NULL
        OR connection_ended_at_utc >= connection_started_at_utc
    )
);

CREATE TABLE IF NOT EXISTS ingest.session_segments (
    session_id TEXT NOT NULL REFERENCES ingest.raw_sessions(session_id) ON DELETE CASCADE,
    segment_id TEXT NOT NULL,
    name TEXT NOT NULL,
    order_index INTEGER NOT NULL CHECK (order_index >= 0),
    started_at_utc TIMESTAMPTZ NOT NULL,
    ended_at_utc TIMESTAMPTZ NOT NULL,
    planned BOOLEAN NOT NULL,
    notes TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (session_id, segment_id),
    UNIQUE (session_id, order_index),
    CONSTRAINT session_segments_time_order CHECK (ended_at_utc >= started_at_utc)
);

CREATE TABLE IF NOT EXISTS ingest.session_streams (
    session_id TEXT NOT NULL REFERENCES ingest.raw_sessions(session_id) ON DELETE CASCADE,
    stream_id TEXT NOT NULL,
    device_id TEXT NOT NULL,
    stream_name ingest.stream_name NOT NULL,
    stream_kind TEXT NOT NULL,
    unit_schema JSONB NOT NULL DEFAULT '{}'::jsonb,
    sample_count BIGINT NOT NULL CHECK (sample_count >= 0),
    started_at_utc TIMESTAMPTZ,
    ended_at_utc TIMESTAMPTZ,
    file_ref TEXT NOT NULL,
    checksum_sha256 TEXT NOT NULL CHECK (checksum_sha256 ~ '^[0-9a-f]{64}$'),
    byte_size BIGINT CHECK (byte_size IS NULL OR byte_size >= 0),
    compression TEXT,
    content_type TEXT,
    missing_intervals JSONB NOT NULL DEFAULT '[]'::jsonb,
    availability_status TEXT NOT NULL DEFAULT 'captured' CHECK (availability_status IN ('captured', 'missing', 'corrupted')),
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (session_id, stream_id),
    UNIQUE (session_id, stream_name),
    FOREIGN KEY (session_id, device_id) REFERENCES ingest.session_devices(session_id, device_id),
    CONSTRAINT session_streams_time_order CHECK (
        ended_at_utc IS NULL
        OR started_at_utc IS NULL
        OR ended_at_utc >= started_at_utc
    )
);

CREATE TABLE IF NOT EXISTS ingest.session_events (
    session_id TEXT NOT NULL REFERENCES ingest.raw_sessions(session_id) ON DELETE CASCADE,
    event_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    occurred_at_utc TIMESTAMPTZ NOT NULL,
    source TEXT NOT NULL,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (session_id, event_id)
);

CREATE TABLE IF NOT EXISTS ingest.session_self_reports (
    session_id TEXT NOT NULL REFERENCES ingest.raw_sessions(session_id) ON DELETE CASCADE,
    report_id TEXT NOT NULL,
    reported_at_utc TIMESTAMPTZ NOT NULL,
    report_version TEXT NOT NULL,
    answers JSONB NOT NULL DEFAULT '{}'::jsonb,
    free_text TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (session_id, report_id)
);

CREATE TABLE IF NOT EXISTS ingest.session_quality_reports (
    session_id TEXT NOT NULL REFERENCES ingest.raw_sessions(session_id) ON DELETE CASCADE,
    quality_report_id TEXT NOT NULL,
    generated_at_utc TIMESTAMPTZ NOT NULL,
    overall_status ingest.quality_status NOT NULL,
    checks JSONB NOT NULL DEFAULT '[]'::jsonb,
    notes TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (session_id, quality_report_id)
);

CREATE TABLE IF NOT EXISTS ingest.ingest_artifacts (
    artifact_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id TEXT NOT NULL REFERENCES ingest.raw_sessions(session_id) ON DELETE CASCADE,
    artifact_path TEXT NOT NULL,
    artifact_role ingest.artifact_role NOT NULL,
    stream_name ingest.stream_name,
    content_type TEXT NOT NULL,
    byte_size BIGINT NOT NULL CHECK (byte_size >= 0),
    checksum_sha256 TEXT NOT NULL CHECK (checksum_sha256 ~ '^[0-9a-f]{64}$'),
    object_key TEXT NOT NULL,
    upload_status ingest.artifact_upload_status NOT NULL DEFAULT 'pending',
    upload_attempt_count INTEGER NOT NULL DEFAULT 0 CHECK (upload_attempt_count >= 0),
    storage_etag TEXT,
    uploaded_at_utc TIMESTAMPTZ,
    verified_at_utc TIMESTAMPTZ,
    error_code TEXT,
    error_message TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (session_id, artifact_path)
);

CREATE TABLE IF NOT EXISTS ingest.ingest_audit_log (
    audit_id BIGSERIAL PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES ingest.raw_sessions(session_id) ON DELETE CASCADE,
    action_type TEXT NOT NULL,
    actor_type TEXT NOT NULL CHECK (actor_type IN ('system', 'device', 'operator', 'service')),
    actor_id TEXT,
    idempotency_key TEXT,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    action_at_utc TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_raw_sessions_subject ON ingest.raw_sessions(subject_id);
CREATE INDEX IF NOT EXISTS idx_raw_sessions_ingest_status ON ingest.raw_sessions(ingest_status);
CREATE INDEX IF NOT EXISTS idx_raw_sessions_started_at ON ingest.raw_sessions(started_at_utc DESC);

CREATE INDEX IF NOT EXISTS idx_streams_session_name ON ingest.session_streams(session_id, stream_name);
CREATE INDEX IF NOT EXISTS idx_streams_device ON ingest.session_streams(session_id, device_id);
CREATE INDEX IF NOT EXISTS idx_events_session_time ON ingest.session_events(session_id, occurred_at_utc);
CREATE INDEX IF NOT EXISTS idx_artifacts_session_status ON ingest.ingest_artifacts(session_id, upload_status);
CREATE INDEX IF NOT EXISTS idx_audit_session_time ON ingest.ingest_audit_log(session_id, action_at_utc DESC);

DROP TRIGGER IF EXISTS trg_subjects_updated_at ON ingest.subjects;
CREATE TRIGGER trg_subjects_updated_at
BEFORE UPDATE ON ingest.subjects
FOR EACH ROW
EXECUTE FUNCTION ingest.set_updated_at();

DROP TRIGGER IF EXISTS trg_raw_sessions_updated_at ON ingest.raw_sessions;
CREATE TRIGGER trg_raw_sessions_updated_at
BEFORE UPDATE ON ingest.raw_sessions
FOR EACH ROW
EXECUTE FUNCTION ingest.set_updated_at();

DROP TRIGGER IF EXISTS trg_session_devices_updated_at ON ingest.session_devices;
CREATE TRIGGER trg_session_devices_updated_at
BEFORE UPDATE ON ingest.session_devices
FOR EACH ROW
EXECUTE FUNCTION ingest.set_updated_at();

DROP TRIGGER IF EXISTS trg_session_segments_updated_at ON ingest.session_segments;
CREATE TRIGGER trg_session_segments_updated_at
BEFORE UPDATE ON ingest.session_segments
FOR EACH ROW
EXECUTE FUNCTION ingest.set_updated_at();

DROP TRIGGER IF EXISTS trg_session_streams_updated_at ON ingest.session_streams;
CREATE TRIGGER trg_session_streams_updated_at
BEFORE UPDATE ON ingest.session_streams
FOR EACH ROW
EXECUTE FUNCTION ingest.set_updated_at();

DROP TRIGGER IF EXISTS trg_ingest_artifacts_updated_at ON ingest.ingest_artifacts;
CREATE TRIGGER trg_ingest_artifacts_updated_at
BEFORE UPDATE ON ingest.ingest_artifacts
FOR EACH ROW
EXECUTE FUNCTION ingest.set_updated_at();
