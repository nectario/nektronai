/* Non-secret, bounded navigation intent only. Never stores credentials or OAuth tokens. */
(()=>{'use strict';
if(location.origin!=='https://nektron.ai')return;
const KEY='nektron.connector.journey',TTL=60*60*1000,allowed=new Set(['connector','connector-authorize']);
function chatReturn(value){try{const url=new URL(value);return url.protocol==='https:'&&url.hostname==='chatgpt.com'&&!url.username&&!url.password&&!url.port&&!url.search&&!url.hash&&/^\/(?:c\/[A-Za-z0-9-]+)?\/?$/.test(url.pathname)?url.href:null;}catch{return null;}}
function read(){try{const value=JSON.parse(localStorage.getItem(KEY));return value&&allowed.has(value.target)&&Number.isFinite(value.expires)&&value.expires>Date.now()&&value.expires<=Date.now()+TTL&&(!value.chat||chatReturn(value.chat))?value:null;}catch{return null;}}
const params=new URLSearchParams(location.search),requested=params.get('returnTo');
if(requested&&!allowed.has(requested))return;
let journey=read();
if(allowed.has(requested)||params.has('redirectUrl')||(location.pathname==='/database-connector-setup.html'&&location.hash==='#add')){
 journey={target:allowed.has(requested)?requested:'connector',chat:chatReturn(params.get('redirectUrl'))||journey?.chat||null,expires:Date.now()+TTL};
 try{localStorage.setItem(KEY,JSON.stringify(journey));}catch{}
}
if(!journey)return;
try{sessionStorage.setItem('nektron.account.return',journey.target);}catch{}
for(const link of document.querySelectorAll('a[href]')){
 try{const url=new URL(link.getAttribute('href'),location.href);if(url.origin===location.origin&&/^\/(login|signup|verify-email)\.html$/.test(url.pathname)){url.searchParams.set('returnTo',journey.target);link.href=url.pathname+url.search+url.hash;}}catch{}
}
if(location.pathname==='/database-connector-setup.html'){
 const returning=document.getElementById('return-chatgpt');
 if(returning){returning.href=journey.chat||'https://chatgpt.com/';returning.addEventListener('click',()=>{try{localStorage.removeItem(KEY);sessionStorage.removeItem('nektron.account.return');}catch{}});}
 if(!location.hash)history.replaceState(null,'',location.pathname+location.search+'#add');
}
})();
