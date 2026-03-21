-- C2: runtime support tables for idempotency and local migration registry.

CREATE TABLE IF NOT EXISTS ingest.idempotency_records (
    operation_key TEXT NOT NULL,
    idempotency_key TEXT NOT NULL,
    request_hash TEXT NOT NULL CHECK (request_hash ~ '^[0-9a-f]{64}$'),
    session_id TEXT,
    response_payload JSONB NOT NULL,
    status_code INTEGER NOT NULL CHECK (status_code >= 100 AND status_code <= 599),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (operation_key, idempotency_key)
);

CREATE INDEX IF NOT EXISTS idx_idempotency_session ON ingest.idempotency_records(session_id);

DROP TRIGGER IF EXISTS trg_idempotency_records_updated_at ON ingest.idempotency_records;
CREATE TRIGGER trg_idempotency_records_updated_at
BEFORE UPDATE ON ingest.idempotency_records
FOR EACH ROW
EXECUTE FUNCTION ingest.set_updated_at();
