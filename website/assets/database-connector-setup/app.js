const $ = (id) => document.getElementById(id);
let config, accessToken = null, tokenExpires = 0, inputMode = 'details', busy = false;
const dialog = $('database-dialog');
const message = (text) => { $('page-message').textContent = text; };
const error = (text) => { $('form-error').textContent = text; $('form-error').hidden = !text; };
const random = () => { const bytes = crypto.getRandomValues(new Uint8Array(32)); return btoa(String.fromCharCode(...bytes)).replaceAll('+','-').replaceAll('/','_').replaceAll('=',''); };
const base64 = (bytes) => btoa(String.fromCharCode(...new Uint8Array(bytes))).replaceAll('+','-').replaceAll('/','_').replaceAll('=','');

async function signIn() {
  if (config.preview) return;
  if (!config.configured) { message('Database setup is not configured yet. Your existing ChatGPT connection is unaffected.'); return; }
  const state = random(), verifier = random();
  sessionStorage.setItem('connector.pkce', JSON.stringify({state, verifier, created: Date.now()}));
  const challenge = base64(await crypto.subtle.digest('SHA-256', new TextEncoder().encode(verifier)));
  const url = new URL(`${config.issuer}/authorize`);
  url.search = new URLSearchParams({response_type:'code', client_id:config.client_id, redirect_uri:config.redirect_uri,
    scope:config.scope, audience:config.audience, resource:config.audience, state, code_challenge:challenge, code_challenge_method:'S256'});
  location.assign(url);
}

async function finishSignIn() {
  const params = new URLSearchParams(location.search);
  if (!params.has('code') && !params.has('error')) return;
  const raw = sessionStorage.getItem('connector.pkce');
  sessionStorage.removeItem('connector.pkce');
  history.replaceState(null, '', '/database-connector-setup.html'); // Remove codes before any subsequent navigation.
  let pending;
  try { pending = JSON.parse(raw); } catch { throw new Error('Sign-in could not be verified. Please sign in again.'); }
  if (params.has('error') || !pending || params.get('state') !== pending.state || Date.now()-pending.created > 600000 || Date.now()<pending.created) {
    throw new Error('Sign-in could not be verified. Please sign in again.');
  }
  const response = await fetch(`${config.issuer}/oauth/token`, {method:'POST', credentials:'omit',
    headers:{'Content-Type':'application/x-www-form-urlencoded'},
    body:new URLSearchParams({grant_type:'authorization_code', client_id:config.client_id, code:params.get('code'),
      redirect_uri:config.redirect_uri, code_verifier:pending.verifier, resource:config.audience})});
  const result = await response.json();
  if (!response.ok || !result.access_token || result.token_type?.toLowerCase() !== 'bearer') throw new Error('Sign-in could not be completed. Please try again.');
  accessToken = result.access_token; // Memory only: no token/password browser storage.
  tokenExpires = Date.now() + Number(result.expires_in || 0)*1000;
  $('signin').textContent = 'Sign out';
}

async function api(path, options = {}) {
  if (!config.preview && (!accessToken || tokenExpires <= Date.now()+5000)) throw new Error('Your session has expired. Sign in again before connecting.');
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 29000);
  try {
    const response = await fetch(`https://3frqh3q39i.execute-api.us-east-2.amazonaws.com/setup/api/${path}`, {...options, signal:controller.signal, credentials:'omit',
      headers:{'Content-Type':'application/json', ...(accessToken ? {Authorization:`Bearer ${accessToken}`} : {}), ...options.headers}});
    const body = await response.json();
    if (!response.ok) {
      const e = new Error(body.error?.message || 'The request could not be completed.');
      e.code = body.error?.code; throw e;
    }
    return body;
  } finally { clearTimeout(timer); }
}

function renderConnections(result) {
  const list = $('connections'); list.replaceChildren();
  for (const connection of result.connections) {
    const card = document.createElement('article'); card.className = 'connection-card';
    const status = document.createElement('span'); status.className = 'card-status'; status.textContent = 'Available in ChatGPT';
    const name = document.createElement('h2'); name.textContent = connection.display_name;
    const details = document.createElement('p'); details.textContent = `${connection.engine.toUpperCase()} · ${connection.database}`;
    const permission = document.createElement('span'); permission.className='badge'; permission.textContent='Read-only';
    card.append(status, name, details, permission); list.append(card);
  }
  $('empty').hidden = result.connections.length > 0;
  const full = result.enabled_count >= result.enabled_limit || result.saved_count >= result.saved_limit;
  $('add').disabled = full;
  if (full) message(`Your ${result.enabled_limit === 1 ? 'database is' : 'databases are'} connected. This account allows ${result.enabled_limit} enabled connection${result.enabled_limit === 1 ? '' : 's'}.`);
  else message('');
}

async function refreshConnections() { renderConnections(await api('connections')); }
function clearCredentials() { $('password').value=''; $('connection-string').value=''; $('password').type='password'; $('show-password').textContent='Show'; $('show-password').setAttribute('aria-label','Show database password'); }
function setBusy(value) { busy=value; $('connect').disabled=value; $('progress').hidden=!value; $('cancel').disabled=value; $('close').disabled=value; }
function closeDialog() { if (busy) return; clearCredentials(); $('database-form').reset(); dialog.close(); $('add').focus(); }
async function openDialog() {
  if (!config) return;
  if (!config.preview && !accessToken) { await signIn(); return; }
  error(''); $('success').hidden=true; $('database-form').hidden=false; setBusy(false);
  dialog.showModal(); (inputMode==='details' ? $('host') : $('connection-string')).focus();
}
function setMode(mode) {
  inputMode=mode;
  for (const name of ['details','string']) { const active=mode===name; $(`${name}-tab`).setAttribute('aria-selected',String(active)); $(`${name}-tab`).tabIndex=active?0:-1; $(`${name}-panel`).hidden=!active; }
  error('');
}
function getDetails() {
  const name=$('name').value.trim();
  let details;
  if (inputMode==='string') {
    let url;
    try { url=new URL($('connection-string').value.trim()); } catch { throw new Error('Enter a MySQL connection URL with a host, database, username and password.'); }
    if (url.protocol!=='mysql:' || url.search || url.hash || url.pathname.slice(1).includes('/') || !url.hostname) throw new Error('Use mysql://user:password@host:3306/database without extra options. TLS is always enabled.');
    try { details={host:url.hostname,port:Number(url.port||3306),database:decodeURIComponent(url.pathname.slice(1)),username:decodeURIComponent(url.username),password:decodeURIComponent(url.password)}; }
    catch { throw new Error('Check the connection URL encoding.'); }
  } else {
    for (const id of ['host','port','database','username','password']) {
      const input=$(id); input.removeAttribute('aria-invalid');
      if (!input.checkValidity() || !input.value) { input.setAttribute('aria-invalid','true'); input.focus(); throw new Error(id==='port' ? 'This release uses MySQL port 3306.' : `Enter your database ${id}.`); }
    }
    details={host:$('host').value.trim(),port:Number($('port').value),database:$('database').value.trim(),username:$('username').value.trim(),password:$('password').value};
  }
  if (!details.database || !details.username || !details.password || details.port!==3306) throw new Error('Enter all connection details. This release uses MySQL port 3306.');
  if (/[\s/@\\?#]/.test(details.host)) throw new Error('Enter a database hostname, without a URL scheme or path.');
  return {...details,name,engine:'mysql',request_id:crypto.randomUUID()};
}

function connected(result) {
  sessionStorage.removeItem('connector.pending');
  clearCredentials(); $('database-form').hidden=true; $('success').hidden=false;
  $('success-message').textContent=`${result.connection.display_name} is ready in Database Connector.`;
  setBusy(false); $('done').focus(); refreshConnections().catch(e=>message(e.message));
}
async function pollRequest(id) {
  for (let attempt=0; attempt<8; attempt++) {
    const result=await api(`requests/${encodeURIComponent(id)}`);
    if (result.status==='connected') { connected(result); return; }
    await new Promise(resolve=>setTimeout(resolve,2000));
  }
  throw new Error(`The save is still pending. Check your connection list before retrying. Request ID: ${id}`);
}
$('database-form').addEventListener('submit',async event=>{
  event.preventDefault(); if(busy) return; error(''); let details;
  try { details=getDetails(); } catch(e) { error(e.message); return; }
  if(config.preview) { clearCredentials(); error('This is a design preview. No credentials were sent or saved. Sign-in and database validation are required in the deployed setup.'); return; }
  setBusy(true); const requestId=details.request_id;
  sessionStorage.setItem('connector.pending',requestId);
  try {
    const pending=api('connections',{method:'POST',body:JSON.stringify(details)});
    clearCredentials(); details=null;
    const result=await pending;
    if(result.status==='connected') connected(result); else await pollRequest(requestId);
  } catch(e) {
    clearCredentials();
    if(e.name==='AbortError' || e.code==='REVIEW_REQUIRED') {
      try { await pollRequest(requestId); return; } catch(reconcileError) { error(`${reconcileError.message} Request ID: ${requestId}`); }
    } else { sessionStorage.removeItem('connector.pending'); error(e.message); }
  } finally { details=null; setBusy(false); }
});
$('add').addEventListener('click',openDialog); $('empty-add').addEventListener('click',openDialog);
for(const id of ['close','cancel','done']) $(id).addEventListener('click',closeDialog);
dialog.addEventListener('cancel',event=>{event.preventDefault(); closeDialog();});
$('show-password').addEventListener('click',()=>{const reveal=$('password').type==='password'; $('password').type=reveal?'text':'password'; $('show-password').textContent=reveal?'Hide':'Show'; $('show-password').setAttribute('aria-label',`${reveal?'Hide':'Show'} database password`);});
for(const mode of ['details','string']) { $(`${mode}-tab`).addEventListener('click',()=>setMode(mode)); $(`${mode}-tab`).addEventListener('keydown',e=>{if(['ArrowLeft','ArrowRight'].includes(e.key)){e.preventDefault(); const next=inputMode==='details'?'string':'details'; setMode(next); $(`${next}-tab`).focus();}}); }
$('signin').addEventListener('click',()=>{if(accessToken){accessToken=null;tokenExpires=0;clearCredentials();$('signin').textContent='Sign in';$('connections').replaceChildren();$('empty').hidden=false;$('add').disabled=false;message('Signed out of database setup.');}else signIn();});
window.addEventListener('pagehide',clearCredentials);
async function start() {
  try {
    const response=await fetch('/assets/database-connector-setup/config.json',{credentials:'omit',cache:'no-store'}); if(!response.ok) throw new Error('Database setup is temporarily unavailable.');
    config=await response.json();
    if(location.origin !== 'https://nektron.ai' || location.pathname !== '/database-connector-setup.html' ||
       config.preview !== false || config.configured !== true ||
       config.issuer !== 'https://dev-cmgmokiptmjiwjri.us.auth0.com' || config.client_id !== '9bYdBkEd654k8ktx58UtDqDVL3TnEgJ8' ||
       config.audience !== 'https://3frqh3q39i.execute-api.us-east-2.amazonaws.com/mcp' || config.scope !== 'openid database-connector/manage' ||
       config.redirect_uri !== 'https://nektron.ai/database-connector-setup.html') {
      config.configured=false;
      throw new Error('Database setup is not configured for this address. Open https://nektron.ai/database-connector-setup.html.');
    }
    if(config.preview){$('preview-note').hidden=false;$('signin').textContent='Preview';$('signin').disabled=true;await refreshConnections();return;}
    await finishSignIn();
    if(accessToken){await api('account',{method:'POST',body:'{}'});await refreshConnections();const pending=sessionStorage.getItem('connector.pending');if(pending){await openDialog();setBusy(true);try{await pollRequest(pending);}finally{setBusy(false);}}}
    else message(config.configured?'Sign in with the same account you use for Database Connector in ChatGPT.':'Database setup is not configured yet. Your existing ChatGPT connection is unaffected.');
  } catch(e){message(e.message);}
}
start();
