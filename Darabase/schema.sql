
-- SecureFileShare — PostgreSQL Schema v2.0


CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ─── USERS
CREATE TABLE IF NOT EXISTS users (
    id               UUID          PRIMARY KEY DEFAULT uuid_generate_v4(),
    wallet_address   VARCHAR(42)   UNIQUE NOT NULL,
    username         VARCHAR(50)   UNIQUE NOT NULL,
    email            VARCHAR(255)  UNIQUE,
    hashed_password  VARCHAR(255)  NOT NULL,
    public_key       TEXT          NOT NULL,
    private_key_enc  TEXT,
    storage_used     BIGINT        DEFAULT 0,
    plan             VARCHAR(20)   DEFAULT 'free',
    is_active        BOOLEAN       DEFAULT TRUE,
    avatar_url       VARCHAR(512),
    created_at       TIMESTAMPTZ   DEFAULT NOW(),
    updated_at       TIMESTAMPTZ   DEFAULT NOW(),
    extra_meta       JSONB         DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_users_wallet ON users(wallet_address);
CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);

-- ─── FILES
CREATE TABLE IF NOT EXISTS files (
    id               UUID          PRIMARY KEY DEFAULT uuid_generate_v4(),
    chain_file_id    INTEGER,
    owner_id         UUID          NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    file_name        VARCHAR(512)  NOT NULL,
    original_name    VARCHAR(512)  NOT NULL,
    mime_type        VARCHAR(100)  NOT NULL,
    file_size        BIGINT        NOT NULL,
    file_hash        VARCHAR(66)   NOT NULL,
    ipfs_cid         VARCHAR(100),
    is_encrypted     BOOLEAN       DEFAULT TRUE,
    encrypted_key    TEXT,
    iv               VARCHAR(32),
    version          INTEGER       DEFAULT 1,
    parent_file_id   UUID          REFERENCES files(id),
    tags             JSONB         DEFAULT '[]',
    description      TEXT,
    is_deleted       BOOLEAN       DEFAULT FALSE,
    is_public        BOOLEAN       DEFAULT FALSE,
    public_token     VARCHAR(64)   UNIQUE,
    tx_hash          VARCHAR(66),
    blockchain_confirmed BOOLEAN   DEFAULT FALSE,
    created_at       TIMESTAMPTZ   DEFAULT NOW(),
    updated_at       TIMESTAMPTZ   DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_files_owner   ON files(owner_id);
CREATE INDEX IF NOT EXISTS idx_files_hash    ON files(file_hash);
CREATE INDEX IF NOT EXISTS idx_files_chain   ON files(chain_file_id);
CREATE INDEX IF NOT EXISTS idx_files_ipfs    ON files(ipfs_cid);
CREATE INDEX IF NOT EXISTS idx_files_tags    ON files USING GIN(tags);

-- Auto-update updated_at
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN NEW.updated_at = NOW(); RETURN NEW; END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_files_updated
    BEFORE UPDATE ON files
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- ─── GRANTS (ACCESS CONTROL)
CREATE TABLE IF NOT EXISTS grants (
    id               UUID          PRIMARY KEY DEFAULT uuid_generate_v4(),
    chain_grant_id   INTEGER,
    file_id          UUID          NOT NULL REFERENCES files(id) ON DELETE CASCADE,
    granter_id       UUID          NOT NULL REFERENCES users(id),
    grantee_id       UUID          NOT NULL REFERENCES users(id),
    encrypted_key    TEXT,
    access_level     VARCHAR(20)   DEFAULT 'VIEW',
    can_reshare      BOOLEAN       DEFAULT FALSE,
    expires_at       TIMESTAMPTZ,
    is_revoked       BOOLEAN       DEFAULT FALSE,
    revoked_at       TIMESTAMPTZ,
    tx_hash          VARCHAR(66),
    created_at       TIMESTAMPTZ   DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_grants_file    ON grants(file_id);
CREATE INDEX IF NOT EXISTS idx_grants_granter ON grants(granter_id);
CREATE INDEX IF NOT EXISTS idx_grants_grantee ON grants(grantee_id);
CREATE INDEX IF NOT EXISTS idx_grants_active  ON grants(grantee_id, is_revoked, expires_at);

-- ─── AUDIT LOGS
CREATE TABLE IF NOT EXISTS audit_logs (
    id               UUID          PRIMARY KEY DEFAULT uuid_generate_v4(),
    file_id          UUID          NOT NULL REFERENCES files(id) ON DELETE CASCADE,
    actor_id         UUID          NOT NULL REFERENCES users(id),
    action           VARCHAR(50)   NOT NULL,
    ip_address       VARCHAR(45),
    user_agent       VARCHAR(512),
    metadata         JSONB         DEFAULT '{}',
    chain_log_id     INTEGER,
    tx_hash          VARCHAR(66),
    created_at       TIMESTAMPTZ   DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_audit_file   ON audit_logs(file_id);
CREATE INDEX IF NOT EXISTS idx_audit_actor  ON audit_logs(actor_id);
CREATE INDEX IF NOT EXISTS idx_audit_action ON audit_logs(action);
CREATE INDEX IF NOT EXISTS idx_audit_time   ON audit_logs(created_at DESC);

-- ─── NOTIFICATIONS
CREATE TABLE IF NOT EXISTS notifications (
    id               UUID          PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id          UUID          NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    type             VARCHAR(50)   NOT NULL,
    title            VARCHAR(255)  NOT NULL,
    message          TEXT          NOT NULL,
    is_read          BOOLEAN       DEFAULT FALSE,
    metadata         JSONB         DEFAULT '{}',
    created_at       TIMESTAMPTZ   DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_notif_user ON notifications(user_id);
CREATE INDEX IF NOT EXISTS idx_notif_read ON notifications(user_id, is_read);

-- ─── BLOCKCHAIN TRANSACTIONS
CREATE TABLE IF NOT EXISTS blockchain_txns (
    id               UUID          PRIMARY KEY DEFAULT uuid_generate_v4(),
    tx_hash          VARCHAR(66)   NOT NULL,
    tx_type          VARCHAR(50)   NOT NULL,
    related_id       VARCHAR(128),
    user_id          UUID          REFERENCES users(id),
    block_number     INTEGER,
    gas_used         INTEGER,
    status           VARCHAR(20)   DEFAULT 'confirmed',
    created_at       TIMESTAMPTZ   DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_btx_user ON blockchain_txns(user_id);
CREATE INDEX IF NOT EXISTS idx_btx_hash ON blockchain_txns(tx_hash);

-- ─── VIEWS ──────────────────────────────────────────────────────────────────

CREATE OR REPLACE VIEW file_version_history AS
SELECT
    f.id, f.file_name, f.version, f.file_hash, f.ipfs_cid,
    f.file_size, f.created_at, f.parent_file_id,
    u.username AS owner_username, u.wallet_address
FROM files f
JOIN users u ON f.owner_id = u.id
WHERE f.is_deleted = FALSE
ORDER BY f.parent_file_id NULLS FIRST, f.version;

CREATE OR REPLACE VIEW active_grants AS
SELECT
    g.*, f.file_name, f.ipfs_cid,
    gu.username AS granter_username,
    ge.username AS grantee_username,
    ge.wallet_address AS grantee_wallet
FROM grants g
JOIN files f  ON g.file_id   = f.id
JOIN users gu ON g.granter_id = gu.id
JOIN users ge ON g.grantee_id = ge.id
WHERE g.is_revoked = FALSE
  AND (g.expires_at IS NULL OR g.expires_at > NOW());

-- ─── FUNCTIONS ──────────────────────────────────────────────────────────────

CREATE OR REPLACE FUNCTION user_stats(p_user_id UUID)
RETURNS TABLE (
    total_files     BIGINT,
    total_size      BIGINT,
    shares_given    BIGINT,
    shares_received BIGINT,
    recent_actions  BIGINT
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        (SELECT COUNT(*) FROM files WHERE owner_id = p_user_id AND is_deleted = FALSE),
        (SELECT COALESCE(SUM(file_size),0) FROM files WHERE owner_id = p_user_id AND is_deleted = FALSE),
        (SELECT COUNT(*) FROM grants WHERE granter_id = p_user_id),
        (SELECT COUNT(*) FROM active_grants WHERE grantee_id = p_user_id),
        (SELECT COUNT(*) FROM audit_logs WHERE actor_id = p_user_id AND created_at > NOW() - INTERVAL '7 days');
END;
$$ LANGUAGE plpgsql STABLE;
