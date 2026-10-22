-- Additive Mail-only registry. Apply explicitly; runtime never executes DDL.
-- Existing User, account/Connector grants and EmailDB messages are untouched.
CREATE TABLE MailArchiveKeys (
    ArchiveId CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    OwnerSubject VARBINARY(1020) NOT NULL,
    RequestId CHAR(36) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
    KeyVersion SMALLINT UNSIGNED NOT NULL,
    WrappedKey VARBINARY(6144) NOT NULL,
    CreatedAt BIGINT UNSIGNED NOT NULL,
    PRIMARY KEY (ArchiveId),
    UNIQUE KEY uq_mail_archive_owner_request (OwnerSubject, RequestId)
) ENGINE=InnoDB;
