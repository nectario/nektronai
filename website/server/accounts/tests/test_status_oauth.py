"""Resource/client/scope isolation with synthetic keys, native users and grants."""
import base64
import hashlib
import re
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.parse import parse_qs, urlencode, urlsplit

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app import create_app
from credentials import password_hash
from connector_oauth import CHATGPT_CLIENT, MANAGEMENT_CLIENT, READ, RESOURCE, ISSUER, PREFIX, VERIFIED
from status_oauth_clients import (STATUS_CLIENT, WORKER_CLIENT, STATUS_RESOURCE, WORKER_RESOURCE,
    STATUS_READ, STATUS_SCOPES, WORKER_SCOPE, configured_status_clients)
from test_accounts import MemoryStore, CaptureMailer, SETTINGS, EMAIL, PASSWORD
from test_mail_oauth import MemoryOAuthStore, pem


CALLBACK='https://chatgpt.com/connector/oauth/status-synthetic'
DB_CALLBACK='https://chatgpt.com/connector/oauth/db-synthetic'
WORKER_CALLBACK='http://127.0.0.1:54321/status-endpoint/callback'
VERIFIER='s'*64
CHALLENGE=base64.urlsafe_b64encode(hashlib.sha256(VERIFIER.encode()).digest()).rstrip(b'=').decode()


class StatusOAuthTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.key=rsa.generate_private_key(public_exponent=65537,key_size=2048)
        cls.hashed=password_hash(PASSWORD)
        cls.settings={**SETTINGS,'NEKTRON_CONNECTOR_OAUTH_ENABLED':'true',
            'NEKTRON_CONNECTOR_CHATGPT_CALLBACK':DB_CALLBACK,'NEKTRON_CONNECTOR_SIGNING_PEM':pem(cls.key),
            'NEKTRON_CONNECTOR_SIGNING_KID':'synthetic-native-key','NEKTRON_STATUS_OAUTH_ENABLED':'true',
            'NEKTRON_STATUS_WORKER_OAUTH_ENABLED':'true','NEKTRON_STATUS_CHATGPT_CALLBACK':CALLBACK,
            'NEKTRON_STATUS_WORKER_CALLBACK':WORKER_CALLBACK}

    def setUp(self):
        self.accounts,self.oauth=MemoryStore(),MemoryOAuthStore()
        self.accounts.users[EMAIL]={'UserId':'native:synthetic-status','Email':EMAIL,'PasswordHash':self.hashed,
            'FirstName':'Test','LastName':'Member','MiddleName':'','CountryCode':'US','PhoneNumber':'',
            'Role':'user','AccountStatus':'active','EmailVerified':1}
        self.enterContext(patch('connector_oauth.OAuthStore',return_value=self.oauth))
        self.db_ready=self.enterContext(patch('connector_oauth.has_connector_database',return_value=True))
        self.app=create_app(self.settings,self.accounts,CaptureMailer())
        self.app.testing=True
        self.client=self.app.test_client()
        self.token_client=self.app.test_client(use_cookies=False)
        csrf=self.client.get('/api/account/csrf',base_url=ISSUER).json['csrfToken']
        response=self.client.post('/api/account/login',json={'email':EMAIL,'password':PASSWORD},
            headers={'Origin':ISSUER,'X-CSRF-Token':csrf},base_url=ISSUER)
        self.assertEqual(200,response.status_code)

    def params(self,cid=STATUS_CLIENT,**changes):
        values=dict(client_id=cid,redirect_uri=WORKER_CALLBACK if cid==WORKER_CLIENT else DB_CALLBACK if cid==CHATGPT_CLIENT else CALLBACK,
            response_type='code',scope=WORKER_SCOPE if cid==WORKER_CLIENT else READ if cid==CHATGPT_CLIENT else STATUS_READ,
            resource=WORKER_RESOURCE if cid==WORKER_CLIENT else RESOURCE if cid==CHATGPT_CLIENT else STATUS_RESOURCE,
            state='synthetic-state',code_challenge=CHALLENGE,code_challenge_method='S256')
        values.update(changes)
        return values

    def consent(self,cid=STATUS_CLIENT,**changes):
        values=self.params(cid,**changes)
        path=PREFIX+'/authorize?'+urlencode(values)
        response=self.client.get(path,base_url=ISSUER)
        self.assertEqual(200,response.status_code,response.text[:100])
        csrf=re.search('data-csrf="([^"]+)"',response.text)[1]
        nonce=re.search('data-nonce="([^"]+)"',response.text)[1]
        result=self.client.post(path,json=dict(approve=True,nonce=nonce),
            headers={'Origin':ISSUER,'X-CSRF-Token':csrf},base_url=ISSUER)
        self.assertEqual(200,result.status_code,result.text[:100])
        query=parse_qs(urlsplit(result.json['redirect']).query)
        self.assertEqual([ISSUER],query['iss'])
        self.assertEqual([values['state']],query['state'])
        return values,query['code'][0]

    def exchange(self,values,code,**changes):
        body=dict(grant_type='authorization_code',client_id=values['client_id'],resource=values['resource'],
            redirect_uri=values['redirect_uri'],code=code,code_verifier=VERIFIER)
        body.update(changes)
        return self.token_client.post(PREFIX+'/token',data=body,base_url=ISSUER)

    def claims(self,response,audience):
        self.assertEqual(200,response.status_code,response.text[:100])
        return jwt.decode(response.json['access_token'],self.key.public_key(),algorithms=['RS256'],audience=audience,issuer=ISSUER)

    def test_status_subset_consent_and_token_bind_scope_resource_client_and_native_subject(self):
        scope=STATUS_READ+' task-status:create task-status:dispatch'
        values,code=self.consent(scope=scope)
        response=self.exchange(values,code)
        claims=self.claims(response,STATUS_RESOURCE)
        self.assertEqual((STATUS_CLIENT,scope,'native:synthetic-status'),(claims['client_id'],claims['scope'],claims['sub']))
        self.assertNotIn(VERIFIED,claims)
        self.assertNotIn('auth_tag',claims)
        self.assertIn('refresh_token',response.json)
        self.db_ready.assert_not_called()

    def test_worker_is_exact_scope_and_has_no_refresh_token(self):
        values,code=self.consent(WORKER_CLIENT)
        response=self.exchange(values,code)
        claims=self.claims(response,WORKER_RESOURCE)
        self.assertEqual((WORKER_CLIENT,WORKER_SCOPE),(claims['client_id'],claims['scope']))
        self.assertNotIn('refresh_token',response.json)
        self.assertEqual(300,response.json['expires_in'])
        self.assertEqual(['code'],[r['kind'] for r in self.oauth.credentials.values()])
        self.db_ready.assert_not_called()

    def test_legacy_connector_preserves_database_gate_audience_scope_refresh_and_claim(self):
        values,code=self.consent(CHATGPT_CLIENT)
        response=self.exchange(values,code)
        claims=self.claims(response,RESOURCE)
        self.assertEqual((CHATGPT_CLIENT,READ),(claims['client_id'],claims['scope']))
        self.assertTrue(claims[VERIFIED])
        self.assertIn('refresh_token',response.json)
        self.assertEqual(2,self.db_ready.call_count)
        data=next(iter(self.oauth.credentials.values()))['data']
        self.assertNotIn('resource',data)
        self.assertNotIn('scope',data)

    def test_connector_without_database_still_redirects_setup(self):
        self.db_ready.return_value=False
        response=self.client.get(PREFIX+'/authorize?'+urlencode(self.params(CHATGPT_CLIENT)),base_url=ISSUER)
        self.assertEqual(302,response.status_code)
        self.assertIn('database-connector-setup',response.location)

    def test_cross_resource_scope_client_or_callback_authorization_rejected(self):
        for changes in (dict(resource=RESOURCE),dict(scope=READ),dict(scope=WORKER_SCOPE),
            dict(scope='task-status:create'),dict(scope=STATUS_READ+' '+STATUS_READ),
            dict(redirect_uri=DB_CALLBACK),dict(client_id=MANAGEMENT_CLIENT)):
            with self.subTest(changes=changes):
                response=self.client.get(PREFIX+'/authorize?'+urlencode(self.params(**changes)),base_url=ISSUER)
                self.assertEqual(400,response.status_code)
        self.db_ready.assert_not_called()

    def test_worker_cannot_request_status_or_connector_scopes(self):
        for scope in (STATUS_READ,READ,WORKER_SCOPE+' '+STATUS_READ):
            response=self.client.get(PREFIX+'/authorize?'+urlencode(self.params(WORKER_CLIENT,scope=scope)),base_url=ISSUER)
            self.assertEqual(400,response.status_code)

    def test_status_code_cannot_exchange_for_another_client_or_resource(self):
        for changes in (dict(client_id=CHATGPT_CLIENT,resource=RESOURCE),dict(resource=WORKER_RESOURCE),
                        dict(redirect_uri=DB_CALLBACK),dict(scope=STATUS_READ+' task-status:dispatch')):
            with self.subTest(changes=changes):
                values,code=self.consent()
                self.assertEqual(400,self.exchange(values,code,**changes).status_code)

    def test_scope_is_frozen_through_refresh_and_refresh_replay_revokes_family(self):
        values,code=self.consent(scope=STATUS_READ+' task-status:create')
        token=self.exchange(values,code).json
        data=dict(grant_type='refresh_token',client_id=STATUS_CLIENT,resource=STATUS_RESOURCE,refresh_token=token['refresh_token'])
        response=self.token_client.post(PREFIX+'/token',data=data,base_url=ISSUER)
        self.assertEqual(STATUS_READ+' task-status:create',self.claims(response,STATUS_RESOURCE)['scope'])
        self.assertEqual(400,self.token_client.post(PREFIX+'/token',data=data,base_url=ISSUER).status_code)
        data['refresh_token']=response.json['refresh_token']
        self.assertEqual(400,self.token_client.post(PREFIX+'/token',data=data,base_url=ISSUER).status_code)

    def test_refresh_cannot_add_or_drop_frozen_scopes(self):
        for scope in (STATUS_READ,STATUS_READ+' task-status:dispatch'):
            values,code=self.consent(scope=STATUS_READ+' task-status:create')
            token=self.exchange(values,code).json
            response=self.token_client.post(PREFIX+'/token',data=dict(grant_type='refresh_token',client_id=STATUS_CLIENT,
                resource=STATUS_RESOURCE,refresh_token=token['refresh_token'],scope=scope),base_url=ISSUER)
            self.assertEqual(400,response.status_code)

    def test_worker_refresh_grant_is_refused(self):
        response=self.token_client.post(PREFIX+'/token',data=dict(grant_type='refresh_token',client_id=WORKER_CLIENT,
            resource=WORKER_RESOURCE,refresh_token='synthetic-not-a-token'),base_url=ISSUER)
        self.assertEqual(400,response.status_code)

    def test_native_account_revocation_after_consent_prevents_token(self):
        values,code=self.consent()
        self.accounts.users[EMAIL]['AccountStatus']='disabled'
        self.assertEqual(400,self.exchange(values,code).status_code)

    def test_malformed_empty_stored_scope_is_not_accepted_as_allowed_scope(self):
        values,code=self.consent()
        for record in self.oauth.credentials.values():
            if record['kind']=='code':
                record['data']['scope']=''
        self.assertEqual(400,self.exchange(values,code).status_code)

    def test_status_disabled_defaults_leave_connector_metadata_unchanged(self):
        settings={k:v for k,v in self.settings.items() if not k.startswith('NEKTRON_STATUS_')}
        app=create_app(settings,self.accounts,CaptureMailer())
        client=app.test_client()
        metadata=client.get('/.well-known/oauth-authorization-server',base_url=ISSUER).json
        self.assertEqual([READ],metadata['scopes_supported'])
        response=client.get(PREFIX+'/authorize?'+urlencode(self.params()),base_url=ISSUER)
        self.assertEqual(400,response.status_code)

    def test_status_only_registration_does_not_enable_connector_management(self):
        settings=dict(self.settings,NEKTRON_CONNECTOR_OAUTH_ENABLED='false')
        app=create_app(settings,self.accounts,CaptureMailer())
        metadata=app.test_client().get('/.well-known/oauth-authorization-server',base_url=ISSUER).json
        self.assertNotIn(READ,metadata['scopes_supported'])
        self.assertEqual(set(STATUS_SCOPES)|{WORKER_SCOPE},set(metadata['scopes_supported']))

    def test_callbacks_must_be_exact_and_worker_must_use_literal_loopback_path(self):
        for value in ('http://localhost:54321/status-endpoint/callback','http://127.0.0.1:54321/other',
                      'http://127.0.0.1:54321/status-endpoint/callback?x=1','https://attacker.invalid/callback'):
            with self.subTest(value=value),self.assertRaises(ValueError):
                configured_status_clients(dict(self.settings,NEKTRON_STATUS_WORKER_CALLBACK=value))

    def test_consent_nonce_cannot_be_reused_for_added_scope(self):
        params=self.params()
        response=self.client.get(PREFIX+'/authorize?'+urlencode(params),base_url=ISSUER)
        self.assertIn('Connect Status Endpoint for ChatGPT',response.text)
        csrf=re.search('data-csrf="([^"]+)"',response.text)[1]
        nonce=re.search('data-nonce="([^"]+)"',response.text)[1]
        params['scope']=STATUS_READ+' task-status:dispatch'
        result=self.client.post(PREFIX+'/authorize?'+urlencode(params),json=dict(approve=True,nonce=nonce),
            headers={'Origin':ISSUER,'X-CSRF-Token':csrf},base_url=ISSUER)
        self.assertEqual(400,result.status_code)
        self.assertEqual({},self.oauth.credentials)

    def test_worker_only_metadata_and_registration_never_enable_refresh_or_connector(self):
        settings=dict(self.settings,NEKTRON_CONNECTOR_OAUTH_ENABLED='false',NEKTRON_STATUS_OAUTH_ENABLED='false')
        app=create_app(settings,self.accounts,CaptureMailer())
        metadata=app.test_client().get('/.well-known/oauth-authorization-server',base_url=ISSUER).json
        self.assertEqual([WORKER_SCOPE],metadata['scopes_supported'])
        self.assertEqual(['authorization_code'],metadata['grant_types_supported'])

    def test_status_pending_login_resumes_without_tab_local_state(self):
        for cid in (STATUS_CLIENT,WORKER_CLIENT):
            with self.subTest(client=cid):
                browser=self.app.test_client()
                response=browser.get(PREFIX+'/authorize?'+urlencode(self.params(cid)),base_url=ISSUER)
                self.assertEqual(302,response.status_code)
                csrf=browser.get('/api/account/csrf',base_url=ISSUER).json['csrfToken']
                result=browser.post('/api/account/login',json={'email':EMAIL,'password':PASSWORD},
                    headers={'Origin':ISSUER,'X-CSRF-Token':csrf},base_url=ISSUER)
                self.assertEqual(200,result.status_code)
                self.assertEqual(PREFIX+'/resume',result.json['redirect'])
                resumed=browser.get(PREFIX+'/resume',base_url=ISSUER)
                self.assertEqual(302,resumed.status_code)
                self.assertIn(cid,resumed.location)

    def test_reporting_is_separately_consented_without_database_setup(self):
        scope=STATUS_READ+' task-status:report'
        values,code=self.consent(scope=scope)
        token=self.exchange(values,code)
        claims=self.claims(token,STATUS_RESOURCE)
        self.assertEqual(scope,claims['scope'])
        self.assertEqual('native:synthetic-status',claims['sub'])
        self.assertNotIn(VERIFIED,claims)
        self.db_ready.assert_not_called()

    def test_existing_refresh_family_cannot_acquire_reporting_permission(self):
        values,code=self.consent()
        token=self.exchange(values,code).json
        response=self.token_client.post(PREFIX+'/token',data=dict(grant_type='refresh_token',
            client_id=STATUS_CLIENT,resource=STATUS_RESOURCE,refresh_token=token['refresh_token'],
            scope=STATUS_READ+' task-status:report'),base_url=ISSUER)
        self.assertEqual(400,response.status_code)

    def test_worker_and_readless_authorization_cannot_request_reporting_scope(self):
        for cid,scope in ((WORKER_CLIENT,WORKER_SCOPE+' task-status:report'),(STATUS_CLIENT,'task-status:report')):
            response=self.client.get(PREFIX+'/authorize?'+urlencode(self.params(cid,scope=scope)),base_url=ISSUER)
            self.assertEqual(400,response.status_code)
