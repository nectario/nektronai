CREATE TABLE IF NOT EXISTS WebsiteOAuthGrant (
    GrantId CHAR(48) CHARACTER SET ascii COLLATE ascii_bin PRIMARY KEY,
    ClientId VARCHAR(128) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    ExpiresAt BIGINT UNSIGNED NOT NULL,
    Revoked BOOLEAN NOT NULL DEFAULT 0,
    INDEX ix_oauth_grant_expiry (ExpiresAt)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS WebsiteOAuthCredential (
    TokenHash CHAR(64) CHARACTER SET ascii COLLATE ascii_bin PRIMARY KEY,
    GrantId CHAR(48) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    Kind ENUM('code','refresh') NOT NULL,
    Data JSON NOT NULL,
    ExpiresAt BIGINT UNSIGNED NOT NULL,
    Used BOOLEAN NOT NULL DEFAULT 0,
    INDEX ix_oauth_credential_grant (GrantId),
    INDEX ix_oauth_credential_expiry (ExpiresAt)
) ENGINE=InnoDB;
