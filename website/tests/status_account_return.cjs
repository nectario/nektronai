/* Real shared account/journey scripts in a synthetic DOM; no network or identities. */
'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {test} = require('node:test');
const vm = require('node:vm');
const root = process.env.STATUS_ACCOUNT_REVIEW_ROOT || path.resolve(__dirname, '..');
const source = fs.readFileSync(path.join(root, 'assets/account.js'), 'utf8');
const journey = fs.readFileSync(path.join(root, 'assets/connector-journey.js'), 'utf8');
const statusResume = '/api/account/oauth/resume';
const mailResume = '/api/account/mail-oauth/resume';

async function login(options) {
  let submit;
  const listeners = new Map(), destinations = [], calls = [];
  function storage(initial = {}) {
    const rows = new Map(Object.entries(initial));
    return {getItem:key=>rows.get(key)??null,setItem:(key,value)=>rows.set(key,String(value)),removeItem:key=>rows.delete(key)};
  }
  const button = {textContent:'Log in',disabled:false};
  const state = {textContent:'',toggleAttribute:()=>{},focus:()=>{}};
  const form = {dataset:{authForm:'login'},reportValidity:()=>true,reset:()=>{},
    querySelector:()=>button,querySelectorAll:()=>[],addEventListener:(type,handler)=>{if(type==='submit')submit=handler;}};
  const sessionStorage = storage(options.saved ? {'nektron.account.return':options.saved} : {});
  const localStorage = storage(options.journey ? {'nektron.connector.journey':JSON.stringify({target:options.journey,expires:Date.now()+300000})} : {});
  const location = {origin:'https://nektron.ai',hostname:'nektron.ai',pathname:'/login.html',
    search:options.search||'',hash:'',href:'https://nektron.ai/login.html'+(options.search||''),assign:value=>destinations.push(value)};
  const context = vm.createContext({
    document:{body:{dataset:{accountScreen:'login'}},
      querySelector:selector=>selector==='[data-account-status]'?state:null,
      querySelectorAll:selector=>selector==='[data-auth-form]'?[form]:[]},
    location,sessionStorage,localStorage,history:{replaceState:()=>{}},URL,URLSearchParams,AbortSignal,
    window:{addEventListener:(type,callback)=>listeners.set(type,callback)},
    FormData:class { *[Symbol.iterator](){yield ['email','synthetic@example.com'];yield ['password','synthetic-form-only'];}},
    fetch:async(url,settings={})=>{
      assert.ok(['/api/account/session','/api/account/csrf','/api/account/login'].includes(url));
      calls.push(url);
      if(url.endsWith('/login')) {
        assert.equal(settings.method,'POST');
        assert.equal(settings.headers['X-CSRF-Token'],'synthetic-csrf');
      }
      return {ok:true,json:async()=>url.endsWith('/session')?{authenticated:false}:url.endsWith('/csrf')?{csrfToken:'synthetic-csrf'}:{authenticated:true,redirect:options.server}};
    }
  });
  vm.runInContext(journey,context,{filename:'connector-journey.js'});
  vm.runInContext(source,context,{filename:'account.js'});
  listeners.get('pageshow')();
  await new Promise(resolve=>setImmediate(resolve));
  assert.equal(button.disabled,false);
  assert.equal(typeof submit,'function');
  await submit({preventDefault:()=>{}});
  assert.ok(calls.includes('/api/account/login'));
  assert.equal(sessionStorage.getItem('nektron.account.return'),null,'Consume navigation intent after login');
  assert.equal(destinations.length,1,'Navigate exactly once');
  return destinations[0];
}

const scenarios = [
  ['Status resumes without saved navigation', {server:statusResume}, statusResume],
  ['Status overrides stale Connector setup journey', {server:statusResume,journey:'connector'}, statusResume],
  ['Status overrides stale saved Connector billing', {server:statusResume,saved:'connector-billing'}, statusResume],
  ['Status overrides stale saved Mail return', {server:statusResume,saved:'mail-authorize'}, statusResume],
  ['Status accepts its existing explicit shared authorize path', {server:statusResume,search:'?returnTo=connector-authorize'}, statusResume],
  ['Explicit Connector setup still wins over pending Status', {server:statusResume,search:'?returnTo=connector'}, '/database-connector-setup.html'],
  ['Explicit Connector billing still wins over pending Status', {server:statusResume,search:'?returnTo=connector-billing'}, '/database-connector.html#account'],
  ['Explicit Mail still wins over pending Status and stale Connector journey', {server:statusResume,search:'?returnTo=mail-authorize',journey:'connector'}, mailResume],
  ['Invalid query return cannot defeat fixed Status fallback', {server:statusResume,search:'?returnTo=https%3A%2F%2Funtrusted.example'}, statusResume],
  ['Mail resumes without saved navigation', {server:mailResume}, mailResume],
  ['Mail still overrides stale Connector setup journey', {server:mailResume,journey:'connector'}, mailResume],
  ['Explicit Connector authorize still wins over pending Mail', {server:mailResume,search:'?returnTo=connector-authorize'}, statusResume],
  ['Explicit Connector setup still wins over pending Mail', {server:mailResume,search:'?returnTo=connector'}, '/database-connector-setup.html'],
  ['Connector authorize return remains intact', {server:'/account.html',saved:'connector-authorize'}, statusResume],
  ['Connector setup journey remains intact', {server:'/account.html',journey:'connector'}, '/database-connector-setup.html'],
  ['Connector explicit setup replaces stale authorize journey', {server:'/account.html',journey:'connector-authorize',search:'?returnTo=connector'}, '/database-connector-setup.html'],
  ['Connector billing return remains intact', {server:'/account.html',saved:'connector-billing'}, '/database-connector.html#account'],
  ['Saved Mail return remains intact', {server:'/account.html',saved:'mail-authorize'}, mailResume],
  ['Ordinary account login remains intact', {server:'/account.html'}, 'account.html'],
  ['Unknown saved return is ignored', {server:'/account.html',saved:'__proto__'}, 'account.html'],
  ['Arbitrary server URL is ignored', {server:'https://untrusted.example/exfiltrate'}, 'account.html'],
  ['Scheme-relative server URL is ignored', {server:'//untrusted.example/exfiltrate'}, 'account.html'],
  ['Status fallback with query is rejected', {server:statusResume+'?next=https://untrusted.example'}, 'account.html'],
  ['Status fallback with fragment is rejected', {server:statusResume+'#unexpected'}, 'account.html'],
  ['Mail fallback with query is rejected', {server:mailResume+'?next=https://untrusted.example'}, 'account.html'],
  ['Non-string server fallback is rejected', {server:[statusResume]}, 'account.html'],
];

for(const [name,options,expected] of scenarios) {
  test(name,async()=>assert.equal(await login(options),expected));
}
