"""Immutable archive key registry in the existing account database.

The runtime needs SELECT/INSERT only. Schema application, key retirement and
ownership changes are deliberately not runtime operations.
"""
from dataclasses import dataclass

from pymysql.err import IntegrityError


@dataclass(frozen=True)
class ArchiveKeyRecord:
    archive_id: str
    owner_subject: str
    request_id: str
    key_version: int
    wrapped_key: bytes
    created_at: int


class ArchiveKeyStore:
    def __init__(self, accounts):
        self.accounts = accounts

    @staticmethod
    def _record(row):
        if row is None:
            return None
        owner = row['OwnerSubject']
        return ArchiveKeyRecord(row['ArchiveId'], bytes(owner).decode('utf-8'),
                                row['RequestId'], row['KeyVersion'], bytes(row['WrappedKey']), row['CreatedAt'])

    def by_request(self, owner, request_id):
        with self.accounts.connection() as connection, connection.cursor() as cursor:
            cursor.execute('SELECT ArchiveId,OwnerSubject,RequestId,KeyVersion,WrappedKey,CreatedAt '
                           'FROM MailArchiveKeys WHERE OwnerSubject=%s AND RequestId=%s',
                           (owner.encode('utf-8'), request_id))
            return self._record(cursor.fetchone())

    def by_archive(self, owner, archive_id):
        with self.accounts.connection() as connection, connection.cursor() as cursor:
            cursor.execute('SELECT ArchiveId,OwnerSubject,RequestId,KeyVersion,WrappedKey,CreatedAt '
                           'FROM MailArchiveKeys WHERE OwnerSubject=%s AND ArchiveId=%s',
                           (owner.encode('utf-8'), archive_id))
            return self._record(cursor.fetchone())

    def insert_or_existing(self, candidate):
        # A unique subject/request pair is the concurrency and lost-response
        # boundary. Never replace a previously issued archive or its key.
        try:
            with self.accounts.connection() as connection, connection.cursor() as cursor:
                cursor.execute('INSERT INTO MailArchiveKeys '
                               '(ArchiveId,OwnerSubject,RequestId,KeyVersion,WrappedKey,CreatedAt) '
                               'VALUES (%s,%s,%s,%s,%s,%s)',
                               (candidate.archive_id, candidate.owner_subject.encode('utf-8'),
                                candidate.request_id, candidate.key_version, candidate.wrapped_key, candidate.created_at))
            return candidate
        except IntegrityError:
            existing = self.by_request(candidate.owner_subject, candidate.request_id)
            if existing is None:
                raise RuntimeError('Archive registry could not commit') from None
            return existing
