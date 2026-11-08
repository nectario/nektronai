CREATE TABLE IF NOT EXISTS Application (
    ApplicationId VARCHAR(64) CHARACTER SET ascii COLLATE ascii_bin PRIMARY KEY,
    DisplayName VARCHAR(128) NOT NULL,
    Enabled BOOLEAN NOT NULL DEFAULT 1
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;

CREATE TABLE IF NOT EXISTS UserApplication (
    UserId VARCHAR(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_bin NOT NULL,
    ApplicationId VARCHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    AccessStatus ENUM('pending','active','suspended','revoked') NOT NULL DEFAULT 'pending',
    AppRole VARCHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL DEFAULT 'member',
    PlanCode VARCHAR(64) CHARACTER SET ascii COLLATE ascii_bin NULL,
    Settings JSON NOT NULL,
    ExpiresAt BIGINT UNSIGNED NULL,
    Version BIGINT UNSIGNED NOT NULL DEFAULT 1,
    CreatedAt BIGINT UNSIGNED NOT NULL,
    UpdatedAt BIGINT UNSIGNED NOT NULL,
    PRIMARY KEY (UserId, ApplicationId),
    INDEX ix_user_application_product (ApplicationId, AccessStatus),
    CONSTRAINT fk_user_application_product FOREIGN KEY (ApplicationId)
        REFERENCES Application (ApplicationId) ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;

CREATE TABLE IF NOT EXISTS ApplicationOAuthClient (
    ClientId VARCHAR(128) CHARACTER SET ascii COLLATE ascii_bin PRIMARY KEY,
    ApplicationId VARCHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    INDEX ix_application_oauth_product (ApplicationId),
    CONSTRAINT fk_application_oauth_product FOREIGN KEY (ApplicationId)
        REFERENCES Application (ApplicationId) ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;
