CREATE TABLE IF NOT EXISTS WebsiteSession (
    TokenHash CHAR(64) CHARACTER SET ascii COLLATE ascii_bin PRIMARY KEY,
    Data JSON NOT NULL,
    ExpiresAt BIGINT UNSIGNED NOT NULL,
    INDEX ix_website_session_expiry (ExpiresAt)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS WebsiteActionToken (
    TokenHash CHAR(64) CHARACTER SET ascii COLLATE ascii_bin PRIMARY KEY,
    UserId VARCHAR(255) NOT NULL,
    Purpose ENUM('verify','reset') NOT NULL,
    CredentialTag CHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    ExpiresAt BIGINT UNSIGNED NOT NULL,
    SentAt BIGINT UNSIGNED NULL,
    INDEX ix_website_action_user (UserId, Purpose),
    INDEX ix_website_action_expiry (ExpiresAt)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS WebsiteRateLimit (
    BucketKey CHAR(64) CHARACTER SET ascii COLLATE ascii_bin PRIMARY KEY,
    Attempts INT UNSIGNED NOT NULL,
    ExpiresAt BIGINT UNSIGNED NOT NULL,
    INDEX ix_website_rate_expiry (ExpiresAt)
) ENGINE=InnoDB;
