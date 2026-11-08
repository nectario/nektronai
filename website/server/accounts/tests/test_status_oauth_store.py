"""SQL intent tests for bounded one-shot family lifetime; no database access."""
from types import SimpleNamespace
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from connector_oauth_store import OAuthStore


class Cursor:
    def __init__(self):
        self.calls=[]

    def __enter__(self):
        return self

    def __exit__(self,*args):
        pass

    def execute(self,sql,args):
        self.calls.append((sql,args))


class Connection:
    def __init__(self,cursor):
        self.value=cursor

    def __enter__(self):
        return self

    def __exit__(self,*args):
        pass

    def cursor(self):
        return self.value


class StatusOAuthStoreTests(unittest.TestCase):
    def test_access_only_worker_code_has_short_family_and_hashed_code(self):
        for data,ttl in (({'client_id':'nektron-status-endpoint-worker','refresh_allowed':False},300),
            ({'client_id':'nektron-status-endpoint-chatgpt','refresh_allowed':True},30*86400),
            ({'client_id':'nektron-database-connector-chatgpt'},30*86400),
            ({'client_id':'nektron-mail-windows'},30*86400)):
            with self.subTest(client=data['client_id']):
                cursor=Cursor()
                store=OAuthStore(SimpleNamespace(connection=lambda:Connection(cursor)))
                with patch.object(store,'_maybe_purge_expired'),patch('connector_oauth_store.time.time',return_value=1000):
                    store.create_code('synthetic-code-only',data)
                self.assertEqual(1000+ttl,cursor.calls[0][1][2])
                self.assertEqual(1120,cursor.calls[1][1][-1])
                self.assertEqual(64,len(cursor.calls[1][1][0]))
                self.assertNotIn('synthetic-code-only',str(cursor.calls))
