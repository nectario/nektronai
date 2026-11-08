"""Disabled opt-in Status clients for the existing native OAuth issuer.

Registration data only: no actor enrollment, application grant or credential.
"""
import re

from authlib.oauth2.rfc6749 import ClientMixin


STATUS_CLIENT = 'nektron-status-endpoint-chatgpt'
WORKER_CLIENT = 'nektron-status-endpoint-worker'
STATUS_RESOURCE = 'https://status.nektron.ai/mcp'
WORKER_RESOURCE = 'https://status-worker.nektron.ai/api/task-worker/v1'
STATUS_READ = 'task-status:read'
STATUS_SCOPES = frozenset((STATUS_READ, 'task-status:read-internal', 'task-status:create', 'task-status:dispatch', 'task-status:report'))
WORKER_SCOPE = 'task-status:worker'
STATUS_FLOW = 'status-resource-code-v1'


def chatgpt_callback(value):
    return isinstance(value,str) and bool(re.fullmatch(
        r'https://chatgpt\.com/(connector/oauth/[A-Za-z0-9_-]+|connector_platform_oauth_redirect)',value))


def worker_callback(value):
    if not isinstance(value,str):
        return False
    match=re.fullmatch(r'http://127\.0\.0\.1:([1-9][0-9]{3,4})/status-endpoint/callback',value)
    return bool(match and 1024<=int(match[1])<=65535)


class StatusClient(ClientMixin):
    def __init__(self,client_id,callback):
        if client_id not in (STATUS_CLIENT,WORKER_CLIENT):
            raise ValueError('Unknown Status client')
        worker=client_id==WORKER_CLIENT
        if not (worker_callback(callback) if worker else chatgpt_callback(callback)):
            raise ValueError('Exact Status callback required')
        self.client_id,self.callbacks=client_id,(callback,)
        self.resource=WORKER_RESOURCE if worker else STATUS_RESOURCE
        self.scopes=frozenset((WORKER_SCOPE,)) if worker else STATUS_SCOPES
        self.required_scope=WORKER_SCOPE if worker else STATUS_READ
        self.display_name='Status Endpoint worker' if worker else 'Status Endpoint for ChatGPT'
        self.refresh_allowed=not worker

    def get_client_id(self):
        return self.client_id

    def get_default_redirect_uri(self):
        return None

    def get_allowed_scope(self,scope):
        if not isinstance(scope,str):
            return ''
        values=scope.split(' ')
        return scope if (values and len(set(values))==len(values) and self.required_scope in values
            and set(values)<=self.scopes) else ''

    def check_redirect_uri(self,value):
        return value in self.callbacks

    def check_client_secret(self,value):
        return False

    def check_endpoint_auth_method(self,method,endpoint):
        return method=='none' and endpoint=='token'

    def check_response_type(self,value):
        return value=='code'

    def check_grant_type(self,value):
        return value=='authorization_code' or value=='refresh_token' and self.refresh_allowed


def configured_status_clients(settings):
    clients={}
    if settings.get('NEKTRON_STATUS_OAUTH_ENABLED')=='true':
        clients[STATUS_CLIENT]=StatusClient(STATUS_CLIENT,settings['NEKTRON_STATUS_CHATGPT_CALLBACK'])
    if settings.get('NEKTRON_STATUS_WORKER_OAUTH_ENABLED')=='true':
        clients[WORKER_CLIENT]=StatusClient(WORKER_CLIENT,settings['NEKTRON_STATUS_WORKER_CALLBACK'])
    return clients


STATUS_CONSENT='''<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><meta name="referrer" content="no-referrer">
<meta http-equiv="Content-Security-Policy" content="default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'none'; form-action 'self'">
<title>Connect Status Endpoint | NektronAI</title><link rel="stylesheet" href="/assets/database-connector-setup/app.css">
<script defer src="/api/account/oauth/consent.js"></script></head><body><main>
<p class="eyebrow">NEKTRON, INC.</p><h1>Connect {{ display_name }}</h1>
<p>Allow only these requested permissions:</p><ul>{% for scope in scopes %}<li>{{ descriptions[scope] }}</li>{% endfor %}</ul>
<p>Tenant, agent and task access still require separate current application grants.
Task IDs and status text do not grant permission. Queueing does not start an agent.</p>
{% if worker %}<p>This worker authorization issues one access token valid for five minutes, with no refresh token.
It does not authorize unattended work or change the runner's execution policy.</p>{% endif %}
<p>Database connections, account credentials and overall task verification are unchanged.</p>
<form id="consent" data-csrf="{{ csrf }}" data-nonce="{{ nonce }}">
<button class="primary" type="submit" value="yes">Allow connection</button>
<button class="secondary" type="submit" value="no">Cancel</button></form>
<p id="status" role="status"></p></main></body></html>'''

SCOPE_DESCRIPTIONS={
    STATUS_READ:'Read only tasks authorized for this account.',
    'task-status:read-internal':'Read internal details for tasks with explicit internal-read access.',
    'task-status:create':'Create task tracking for an explicitly authorized registered agent.',
    'task-status:dispatch':'Request queued work for an explicitly authorized task and agent.',
    'task-status:report':'Report attributed progress on assigned tasks or tasks within the explicitly authorized workspace; never grant overall completion authority.',
    WORKER_SCOPE:'Claim and report tasks assigned to this exact authorized worker identity and agent.'}
