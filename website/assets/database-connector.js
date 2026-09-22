const byId = (id) => document.getElementById(id);
const scenarios = {
  orders: { question:'Which products brought in the most revenue this month?', answer:'Here are the top products by revenue.', caption:'Illustrative product revenue, not a live query', columns:['Product','Orders','Revenue'], rows:[['Studio Desk','128','$38,400'],['Arc Lamp','204','$24,480'],['Oak Shelf','96','$17,280']], followup:'And how does that compare with last month?', detail:'In this sample, Studio Desk revenue increased 20%, Arc Lamp increased 8%, and Oak Shelf decreased 4%. A real follow-up would query the comparison period in your database.' },
  support: { question:'Which topics generated the most support tickets this week?', answer:'These topics account for the most tickets in the example.', caption:'Illustrative support ticket counts, not a live query', columns:['Topic','Tickets','Resolved'], rows:[['Account access','86','79'],['Billing questions','54','48'],['Delivery updates','37','31']], followup:'Which topic has the longest resolution time?', detail:'In this sample, billing questions take the longest to resolve: a median of 6.2 hours. A real investigation would use your ticket timestamps and explain any missing values.' },
  operations: { question:'Which locations have the most orders waiting to ship?', answer:'Here is the unshipped order count for each location.', caption:'Illustrative fulfillment counts, not a live query', columns:['Location','Waiting','Over 2 days'], rows:[['East warehouse','42','8'],['Central warehouse','31','3'],['West warehouse','18','2']], followup:'What is holding up the East warehouse?', detail:'In this sample, five of the eight older orders are waiting for the same component. A real follow-up would use the returned order identifiers to inspect the related records.' }
};
let selectedScenario = 'orders';
const tabs = [...document.querySelectorAll('[data-scenario]')];
function renderScenario(name, focus = false) {
  selectedScenario = name;
  const data = scenarios[name];
  for (const tab of tabs) { const active = tab.dataset.scenario === name; tab.setAttribute('aria-selected',String(active)); tab.tabIndex = active ? 0 : -1; if(active && focus) tab.focus(); }
  byId('demo-panel').setAttribute('aria-labelledby',`${name}-tab`);
  byId('demo-question').textContent=data.question; byId('demo-answer').textContent=data.answer;
  const table=byId('demo-table'); table.querySelector('caption').textContent=data.caption;
  const headings=document.createElement('tr');
  for(const label of data.columns){const cell=document.createElement('th');cell.scope='col';cell.textContent=label;headings.append(cell);}
  table.tHead.replaceChildren(headings); table.tBodies[0].replaceChildren();
  for(const row of data.rows){const tr=document.createElement('tr');row.forEach((text,index)=>{const cell=document.createElement(index===0?'th':'td');if(index===0)cell.scope='row';cell.textContent=text;tr.append(cell);});table.tBodies[0].append(tr);}
  byId('demo-followup').textContent=data.followup+' ↗︎'; byId('demo-followup').setAttribute('aria-expanded','false');
  byId('demo-followup-answer').hidden=true;byId('demo-followup-answer').textContent='';
}
tabs.forEach((tab,index)=>{tab.addEventListener('click',()=>renderScenario(tab.dataset.scenario));tab.addEventListener('keydown',event=>{let next;if(event.key==='ArrowRight')next=(index+1)%tabs.length;else if(event.key==='ArrowLeft')next=(index+tabs.length-1)%tabs.length;else if(event.key==='Home')next=0;else if(event.key==='End')next=tabs.length-1;else return;event.preventDefault();renderScenario(tabs[next].dataset.scenario,true);});});
byId('demo-followup').setAttribute('aria-controls','demo-followup-answer');byId('demo-followup').setAttribute('aria-expanded','false');
byId('demo-followup').addEventListener('click',()=>{const output=byId('demo-followup-answer'),open=output.hidden;output.textContent=scenarios[selectedScenario].detail;output.hidden=!open;byId('demo-followup').setAttribute('aria-expanded',String(open));});
document.querySelector('[data-explore]').addEventListener('click',()=>{tabs.find(t=>t.dataset.scenario===selectedScenario).focus({preventScroll:true});});
document.querySelectorAll('[data-open-setup]').forEach(button=>button.addEventListener('click',()=>byId('setup-dialog').showModal()));

// Native account/billing section appended to the existing product-page visuals.
let selectedPlan='free', config=null, accessToken=null, expiresAt=0, pending=false, currentAccount=null;
const status=(text)=>{byId('account-status').textContent=text;};
const messages={AUTH_REQUIRED:'Sign in to manage your account.',EMAIL_VERIFICATION_REQUIRED:'Verify your NektronAI email, then sign in again.',SETUP_UNAVAILABLE:'Account setup is not open yet.',BILLING_UNAVAILABLE:'Billing is not available right now. Your existing access is unchanged.',SUBSCRIPTION_EXISTS:'You already have a subscription. Choose Manage billing to review it.',BILLING_REVIEW_REQUIRED:'Please contact info@nektron.ai before retrying this billing request.'};
function updateCheckout(){byId('account-checkout').hidden=!currentAccount?.billing_available||currentAccount.plan==='pro'||selectedPlan!=='pro';}
function choosePlan(plan){selectedPlan=plan;const pro=plan==='pro';byId('selected-plan').textContent=pro?'Pro':'Free';byId('selected-limit').textContent=pro?'Up to 5 databases':'1 database';byId('selected-price').textContent=pro?'$12 USD / month':'$0';updateCheckout();if(!accessToken)status(`${pro?'Pro':'Free'} selected. ${config?.enabled?'Sign in to continue.':'Account sign-in and billing will open with the public release.'}`);}
document.querySelectorAll('[data-plan]').forEach(link=>link.addEventListener('click',()=>choosePlan(link.dataset.plan)));
async function nativeToken(){
  const csrfResponse=await fetch('/api/account/csrf',{credentials:'same-origin',cache:'no-store',signal:AbortSignal.timeout(10000)});
  if(!csrfResponse.ok)throw new Error('Account access is temporarily unavailable.');
  const csrf=(await csrfResponse.json()).csrfToken;
  if(!csrf)throw new Error(messages.AUTH_REQUIRED);
  const response=await fetch('/api/account/connector-token',{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json','X-CSRF-Token':csrf},body:'{}',signal:AbortSignal.timeout(10000)});
  if(!response.ok){accessToken=null;expiresAt=0;throw new Error(response.status===401?messages.AUTH_REQUIRED:'Account access is temporarily unavailable.');}
  const value=await response.json();
  if(value.token_type!=='Bearer'||!value.access_token||!Number.isFinite(value.expires_in)||value.expires_in<=0||value.expires_in>300)throw new Error('Account access could not be verified.');
  accessToken=value.access_token;expiresAt=Date.now()+value.expires_in*1000;
}
async function api(action){
  if(!accessToken||expiresAt<=Date.now()+5000)await nativeToken();
  const route=action==='account'?'/setup/api/account':`/billing/api/${action}`;
  const response=await fetch(`${config.apiBase}${route}`,{method:'POST',credentials:'omit',headers:{'Content-Type':'application/json',Authorization:`Bearer ${accessToken}`},body:'{}',signal:AbortSignal.timeout(29000)});
  const result=await response.json();
  if(!response.ok)throw new Error(messages[typeof result.error==='string'?result.error:result.error?.code]||'The request could not be completed.');
  return result;
}
async function signIn(){if(config?.enabled)location.assign('/login.html?returnTo=connector-billing');}
function clearSession(){accessToken=null;expiresAt=0;currentAccount=null;byId('account-actions').hidden=true;if(config?.enabled){byId('account-signin').textContent='Sign in to your account';byId('account-badge').textContent='YOUR ACCOUNT';byId('account-plan-label').textContent='Your plan and databases';}}
async function signOut(){
  const csrfResponse=await fetch('/api/account/csrf',{credentials:'same-origin',cache:'no-store',signal:AbortSignal.timeout(10000)});
  if(!csrfResponse.ok)throw new Error('Sign out could not be completed.');
  const csrf=(await csrfResponse.json()).csrfToken;
  const response=await fetch('/api/account/logout',{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json','X-CSRF-Token':csrf},body:'{}',signal:AbortSignal.timeout(10000)});
  if(!response.ok)throw new Error('Sign out could not be completed.');
  clearSession();status('Signed out.');
}
function renderAccount(account){
  currentAccount=account;
  if(account.plan==='pro')choosePlan('pro');
  byId('account-signin').textContent='Sign out';byId('account-badge').textContent=config.testBilling&&account.billing_available?'TEST BILLING':'SIGNED IN';
  byId('account-plan-label').textContent=`${account.plan==='pro'?'Pro':account.plan==='free'?'Free':'Private'} account · ${account.saved_connections} saved database${account.saved_connections===1?'':'s'}`;
  byId('account-actions').hidden=false;updateCheckout();byId('account-portal').hidden=!account.has_billing_customer;
  byId('account-setup').href=config.setupUrl;
  byId('account-checkout').textContent=config.testBilling?'Open Stripe test checkout':'Continue to Stripe · $12/month';
  status(config.testBilling&&account.billing_available?'Payment testing is enabled for this approved account. Use Stripe test payment details only; no real payment will be taken.':'Signed in. Manage your database connections below.');
}
byId('account-signin').addEventListener('click',()=>{(accessToken?signOut():signIn()).catch(error=>status(error.message));});
async function billingAction(action){
  if(pending||!currentAccount?.billing_available)return;
  pending=true;const button=byId(action==='checkout'?'account-checkout':'account-portal');button.disabled=true;
  status(config.testBilling?'Opening Stripe test billing…':'Opening secure Stripe billing…');
  try{const result=await api(action);const url=new URL(result.url);const expected=action==='checkout'?'checkout.stripe.com':'billing.stripe.com';if(url.protocol!=='https:'||url.hostname!==expected||url.username||url.password||url.port)throw new Error('The billing destination could not be verified.');location.assign(url.href);}
  catch(error){status(error.name==='TimeoutError'?'The request is still being checked. Reload your account before retrying.':error.message);}
  finally{pending=false;button.disabled=false;}
}
byId('account-checkout').addEventListener('click',()=>billingAction('checkout'));byId('account-portal').addEventListener('click',()=>billingAction('portal'));
window.addEventListener('pagehide',clearSession);
async function start(){
  try{
    const response=await fetch('assets/database-connector/config.json',{credentials:'omit',cache:'no-store'});if(!response.ok)return;config=await response.json();
    if(!config.enabled)return;
    if(location.origin!=='https://nektron.ai'||location.pathname!=='/database-connector.html'||config.mode!=='nektron-native'||config.apiBase!=='https://3frqh3q39i.execute-api.us-east-2.amazonaws.com'||config.setupUrl!=='https://nektron.ai/database-connector-setup.html')throw new Error('Account access is not configured for this page.');
    byId('account-signin').disabled=false;byId('account-signin').textContent='Sign in to your account';byId('account-badge').textContent='YOUR ACCOUNT';
    renderAccount(await api('account'));
  }catch(error){status(error.message||'Account access is temporarily unavailable.');}
}
start();
