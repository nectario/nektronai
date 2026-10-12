import '/assets/connector-journey.js?v=4cee55db351b';
const $ = (id) => document.getElementById(id);
let config, accessToken = null, tokenExpires = 0, inputMode = 'details', busy = false;
const dialog = $('database-dialog');
const connectingChatGPT = new URLSearchParams(location.search).get('returnTo') === 'connector-authorize';
const message = (text) => { $('page-message').textContent = text; };
const error = (text) => { $('form-error').textContent = text; $('form-error').hidden = !text; };
const random = () => { const bytes = crypto.getRandomValues(new Uint8Array(32)); return btoa(String.fromCharCode(...bytes)).replaceAll('+','-').replaceAll('/','_').replaceAll('=',''); };
const base64 = (bytes) => btoa(String.fromCharCode(...new Uint8Array(bytes))).replaceAll('+','-').replaceAll('/','_').replaceAll('=','');

async function signIn() {
  if(!config?.configured)return;
  location.assign(connectingChatGPT?'/login.html?returnTo=connector-authorize':'/login.html?returnTo=connector');
}

async function acquireNativeToken() {
  if(!config?.configured)throw new Error('Open database setup on nektron.ai.');
  const headers={'Content-Type':'application/json'};
  const csrfResponse=await fetch('/api/account/csrf',{credentials:'same-origin',cache:'no-store',signal:AbortSignal.timeout(10000)});
  if(!csrfResponse.ok)throw new Error('Account access is temporarily unavailable.');
  const csrf=(await csrfResponse.json()).csrfToken;
  if(!csrf)throw new Error('Sign in to your NektronAI account to continue.');
  headers['X-CSRF-Token']=csrf;
  const response=await fetch('/api/account/connector-token',{method:'POST',credentials:'same-origin',headers,body:'{}',signal:AbortSignal.timeout(10000)});
  if(!response.ok){accessToken=null;tokenExpires=0;$('signin').textContent='Sign in';
    const failure=new Error(response.status===401?'Sign in to your NektronAI account to manage your databases.':'Database account access is temporarily unavailable.');if(response.status===401)failure.code='NEKTRON_SIGNIN_REQUIRED';throw failure;}
  const result=await response.json();
  if(result.token_type!=='Bearer'||!result.access_token||result.expires_in!==300)throw new Error('Account access could not be verified.');
  accessToken=result.access_token;tokenExpires=Date.now()+result.expires_in*1000;
  $('signin').textContent='Sign out';
}

async function nativeSignOut() {
  const response=await fetch('/api/account/csrf',{credentials:'same-origin',cache:'no-store',signal:AbortSignal.timeout(10000)});
  if(!response.ok)throw new Error('Sign out could not be completed. Try again.');
  const csrf=(await response.json()).csrfToken;
  const logout=await fetch('/api/account/logout',{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json','X-CSRF-Token':csrf},body:'{}',signal:AbortSignal.timeout(10000)});
  if(!logout.ok)throw new Error('Sign out could not be completed. Try again.');
  accessToken=null;tokenExpires=0;clearCredentials();$('connections').replaceChildren();
  $('signin').textContent='Sign in';$('empty').hidden=false;$('add').disabled=false;
  message('Signed out of your NektronAI account.');
}

async function api(path, options = {}) {
  if (!accessToken || tokenExpires <= Date.now()+5000) await acquireNativeToken();
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
    card.append(status, name, details, permission);if(typeof result.account_ref==='string'&&/^[a-f0-9]{64}$/.test(result.account_ref)){const remove=document.createElement('button');remove.textContent='Remove';remove.className='secondary';remove.style.display='flex';remove.style.marginTop='18px';remove.onclick=()=>location.assign('/database-connector-remove.html?connection='+encodeURIComponent(connection.connection_id)+'&account='+result.account_ref);card.append(remove);}list.append(card);
  }
  $('empty').hidden = result.connections.length > 0;
  const full = result.enabled_count >= result.enabled_limit || result.saved_count >= result.saved_limit;
  $('add').disabled = full;
  if (full) message(`Your ${result.enabled_limit === 1 ? 'database is' : 'databases are'} connected. This account allows ${result.enabled_limit} enabled connection${result.enabled_limit === 1 ? '' : 's'}.`);
  else message('');
}

async function refreshConnections() { const result=await api('connections');renderConnections(result);return result; }
function continueConnection(result){if(connectingChatGPT&&result.connections.length){clearCredentials();location.assign('/api/account/oauth/resume');return true;}return false;}
async function cancelConnection(){if(busy)return;clearCredentials();const csrf=await fetch('/api/account/csrf',{credentials:'same-origin',cache:'no-store'});if(!csrf.ok)throw Error('Unable to cancel. Please try again.');const token=(await csrf.json()).csrfToken;const response=await fetch('/api/account/oauth/cancel-setup',{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json','X-CSRF-Token':token},body:'{}'});const result=await response.json();if(!response.ok)throw Error('This connection request expired. Return to ChatGPT.');const target=new URL(result.redirect);if(target.origin!=='https://chatgpt.com'||target.pathname!=='/connector_platform_oauth_redirect')throw Error('Unexpected return address.');location.assign(target.href);}
function clearCredentials() { $('password').value=''; $('connection-string').value=''; $('password').type='password'; $('show-password').textContent='Show'; $('show-password').setAttribute('aria-label','Show database password'); }
function setBusy(value) { busy=value; $('connect').disabled=value; $('progress').hidden=!value; $('cancel').disabled=value; $('close').disabled=value; }
function closeDialog() { if (busy) return; clearCredentials(); $('database-form').reset(); $('schema-fields').hidden=true;$('schema-name').required=false;$('database-caption').textContent='Database'; dialog.close(); $('add').focus(); }
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
const enginePorts={mysql:3306,postgresql:5432,sqlserver:1433,oracle:2484,mongodb:27017};
$('engine').addEventListener('change',()=>{clearCredentials();$('port').value=enginePorts[$('engine').value];$('schema-name').value='';$('schema-fields').hidden=['mysql','mongodb'].includes($('engine').value);$('schema-name').required=$('engine').value==='oracle';$('schema-caption').textContent=$('engine').value==='oracle'?'Table owner / schema':'Schema (optional)';$('database-caption').textContent=$('engine').value==='oracle'?'Service name':'Database';});
function invalidConnectionField(id, message) {
  const input=$(id);
  input.setAttribute('aria-invalid','true');
  input.focus();
  throw new Error(message);
}
function getDetails() {
  const fieldIds=['engine','host','port','database','username','password','connection-string','schema-name','name'];
  for(const id of fieldIds) $(id).removeAttribute('aria-invalid');
  const engine=$('engine').value,port=enginePorts[engine],name=$('name').value.trim();
  if(!Object.hasOwn(enginePorts,engine)) invalidConnectionField('engine','Select a supported database engine.');
  if(!$('name').checkValidity()) invalidConnectionField('name','Use a connection name of 100 characters or fewer.');
  let details;
  if(inputMode==='string') {
    const input=$('connection-string');
    if(!input.checkValidity()||!input.value.trim()) invalidConnectionField('connection-string','Enter a connection URL with host, database, username and password.');
    let url;
    try { url=new URL(input.value.trim()); }
    catch { invalidConnectionField('connection-string','Enter a connection URL with host, database, username and password.'); }
    if(url.protocol!==engine+':'||url.search||url.hash||!url.hostname||url.pathname.slice(1).includes('/'))
      invalidConnectionField('connection-string','Use the selected engine scheme without extra options or SRV discovery.');
    try {
      details={host:url.hostname,port:Number(url.port||port),database:decodeURIComponent(url.pathname.slice(1)),username:decodeURIComponent(url.username),password:decodeURIComponent(url.password)};
    } catch { invalidConnectionField('connection-string','Check the connection URL encoding.'); }
    if(!details.database||!details.username||!details.password) invalidConnectionField('connection-string','Enter a connection URL with host, database, username and password.');
    if(details.port!==port) invalidConnectionField('connection-string','Use port '+port+' for this engine.');
  } else {
    for(const id of ['host','port','database','username','password']) {
      const input=$(id),value=id==='password'?input.value:input.value.trim();
      if(!input.checkValidity()||!value) invalidConnectionField(id,id==='port'?'Use port '+port+' for this engine.':`Enter your database ${id}.`);
    }
    details={host:$('host').value.trim(),port:Number($('port').value),database:$('database').value.trim(),username:$('username').value.trim(),password:$('password').value};
    if(details.port!==port) invalidConnectionField('port','Use port '+port+' for this engine.');
  }
  if(/[\s/@\\?#]/.test(details.host)) invalidConnectionField(inputMode==='string'?'connection-string':'host','Enter a database hostname without a URL path.');
  const schema_name=$('schema-name').value.trim()||null;
  if(['mysql','mongodb'].includes(engine)&&schema_name) invalidConnectionField('engine','For '+(engine==='mysql'?'MySQL':'MongoDB')+', use the database field and leave schema empty.');
  if(engine==='oracle'&&!schema_name) invalidConnectionField('schema-name','Enter the Oracle table owner/schema; the database field is the service name.');
  if(!$('schema-name').checkValidity()) invalidConnectionField('schema-name','Enter a valid database schema of 128 characters or fewer.');
  return {...details,name,engine,schema_name,request_id:crypto.randomUUID()};
}

function connected(result) {
  sessionStorage.removeItem('connector.pending');
  clearCredentials(); $('database-form').hidden=true; $('success').hidden=false;
  $('success-message').textContent=`${result.connection.display_name} is ready in Database Connector.`;
  setBusy(false); $('done').focus(); refreshConnections().then(continueConnection).catch(e=>message(e.message));
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
$('signin').addEventListener('click',()=>{(accessToken?nativeSignOut():signIn()).catch(e=>message(e.message));});
window.addEventListener('pagehide',clearCredentials);
async function start() {
  try{const pending=JSON.parse(sessionStorage.getItem('connector.removal')||'null');if(pending?.resume===true&&pending.expires>Date.now()&&pending.expires<=Date.now()+600000){location.replace('/database-connector-remove.html');return;}}catch{}
  config={preview:false,configured:location.origin==='https://nektron.ai'&&location.pathname==='/database-connector-setup.html'};
  if(!config.configured){message('Open database setup on https://nektron.ai.');return;}
  if(connectingChatGPT){const returning=$('return-chatgpt');returning.href='/api/account/oauth/resume';returning.textContent='Continue to ChatGPT';const cancel=document.createElement('button');cancel.type='button';cancel.textContent='Cancel connection';cancel.addEventListener('click',()=>cancelConnection().catch(e=>message(e.message)));returning.after(cancel);}
  try {await acquireNativeToken();await api('account',{method:'POST',body:'{}'});const result=await refreshConnections();if(continueConnection(result))return;if((connectingChatGPT||location.hash==='#add')&&!$('add').disabled)await openDialog();}
  catch(e){if(location.hash==='#add'&&e.code==='NEKTRON_SIGNIN_REQUIRED'){await signIn();return;}message(e.message);}
}
start();
